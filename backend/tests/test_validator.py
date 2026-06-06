"""
Validator tests — exercise the major error codes and the
schema_version gate. These are deterministic and do not call the LLM.
"""
from __future__ import annotations

from engine.validator import validate_dag


def _studio_stub(**extra) -> dict:
    """A single-node valid workflow stub."""
    return {
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "n01",
                "type": "manual_trigger",
                "label": "Start",
                "config": {},
            }
        ],
        "edges": [],
        **extra,
    }


class TestSchemaVersion:
    def test_current_version_passes(self):
        assert validate_dag(_studio_stub()).valid

    def test_legacy_file_without_version_defaults_ok(self):
        dag = _studio_stub()
        dag.pop("schema_version")
        assert validate_dag(dag).valid

    def test_future_version_blocked(self):
        dag = _studio_stub()
        dag["schema_version"] = "99.0"
        result = validate_dag(dag)
        assert not result.valid
        assert any(i.code == "SCHEMA_TOO_NEW" for i in result.errors)

    def test_garbage_version_blocked(self):
        dag = _studio_stub()
        dag["schema_version"] = "not-a-version"
        result = validate_dag(dag)
        assert not result.valid
        assert any(i.code == "BAD_SCHEMA_VERSION" for i in result.errors)


class TestStructural:
    def test_missing_nodes(self):
        result = validate_dag({"schema_version": "1.0"})
        assert not result.valid
        assert any(i.code == "MISSING_NODES" for i in result.errors)

    def test_empty_nodes(self):
        result = validate_dag({"schema_version": "1.0", "nodes": []})
        assert any(i.code == "EMPTY_WORKFLOW" for i in result.errors)

    def test_unknown_type(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [{"id": "n01", "type": "DOES_NOT_EXIST", "label": "x", "config": {}}],
            }
        )
        assert not result.valid
        assert any(i.code == "UNKNOWN_TYPE" for i in result.errors)

    def test_missing_label_is_warning(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [{"id": "n01", "type": "manual_trigger", "config": {}}],
            }
        )
        assert any(i.code == "MISSING_LABEL" and i.severity == "warning" for i in result.issues)

    def test_manual_trigger_is_not_orphan(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "n2",
                        "type": "csv_extract",
                        "label": "Trades",
                        "config": {"source": "transactions.csv"},
                    },
                ],
                "edges": [{"from": "n1", "to": "n2"}],
            }
        )
        assert not any(
            i.code == "ORPHAN_NODE" and i.node_id == "n1" for i in result.issues
        ), result.issues


class TestParams:
    def test_agent_per_row_defaults_when_enabled(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "n2",
                        "type": "csv_extract",
                        "label": "Data",
                        "config": {"source": "transactions.csv"},
                    },
                    {
                        "id": "n3",
                        "type": "agent",
                        "label": "Score",
                        "config": {
                            "prompt": "Analyst",
                            "task": "Score row",
                            "perRow": True,
                        },
                    },
                ],
                "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
            }
        )
        assert not any(
            i.code == "MISSING_REQUIRED_PARAM" and i.node_id == "n3" for i in result.errors
        ), result.errors

    def test_agent_aggregate_skips_per_row_fields(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "n3",
                        "type": "agent",
                        "label": "Summarize",
                        "config": {"prompt": "Analyst", "task": "Summarize"},
                    },
                ],
                "edges": [{"from": "n1", "to": "n3"}],
            }
        )
        assert not any(
            i.code == "MISSING_REQUIRED_PARAM"
            and i.node_id == "n3"
            and i.field in {"config.perRow", "config.outputColumn", "config.maxRows"}
            for i in result.errors
        ), result.errors

    def test_agent_row_dot_placeholder_warns(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "n3",
                        "type": "agent",
                        "label": "Poems",
                        "config": {
                            "prompt": "Write a poem",
                            "perRow": True,
                            "rowTemplate": "Company: {{row.company}}",
                            "outputColumn": "poem",
                        },
                    },
                ],
                "edges": [{"from": "n1", "to": "n3"}],
            }
        )
        assert result.valid
        assert any(
            i.node_id == "n3"
            and i.field == "config.rowTemplate"
            and i.severity == "warning"
            for i in result.warnings + result.errors
        )

    def test_missing_required_param(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "n02",
                        "type": "csv_extract",
                        "label": "Data",
                        "config": {},
                    },
                ],
                "edges": [{"from": "n01", "to": "n02"}],
            }
        )
        assert not result.valid
        assert any(
            i.code == "MISSING_REQUIRED_PARAM" and i.node_id == "n02" for i in result.errors
        )


class TestAcyclicity:
    def test_cycle_is_rejected(self):
        result = validate_dag(
            {
                "schema_version": "1.0",
                "nodes": [
                    {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
                    {
                        "id": "n02",
                        "type": "csv_extract",
                        "label": "Data",
                        "config": {"source": "transactions.csv"},
                    },
                ],
                "edges": [
                    {"from": "n01", "to": "n02"},
                    {"from": "n02", "to": "n01"},
                ],
            }
        )
        assert not result.valid
        assert any(i.code == "CYCLE" for i in result.errors)


class TestCodeNodeStarlarkGuardrails:
    def test_python_import_in_code_node_is_rejected(self):
        dag = {
            "schema_version": "1.0",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                {
                    "id": "n2",
                    "type": "code",
                    "label": "Transform",
                    "config": {
                        "code_summary": "attempted transform",
                        "code": "import json\noutput = []",
                    },
                },
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        }
        result = validate_dag(dag)
        assert not result.valid
        assert any(
            i.code == "BAD_PARAM_TYPE" and i.field == "config.code"
            for i in result.errors
        )

    def test_code_node_without_comments_adds_warning(self):
        dag = {
            "schema_version": "1.0",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                {
                    "id": "n2",
                    "type": "code",
                    "label": "Transform",
                    "config": {
                        "code_summary": "collect companies",
                        "code": 'output = [{"company": r.get("company", {}).get("name", "")} for r in input_data["rows"]]',
                    },
                },
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        }
        result = validate_dag(dag)
        assert any(
            i.code == "BAD_PARAM_TYPE"
            and i.severity == "warning"
            and i.field == "config.code"
            for i in result.warnings
        )

    def test_python_module_style_access_is_rejected(self):
        dag = {
            "schema_version": "1.0",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                {
                    "id": "n2",
                    "type": "code",
                    "label": "Transform",
                    "config": {
                        "code_summary": "parse json",
                        "code": 'output = [json.decode(r.get("payload", "{}")) for r in input_data["rows"]]',
                    },
                },
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        }
        result = validate_dag(dag)
        assert not result.valid
        assert any(
            i.code == "BAD_PARAM_TYPE" and i.field == "config.code"
            for i in result.errors
        )
