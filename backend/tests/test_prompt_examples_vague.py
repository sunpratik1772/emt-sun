from copilot.prompt_examples import _is_vague_example_prompt


def test_rejects_generic_draft_suggestion():
    assert _is_vague_example_prompt(
        "Finish my draft workflow: connect the open nodes and add a CSV export at the end."
    )


def test_accepts_grounded_build_prompt():
    assert not _is_vague_example_prompt(
        'Load `leads.csv`, filter high-risk rows, and export a CSV summary.'
    )
