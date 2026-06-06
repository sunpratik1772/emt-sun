"""example-prompts must include dashboard_subline (dashboard + side panel share this route)."""


def test_example_prompts_includes_dashboard_subline(monkeypatch):
    from app.routers import copilot as copilot_router

    monkeypatch.setattr(
        'copilot.prompt_examples.generate_example_prompts',
        lambda: {'build_prompts': [{'text': 'Build x', 'tag': 'csv'}], 'ask_prompts': []},
    )
    monkeypatch.setattr(
        'copilot.dashboard_subline.generate_dashboard_subline',
        lambda **_: {'subline': 'What would you like to automate today?', 'from_ai': True},
    )

    out = copilot_router.example_prompts(first_name='John', period='morning')
    assert out['dashboard_subline'] == 'What would you like to automate today?'
    assert out['dashboard_subline_from_ai'] is True
    assert len(out['build_prompts']) == 1
