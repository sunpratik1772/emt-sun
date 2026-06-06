"""Tests for copilot thread context helpers."""
from __future__ import annotations

from copilot.thread_context import (
    append_thread_turn,
    format_thread_context,
    normalize_thread_messages,
    resolve_thread_history,
    thread_references_recent_workflow,
)


def test_normalize_thread_messages_filters_roles():
    raw = [
        {"role": "user", "content": "Build a pipeline"},
        {"role": "system", "content": "ignored"},
        {"role": "assistant", "content": "Done"},
    ]
    assert normalize_thread_messages(raw) == [
        {"role": "user", "content": "Build a pipeline"},
        {"role": "assistant", "content": "Done"},
    ]


def test_resolve_thread_history_prefers_client_payload():
    histories: dict[str, list[dict]] = {"s1": [{"role": "user", "content": "old"}]}
    resolved = resolve_thread_history(
        histories,
        "s1",
        thread_messages=[{"role": "user", "content": "new"}],
    )
    assert resolved == [{"role": "user", "content": "new"}]


def test_format_thread_context_truncates_long_turns():
    history = [{"role": "user", "content": "x" * 2000}]
    text = format_thread_context(history, per_message_chars=100)
    assert text.startswith("User:")
    assert text.endswith("…")


def test_append_thread_turn_records_exchange():
    histories: dict[str, list[dict]] = {}
    append_thread_turn(
        histories,
        "sess",
        user_message="Schedule it",
        assistant_message="Automation created.",
    )
    assert histories["sess"] == [
        {"role": "user", "content": "Schedule it"},
        {"role": "assistant", "content": "Automation created."},
    ]


def test_thread_references_recent_workflow():
    assert thread_references_recent_workflow("Sherpa: Built **Leads** (4 nodes)")
    assert not thread_references_recent_workflow("Sherpa: Here are your skills.")


def test_resolve_thread_prefers_client_when_footer_present() -> None:
    """Client UI thread with Next step wins over longer server summary without footer."""
    histories: dict[str, list[dict]] = {
        "s1": [
            {"role": "user", "content": "build"},
            {
                "role": "assistant",
                "content": "Built **Comms Messages High-Risk Summary** (4 nodes) on the canvas.",
            },
        ],
    }
    client = [
        {"role": "user", "content": "build"},
        {
            "role": "assistant",
            "content": (
                "Built **Comms Messages High-Risk Summary**.\n\n"
                "**Next step:** Run **Comms Messages High-Risk Summary** with sample data.\n\n"
                "Want me to start a sample run now?"
            ),
        },
    ]
    resolved = resolve_thread_history(histories, "s1", thread_messages=client)
    assert "Next step" in resolved[-1]["content"]
    assert "sample run" in resolved[-1]["content"].lower()
