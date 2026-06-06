"""Single application-wide Gemini / Vertex LLM gateway (google-genai SDK).

All LLM traffic must go through ``get_default_adapter()`` — do not construct
``GeminiAdapter()`` in application code (tests may use ``reset_llm_runtime_for_tests``).

API-key rotation and SDK client reuse live only in this module so a future switch
from ``GEMINI_API_KEY`` to Vertex AI credentials is a one-file change.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Iterator, TypeVar

DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_API_KEY_2_ENV = "GEMINI_API_KEY_2"
GEMINI_API_KEY_3_ENV = "GEMINI_API_KEY_3"
GEMINI_API_KEY_ENVS = (GEMINI_API_KEY_ENV, GEMINI_API_KEY_2_ENV, GEMINI_API_KEY_3_ENV)
LLM_PROVIDER_ENV = "LLM_PROVIDER"
VERTEX_PROJECT_ENV = "VERTEX_PROJECT"
VERTEX_LOCATION_ENV = "VERTEX_LOCATION"

logger = logging.getLogger(__name__)

_T = TypeVar("_T")

# Reused google.genai.Client per resolved API key (or Vertex singleton).
_CLIENT_CACHE: dict[str, Any] = {}

def llm_provider() -> str:
    """``gemini`` (API key) today; ``vertex`` when Vertex env is wired."""
    return (os.getenv(LLM_PROVIDER_ENV) or "gemini").strip().lower()


def _sdk():
    # Lazy import — adapter module load must not require google-genai installed.
    from google import genai
    from google.genai import types

    return genai, types


def _create_sdk_client(*, api_key: str) -> Any:
    """Central factory for SDK clients (API key now, Vertex project/location later)."""
    genai, _ = _sdk()
    provider = llm_provider()
    if provider == "vertex":
        project = (os.getenv(VERTEX_PROJECT_ENV) or "").strip()
        location = (os.getenv(VERTEX_LOCATION_ENV) or "us-central1").strip()
        if not project:
            raise RuntimeError(
                f"LLM_PROVIDER=vertex requires {VERTEX_PROJECT_ENV} in backend/.env"
            )
        return genai.Client(vertexai=True, project=project, location=location)
    return genai.Client(api_key=api_key)


def _client_cache_key(api_key: str) -> str:
    if llm_provider() == "vertex":
        project = (os.getenv(VERTEX_PROJECT_ENV) or "").strip()
        location = (os.getenv(VERTEX_LOCATION_ENV) or "us-central1").strip()
        return f"vertex:{project}:{location}"
    return f"api_key:{api_key}"


def _get_client(api_key: str) -> Any:
    """Return a cached SDK client for this credential (one client per key / Vertex config)."""
    key = _client_cache_key(api_key)
    if key not in _CLIENT_CACHE:
        _CLIENT_CACHE[key] = _create_sdk_client(api_key=api_key)
        logger.debug("Created Gemini SDK client (%s)", key.split(":")[0])
    return _CLIENT_CACHE[key]


def reset_llm_runtime_for_tests() -> None:
    """Clear process singleton and SDK client cache (unit tests only)."""
    _CLIENT_CACHE.clear()
    get_default_adapter.cache_clear()


def _status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "code", "status"):
        raw = getattr(exc, attr, None)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _should_failover_to_next_key(exc: BaseException, *, more_keys: bool) -> bool:
    """True when trying another configured API key may help."""
    if llm_provider() == "vertex":
        return False
    if not more_keys:
        return False
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    status = _status_code(exc)
    if status is not None:
        return status in (401, 403, 408, 429, 500, 502, 503, 504)
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "timeout",
            "timed out",
            "deadline",
            "rate limit",
            "quota",
            "resource exhausted",
            "too many requests",
            "unavailable",
            "connection",
            "503",
            "502",
            "500",
            "429",
        )
    )


@dataclass(frozen=True)
class GeminiConnectivityResult:
    ok: bool
    provider: str
    model: str
    message: str
    latency_ms: float | None = None


@dataclass(frozen=True)
class GeminiAdapter:
    default_model: str = DEFAULT_MODEL
    api_key_env: str = GEMINI_API_KEY_ENV
    fallback_env_keys: tuple[str, ...] = field(default=())

    def chat_turn(
        self,
        *,
        system_prompt: str,
        history: list[dict],
        user_turn: str,
        model: str | None = None,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> str:
        _, types = _sdk()

        contents = []
        for msg in history:
            role = "model" if msg.get("role") == "assistant" else "user"
            text = str(msg.get("content") or "")
            contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_turn)]))

        cfg: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": float(temperature),
        }
        if json_mode:
            cfg["response_mime_type"] = "application/json"

        def _call(api_key: str) -> str:
            client = _get_client(api_key)
            response = client.models.generate_content(
                model=model or self.default_model,
                contents=contents,
                config=types.GenerateContentConfig(**cfg),
            )
            return getattr(response, "text", "") or ""

        return self._with_api_key_failover(_call)

    def chat_turn_stream(
        self,
        *,
        system_prompt: str,
        history: list[dict],
        user_turn: str,
        model: str | None = None,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> Iterator[str]:
        _, types = _sdk()

        contents = []
        for msg in history:
            role = "model" if msg.get("role") == "assistant" else "user"
            text = str(msg.get("content") or "")
            contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_turn)]))

        cfg: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": float(temperature),
        }
        if json_mode:
            cfg["response_mime_type"] = "application/json"

        def _open_stream(api_key: str):
            client = _get_client(api_key)
            return client.models.generate_content_stream(
                model=model or self.default_model,
                contents=contents,
                config=types.GenerateContentConfig(**cfg),
            )

        keys = self._api_keys()
        if not keys:
            raise RuntimeError(_missing_api_key_message())

        last_exc: BaseException | None = None
        for index, api_key in enumerate(keys):
            more_keys = index + 1 < len(keys)
            try:
                stream = _open_stream(api_key)
            except Exception as exc:
                last_exc = exc
                if _should_failover_to_next_key(exc, more_keys=more_keys):
                    logger.warning(
                        "Gemini stream open failed with key #%s; trying next key: %s",
                        index + 1,
                        exc,
                    )
                    continue
                raise

            yielded = False
            try:
                for chunk in stream:
                    text = getattr(chunk, "text", "") or ""
                    if text:
                        yielded = True
                        yield text
                return
            except Exception as exc:
                last_exc = exc
                if yielded or not _should_failover_to_next_key(exc, more_keys=more_keys):
                    raise
                logger.warning(
                    "Gemini stream failed with key #%s before completion; trying next key: %s",
                    index + 1,
                    exc,
                )

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Gemini stream failed with no API keys configured")

    def single_shot(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        system_prompt: str | None = None,
    ) -> str:
        _, types = _sdk()

        cfg: dict[str, Any] = {"temperature": float(temperature)}
        if system_prompt:
            cfg["system_instruction"] = system_prompt
        if max_output_tokens is not None:
            cfg["max_output_tokens"] = int(max_output_tokens)

        def _call(api_key: str) -> str:
            client = _get_client(api_key)
            response = client.models.generate_content(
                model=model or self.default_model,
                contents=prompt,
                config=types.GenerateContentConfig(**cfg),
            )
            return getattr(response, "text", "") or ""

        return self._with_api_key_failover(_call)

    def _api_keys(self) -> tuple[str, ...]:
        """Primary + backup keys (ENV1→ENV2→ENV3), then legacy fallbacks (deduped)."""
        if llm_provider() == "vertex":
            primary = self._resolve_key()
            return (primary,) if primary else ("vertex",)
        ordered_envs = (
            self.api_key_env,
            GEMINI_API_KEY_2_ENV,
            GEMINI_API_KEY_3_ENV,
            *self.fallback_env_keys,
        )
        seen: set[str] = set()
        keys: list[str] = []
        for env in ordered_envs:
            value = os.environ.get(env, "").strip()
            if value and value not in seen:
                seen.add(value)
                keys.append(value)
        return tuple(keys)

    def _resolve_key(self) -> str:
        if llm_provider() == "vertex":
            return "vertex"
        keys = self._api_keys()
        return keys[0] if keys else ""

    def _with_api_key_failover(self, fn: Callable[[str], _T]) -> _T:
        keys = self._api_keys()
        if not keys:
            raise RuntimeError(_missing_api_key_message())

        last_exc: BaseException | None = None
        for index, api_key in enumerate(keys):
            more_keys = index + 1 < len(keys)
            try:
                return fn(api_key)
            except Exception as exc:
                last_exc = exc
                if _should_failover_to_next_key(exc, more_keys=more_keys):
                    logger.warning(
                        "Gemini call failed with key #%s; trying next key: %s",
                        index + 1,
                        exc,
                    )
                    continue
                raise

        assert last_exc is not None
        raise last_exc


def _missing_api_key_message() -> str:
    if llm_provider() == "vertex":
        return f"Set {VERTEX_PROJECT_ENV} (and optional {VERTEX_LOCATION_ENV}) for Vertex, or switch LLM_PROVIDER=gemini"
    env_list = ", ".join(GEMINI_API_KEY_ENVS)
    return f"Set at least one Gemini API key in backend/.env ({env_list}, or GOOGLE_API_KEY)"


@lru_cache(maxsize=1)
def get_default_adapter() -> GeminiAdapter:
    """Process-wide singleton adapter — the only Gemini instance for the backend."""
    adapter = GeminiAdapter(fallback_env_keys=("GOOGLE_API_KEY",))
    logger.info(
        "LLM adapter ready (provider=%s, model=%s)",
        llm_provider(),
        adapter.default_model,
    )
    return adapter


def gemini_api_key() -> str:
    """Resolve the primary Gemini API key (first configured in priority order)."""
    return get_default_adapter()._resolve_key()


def gemini_configured() -> bool:
    """True when LLM credentials are available (API key or Vertex project)."""
    if llm_provider() == "vertex":
        return bool((os.getenv(VERTEX_PROJECT_ENV) or "").strip())
    return bool(get_default_adapter()._api_keys())


def probe_gemini_connection(
    *,
    adapter: GeminiAdapter | None = None,
    model: str | None = None,
) -> GeminiConnectivityResult:
    """Hello-world connectivity check using the shared adapter (no extra SDK clients)."""
    ad = adapter or get_default_adapter()
    provider = llm_provider()
    target_model = model or ad.default_model

    if not gemini_configured():
        return GeminiConnectivityResult(
            ok=False,
            provider=provider,
            model=target_model,
            message=_missing_api_key_message(),
        )

    started = time.perf_counter()
    try:
        text = ad.single_shot(
            "Reply with exactly: ok",
            model=target_model,
            temperature=0.0,
            max_output_tokens=16,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        snippet = (text or "").strip()[:80]
        ok = bool(snippet)
        return GeminiConnectivityResult(
            ok=ok,
            provider=provider,
            model=target_model,
            message=snippet or "(empty response)",
            latency_ms=round(latency_ms, 1),
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return GeminiConnectivityResult(
            ok=False,
            provider=provider,
            model=target_model,
            message=str(exc)[:500],
            latency_ms=round(latency_ms, 1),
        )
