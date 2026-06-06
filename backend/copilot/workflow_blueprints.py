"""Vetted workflow skeletons for common Sherpa build prompts."""
from __future__ import annotations

from engine.data_bundle_catalog import build_load_spec

# Domain glossary — surfaced in filter node labels / expressions.
LEADS_HIGH_RISK_EXPRESSION = "row.score >= 80"
LEADS_HIGH_RISK_LABEL = "High-risk leads (score >= 80)"


def build_leads_sort_csv_skeleton() -> dict:
    load = build_load_spec("leads.csv")
    return {
        "workflow_id": "blueprint-leads-sort-csv",
        "name": "Leads sorted by score",
        "description": "Load leads.csv, sort by score descending, export CSV.",
        "nodes": [
            {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
            {
                "id": "n02",
                "type": load.node_type,
                "label": "Load leads.csv",
                "config": load.config,
            },
            {
                "id": "n03",
                "type": "sort",
                "label": "Sort by score desc",
                "config": {"sortBy": "score", "order": "desc"},
            },
            {
                "id": "n04",
                "type": "csv_output",
                "label": "Export sorted leads",
                "config": {"filename": "leads_sorted_by_score.csv"},
            },
        ],
        "edges": [
            {"from": "n01", "to": "n02"},
            {"from": "n02", "to": "n03"},
            {"from": "n03", "to": "n04"},
        ],
    }


def build_leads_filter_csv_skeleton() -> dict:
    load = build_load_spec("leads.csv")
    return {
        "workflow_id": "blueprint-leads-filter-csv",
        "name": "High-risk leads export",
        "description": "Load leads.csv, filter high-risk rows (score >= 80), export CSV summary.",
        "nodes": [
            {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
            {
                "id": "n02",
                "type": load.node_type,
                "label": "Load leads.csv",
                "config": load.config,
            },
            {
                "id": "n03",
                "type": "filter",
                "label": LEADS_HIGH_RISK_LABEL,
                "config": {"expression": LEADS_HIGH_RISK_EXPRESSION},
            },
            {
                "id": "n04",
                "type": "csv_output",
                "label": "Export high-risk leads",
                "config": {"filename": "high_risk_leads.csv"},
            },
        ],
        "edges": [
            {"from": "n01", "to": "n02"},
            {"from": "n02", "to": "n03"},
            {"from": "n03", "to": "n04"},
        ],
    }
