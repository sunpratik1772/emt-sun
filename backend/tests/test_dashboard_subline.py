from copilot.dashboard_subline import (
    FALLBACK_SUBLINES,
    GREETING_INSPIRATION_EXAMPLES,
    _coerce_subline,
    generate_dashboard_subline,
)


def test_greeting_inspiration_examples_are_four_workflow_lines():
    assert len(GREETING_INSPIRATION_EXAMPLES) == 4
    assert FALLBACK_SUBLINES == GREETING_INSPIRATION_EXAMPLES
    for line in GREETING_INSPIRATION_EXAMPLES:
        assert "node" not in line.lower()
        assert "sherpa" not in line.lower()


def test_coerce_subline_adds_question_mark():
    assert _coerce_subline('{"subline": "Ready to build a pipeline"}') == "Ready to build a pipeline?"


def test_coerce_subline_keeps_existing_punctuation():
    assert (
        _coerce_subline('{"subline": "What would you like to automate today?"}')
        == "What would you like to automate today?"
    )


def test_generate_dashboard_subline_fallback_without_gemini(monkeypatch):
    monkeypatch.setattr(
        "copilot.dashboard_subline._generate_with_gemini",
        lambda **_: None,
    )
    out = generate_dashboard_subline(first_name="John", period="morning")
    assert out["from_ai"] is False
    assert out["subline"] in FALLBACK_SUBLINES or out["subline"].startswith("John,")


def test_generate_dashboard_subline_uses_ai_when_available(monkeypatch):
    monkeypatch.setattr(
        'copilot.dashboard_subline._generate_with_gemini',
        lambda **_: "What workflow would you like to wire up today?",
    )
    out = generate_dashboard_subline(first_name="Jane", period="afternoon")
    assert out["from_ai"] is True
    assert "workflow" in out["subline"].lower()
