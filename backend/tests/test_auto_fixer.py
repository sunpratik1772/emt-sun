"""
AutoFixer tests — exercise each deterministic repair rule in isolation
and confirm idempotency. No LLM calls.
"""
from __future__ import annotations

from generation.repair.auto_fixer import AutoFixer


def _err(code: str, node_id: str | None = None, **extra) -> dict:
    return {"code": code, "node_id": node_id, "message": "", **extra}


class TestEdgeNormalisation:
    def test_source_target_becomes_from_to(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [{"id": "n01"}, {"id": "n02"}],
            "edges": [{"source": "n01", "target": "n02"}],
        }
        report = AutoFixer().fix(wf, [])
        assert report.changed
        assert wf["edges"] == [{"from": "n01", "to": "n02"}]

    def test_already_normalised_is_idempotent(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [{"id": "n01"}, {"id": "n02"}],
            "edges": [{"from": "n01", "to": "n02"}],
        }
        report = AutoFixer().fix(wf, [])
        assert not report.changed
        assert wf["edges"] == [{"from": "n01", "to": "n02"}]


class TestLabelFix:
    def test_missing_label_fills_from_type(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [{"id": "n01", "type": "manual_trigger", "config": {}}],
            "edges": [],
        }
        report = AutoFixer().fix(wf, [_err("MISSING_LABEL", node_id="n01", field="label")])
        assert report.changed
        assert wf["nodes"][0]["label"]


class TestConditionBranchFix:
    def test_bad_edge_source_handle_assigns_true_false(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [
                {"id": "n01", "type": "manual_trigger", "config": {}},
                {"id": "c1", "type": "condition", "config": {"expression": "row.score >= 80"},
                 "position": {"x": 0, "y": 200}},
                {"id": "n02", "type": "csv_output", "config": {"filename": "pass.csv"},
                 "position": {"x": 200, "y": 100}},
                {"id": "n03", "type": "csv_output", "config": {"filename": "fail.csv"},
                 "position": {"x": 200, "y": 300}},
            ],
            "edges": [
                {"from": "n01", "to": "c1"},
                {"from": "c1", "to": "n02"},
                {"from": "c1", "to": "n03"},
            ],
        }
        report = AutoFixer().fix(
            wf,
            [
                _err(
                    "BAD_EDGE",
                    message=(
                        "Condition node 'c1' has outgoing edges without sourceHandle. "
                        "Each edge from a condition must set sourceHandle: 'true' or 'false'."
                    ),
                )
            ],
        )
        assert report.changed
        handles = {e["to"]: e.get("sourceHandle") for e in wf["edges"] if e["from"] == "c1"}
        assert handles["n02"] == "true"
        assert handles["n03"] == "false"


class TestAgentRowTemplateFix:
    def test_normalizes_row_dot_placeholders(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [
                {
                    "id": "n3",
                    "type": "agent",
                    "label": "Poems",
                    "config": {
                        "prompt": "Write a poem for {{row.company}}",
                        "rowTemplate": "{{row.company}} in {{row.region}}",
                        "perRow": True,
                        "outputColumn": "poem",
                    },
                }
            ],
            "edges": [],
        }
        report = AutoFixer().fix(wf, [])
        assert report.changed
        cfg = wf["nodes"][0]["config"]
        assert cfg["prompt"] == "Write a poem for {{company}}"
        assert cfg["rowTemplate"] == "{{company}} in {{region}}"


class TestMcpParamTemplateFix:
    def test_normalizes_mcp_params(self):
        wf = {
            "schema_version": "1.0",
            "nodes": [
                {
                    "id": "n9",
                    "type": "mcp",
                    "label": "Jira",
                    "config": {
                        "tool": "jira_create_issue",
                        "params": {
                            "summary": "Poem for {{row.company}}",
                            "description": "{{row.poem}}",
                        },
                    },
                }
            ],
            "edges": [],
        }
        report = AutoFixer().fix(wf, [])
        assert report.changed
        params = wf["nodes"][0]["config"]["params"]
        assert params["summary"] == "Poem for {{company}}"
        assert params["description"] == "{{poem}}"


class TestAutoFixerIsSafe:
    def test_non_dict_workflow_returns_empty_report(self):
        report = AutoFixer().fix("not a dict", [_err("EDGE_SHAPE")])  # type: ignore[arg-type]
        assert not report.changed
        assert report.applied == []

    def test_unknown_error_code_is_ignored(self):
        wf = {"schema_version": "1.0", "nodes": [], "edges": []}
        report = AutoFixer().fix(wf, [_err("SOMETHING_BRAND_NEW")])
        assert not report.changed
