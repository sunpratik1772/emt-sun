"""Multi-question / multi-select clarification."""
from __future__ import annotations

from copilot.intent_clarification import (
    _parse_clarification_questions,
    _workflow_not_found_questions,
    normalize_clarification_options,
    resolve_clarification_answers,
    ClarificationOption,
)


def test_normalize_always_ends_with_something_else() -> None:
    opts = normalize_clarification_options(
        [
            ClarificationOption("a", "Create", "Build new"),
            ClarificationOption("other", "Other", "legacy"),
        ],
        kind="choice",
    )
    assert opts[-1].id == "other"
    assert opts[-1].label == "Something else"
    assert sum(1 for o in opts if o.id == "other") == 1


def test_workflow_not_found_question_allows_multi_select() -> None:
    qs = _workflow_not_found_questions("tes Excel Report")
    assert len(qs) == 1
    assert qs[0].allow_multiple is True
    assert qs[0].options[-1].label == "Something else"


def test_parse_multi_question_llm_json() -> None:
    parsed = {
        "needs_clarification": True,
        "questions": [
            {
                "id": "q1",
                "kind": "choice",
                "allow_multiple": True,
                "question": "What should we do?",
                "options": [{"id": "a", "label": "Create", "description": "New wf"}],
                "default_option_id": "a",
            },
            {
                "id": "q2",
                "kind": "confirm",
                "question": "Proceed?",
                "options": [
                    {"id": "yes", "label": "Yes", "description": ""},
                    {"id": "no", "label": "No", "description": ""},
                ],
            },
        ],
    }
    qs = _parse_clarification_questions(parsed)
    assert len(qs) == 2
    assert qs[0].allow_multiple is True
    assert qs[1].kind == "confirm"
    assert qs[1].options[-1].id == "other"


def test_resolve_batch_create_goes_to_plan_phase() -> None:
    pending = {
        "intent": "explain_run",
        "metadata": {"workflow_name": "tes Excel Report"},
        "enhanced_question": "Review run",
        "source": "llm",
    }
    out = resolve_clarification_answers(
        answers=[
            {
                "question": "Workflow not found",
                "kind": "choice",
                "selection_ids": ["b"],
                "selection_labels": ["Create a new workflow"],
                "other_text": None,
            },
        ],
        pending_route=pending,
        message="Review the latest run of 'tes Excel Report'",
    )
    assert out["intent"] == "ask"
    assert out["metadata"].get("propose_build_plan") is True
    assert out["source"] == "clarification_create_plan"
