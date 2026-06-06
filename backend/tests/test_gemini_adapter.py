"""
Unit tests for `GeminiAdapter`.

We don't hit the real API — a fake `google.genai` module is injected
via `sys.modules` so every request shape is asserted against a mock
client. The tests pin the behaviours downstream code depends on:

* `chat_turn` renders history with "assistant" → "model" role mapping.
* `chat_turn` pins `temperature=0` + JSON mime by default (the planner
  depends on reproducibility).
* `single_shot` passes `max_output_tokens` through when set.
* The adapter is stateless / freezable — it's a `@dataclass(frozen=True)`.
* Lazy SDK import: building an adapter instance must NOT import google.genai.
"""
from __future__ import annotations

import sys
import types
from dataclasses import FrozenInstanceError
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fake google.genai SDK — installed into sys.modules before the adapter
# ever calls `_sdk()`, so the real package is never loaded in this test.
# ---------------------------------------------------------------------------
class _FakeContent:
    def __init__(self, role: str, parts: list[Any]) -> None:
        self.role = role
        self.parts = parts

    def __repr__(self) -> str:  # pragma: no cover - debug only
        text = "|".join(getattr(p, "text", "") for p in self.parts)
        return f"Content(role={self.role!r}, text={text!r})"


class _FakePart:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, recorder: dict, api_key: str) -> None:
        self._recorder = recorder
        self._api_key = api_key

    def generate_content(self, *, model: str, contents: Any, config: Any) -> _FakeResponse:
        self._recorder.setdefault("keys_attempted", []).append(self._api_key)
        fail_for = self._recorder.get("fail_for_keys") or ()
        if self._api_key in fail_for:
            raise TimeoutError(f"simulated timeout for {self._api_key}")
        self._recorder.setdefault("keys_used", []).append(self._api_key)
        self._recorder["model"] = model
        self._recorder["contents"] = contents
        self._recorder["config"] = config.kwargs
        return _FakeResponse(text=self._recorder.get("reply", "ok"))


class _FakeClient:
    def __init__(self, *, api_key: str, recorder: dict) -> None:
        recorder["api_key"] = api_key
        recorder["client_construct_count"] = recorder.get("client_construct_count", 0) + 1
        self.models = _FakeModels(recorder, api_key)


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Install a fake `google` + `google.genai` + `google.genai.types`
    into sys.modules. Returns a recorder dict the tests inspect after
    the adapter fires a request."""
    recorder: dict = {}

    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    types_mod = types.ModuleType("google.genai.types")

    genai_mod.Client = lambda api_key: _FakeClient(api_key=api_key, recorder=recorder)
    types_mod.Content = _FakeContent
    types_mod.Part = _FakePart
    types_mod.GenerateContentConfig = _FakeConfig

    # Wire the tree so `from google import genai` resolves.
    google_mod.genai = genai_mod
    genai_mod.types = types_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.genai", genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_mod)

    # Ensure the adapter can read an API key deterministically.
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY_2", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_3", raising=False)
    from llm import reset_llm_runtime_for_tests

    reset_llm_runtime_for_tests()
    return recorder


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_adapter_is_frozen() -> None:
    """Adapter is a frozen dataclass — safe to stash in a global / module."""
    from llm import GeminiAdapter

    a = GeminiAdapter()
    with pytest.raises(FrozenInstanceError):
        a.default_model = "other-model"  # type: ignore[misc]


def test_chat_turn_translates_history_roles(fake_sdk: dict) -> None:
    from llm import GeminiAdapter

    fake_sdk["reply"] = "{\"ok\": true}"
    out = GeminiAdapter().chat_turn(
        system_prompt="SYS",
        history=[
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ],
        user_turn="now",
    )
    assert out == "{\"ok\": true}"

    contents = fake_sdk["contents"]
    # 3 entries: the 2 history turns + the current user_turn.
    assert [c.role for c in contents] == ["user", "model", "user"]
    # Roles and text round-trip cleanly.
    assert contents[0].parts[0].text == "u1"
    assert contents[1].parts[0].text == "a1"
    assert contents[2].parts[0].text == "now"


def test_chat_turn_default_pins_determinism(fake_sdk: dict) -> None:
    """Planner relies on temperature=0 + JSON mime for reproducible drafts."""
    from llm import GeminiAdapter

    GeminiAdapter().chat_turn(system_prompt="S", history=[], user_turn="hi")
    cfg = fake_sdk["config"]
    assert cfg["system_instruction"] == "S"
    assert cfg["temperature"] == 0.0
    assert cfg["response_mime_type"] == "application/json"


def test_chat_turn_can_opt_out_of_json(fake_sdk: dict) -> None:
    """Chat endpoint wants prose, not JSON — json_mode=False must NOT
    attach `response_mime_type`."""
    from llm import GeminiAdapter

    GeminiAdapter().chat_turn(
        system_prompt="S", history=[], user_turn="hi",
        temperature=0.3, json_mode=False,
    )
    cfg = fake_sdk["config"]
    assert "response_mime_type" not in cfg
    assert cfg["temperature"] == 0.3


def test_single_shot_passes_token_budget(fake_sdk: dict) -> None:
    """Summary nodes cap tokens via NODE_SPEC — the adapter must forward it."""
    from llm import GeminiAdapter

    fake_sdk["reply"] = "narrative"
    out = GeminiAdapter().single_shot(
        "write a summary",
        temperature=0.2,
        max_output_tokens=600,
    )
    assert out == "narrative"
    cfg = fake_sdk["config"]
    assert cfg["temperature"] == 0.2
    assert cfg["max_output_tokens"] == 600
    # No system prompt was passed, so it must NOT be in the config.
    assert "system_instruction" not in cfg
    # Single-shot passes the raw prompt string as contents.
    assert fake_sdk["contents"] == "write a summary"


def test_single_shot_omits_optional_fields(fake_sdk: dict) -> None:
    """Both `system_prompt` and `max_output_tokens` are opt-in — default
    calls should not populate them."""
    from llm import GeminiAdapter

    GeminiAdapter().single_shot("p")
    cfg = fake_sdk["config"]
    assert "system_instruction" not in cfg
    assert "max_output_tokens" not in cfg


def test_api_key_pulled_from_configured_env(monkeypatch: pytest.MonkeyPatch, fake_sdk: dict) -> None:
    """Overriding `api_key_env` lets callers pick a different key per
    adapter (useful for dev/prod split without code changes)."""
    from llm import GeminiAdapter

    monkeypatch.setenv("CUSTOM_GEMINI_KEY", "prod-key")
    GeminiAdapter(api_key_env="CUSTOM_GEMINI_KEY").single_shot("p")
    assert fake_sdk["api_key"] == "prod-key"


def test_get_default_adapter_is_cached() -> None:
    """Process-wide singleton — repeated lookups return the same instance."""
    from llm import get_default_adapter

    a = get_default_adapter()
    b = get_default_adapter()
    assert a is b


def test_failover_to_second_api_key_on_timeout(
    monkeypatch: pytest.MonkeyPatch, fake_sdk: dict
) -> None:
    from llm import GeminiAdapter

    monkeypatch.setenv("GEMINI_API_KEY", "primary-key")
    monkeypatch.setenv("GEMINI_API_KEY_2", "backup-key")
    fake_sdk["fail_for_keys"] = ("primary-key",)

    from llm import get_default_adapter, reset_llm_runtime_for_tests

    reset_llm_runtime_for_tests()
    out = get_default_adapter().single_shot("hello")
    assert out == "ok"
    assert fake_sdk["keys_attempted"] == ["primary-key", "backup-key"]


def test_failover_rotates_through_three_keys_on_resource_exhausted(
    monkeypatch: pytest.MonkeyPatch, fake_sdk: dict
) -> None:
    from llm import GeminiAdapter

    class ResourceExhausted(Exception):
        pass

    monkeypatch.setenv("GEMINI_API_KEY", "key-1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "key-2")
    monkeypatch.setenv("GEMINI_API_KEY_3", "key-3")
    fake_sdk["fail_for_keys"] = ("key-1", "key-2")

    def _fail_exhausted(api_key: str) -> _FakeResponse:
        fake_sdk.setdefault("keys_attempted", []).append(api_key)
        if api_key in fake_sdk["fail_for_keys"]:
            raise ResourceExhausted("resource exhausted for quota")
        fake_sdk.setdefault("keys_used", []).append(api_key)
        return _FakeResponse(text="ok")

    fake_sdk["custom_generate"] = _fail_exhausted

    class _RotatingModels(_FakeModels):
        def generate_content(self, *, model: str, contents: Any, config: Any) -> _FakeResponse:
            return fake_sdk["custom_generate"](self._api_key)

    class _RotatingClient(_FakeClient):
        def __init__(self, *, api_key: str, recorder: dict) -> None:
            recorder["api_key"] = api_key
            self.models = _RotatingModels(recorder, api_key)

    import google.genai as genai_mod

    genai_mod.Client = lambda api_key: _RotatingClient(api_key=api_key, recorder=fake_sdk)

    from llm import get_default_adapter, reset_llm_runtime_for_tests

    reset_llm_runtime_for_tests()
    out = get_default_adapter().single_shot("hello")
    assert out == "ok"
    assert fake_sdk["keys_attempted"] == ["key-1", "key-2", "key-3"]
    assert fake_sdk["keys_used"] == ["key-3"]


def test_gemini_configured_when_only_secondary_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from llm import gemini_configured

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY_2", "backup-only")
    assert gemini_configured() is True


def test_sdk_client_reused_for_same_api_key(fake_sdk: dict) -> None:
    """One google.genai.Client per API key — not per request."""
    from llm import get_default_adapter, reset_llm_runtime_for_tests

    reset_llm_runtime_for_tests()
    ad = get_default_adapter()
    ad.single_shot("first")
    ad.single_shot("second")
    assert fake_sdk.get("client_construct_count") == 1


def test_probe_gemini_connection_mocked(fake_sdk: dict) -> None:
    from llm import probe_gemini_connection, reset_llm_runtime_for_tests

    reset_llm_runtime_for_tests()
    fake_sdk["reply"] = "ok"
    result = probe_gemini_connection()
    assert result.ok is True
    assert result.message == "ok"
    assert result.latency_ms is not None


def test_planner_uses_adapter(fake_sdk: dict) -> None:
    """End-to-end: Planner now routes through the adapter, so a single
    fake SDK covers every workflow-generation call site."""
    from generation.planner import Planner

    fake_sdk["reply"] = '{"workflow_id": "x", "nodes": [], "edges": []}'
    result = Planner().generate(
        system_prompt="S", history=[], user_turn="make one",
    )
    assert result.raw.startswith("{")
    assert result.workflow == {"workflow_id": "x", "nodes": [], "edges": []}
    # The planner must have used JSON mode (determinism guarantee).
    assert fake_sdk["config"]["response_mime_type"] == "application/json"
    assert fake_sdk["config"]["temperature"] == 0.0
