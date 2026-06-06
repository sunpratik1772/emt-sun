# Studio demo workflows

These files appear in the **Workflows** drawer (saved list). Open one and click **Run** — no CLI scripts required.

**Docs:** [docs/README.md](../../docs/README.md) (Starlark `code` node, node YAML/UI, MCP setup).

## Prerequisites

1. Start backend + frontend (Studio UI).
2. Set **`GEMINI_API_KEY`** in `backend/.env` (required for every workflow that uses **AI Agent** — real Gemini only, no stubs).
3. MCP workflows auto-start the bridge on port `8765` when the backend starts.

## Demos (approved palette nodes only)

| File | Flow |
|------|------|
| `studio_01_mcp_ticket_swarm.json` | MCP chain → Excel |
| `studio_02_revenue_ai_pipeline.json` | CSV → group → AI → evaluator → Excel |
| `studio_03_hot_cold_leads_branch.json` | CSV → condition branches → AI → CSV |
| `studio_04_product_360_join.json` | Two CSVs → join → Excel |
| `studio_05_web_github_mcp_briefing.json` | HTTP + MCP → merge → AI → CSV |
| `studio_06_transform_obstacle_course.json` | Transform pipeline → CSV |
| `studio_07_join_analyze_confluence.json` | Join → calculate → AI → Confluence (MCP) |
| `studio_08_starlark_margin_analysis.json` | Starlark transforms → margin analysis pack |
| `studio_09_trades_risk_mcp.json` | Trade risk screening → Confluence/Jira |
| `studio_10_leads_tier_mcp_publish.json` | Lead tiers → Confluence + Jira follow-ups |
| `studio_11_teams_risk_digest.json` | Trade digest → Teams/communications handoff |
| `studio_12_market_ticks_spread_monitor.json` | DB monitor (market_ticks) → condition → Confluence |
| `studio_13_confluence_actions_issue_pipeline.json` | Confluence action extraction → Jira backlog |
| `studio_14_alerts_ticks_join_publish.json` | hs_alerts + market_ticks join → Confluence + Jira + Excel |
| `studio_15_starlark_excel_colors_demo.json` | Trades + alerts join → Starlark row coloring → multi-tab Excel |
| `studio_16_hs_alerts_anomaly_report.json` | hs_alerts filter → evaluator → Starlark summary → condition → Confluence |
| `studio_17_github_activity_briefing.json` | github_mcp list_commits → Starlark briefing → Confluence |

Canonical demos live in **`backend/good_examples/studio_*.json`**. Authoring copies also exist under `workflows/demo_showcase/`. Sherpa harness blueprints and `/run` resolution check `good_examples/` first.

## Approved node types

`manual_trigger`, `csv_extract`, `db_query`, `join`, `map_transform`, `group_by`, `sort`, `filter`, `deduplicate`, `select_columns`, `condition`, `data_merge`, `code`, `http`, `agent`, `evaluator`, `mcp`, `teams`, `outlook`, `note`, `csv_output`, `excel_output`, and other entries in `engine/studio_nodes.py`.

Legacy n8n types are no longer supported at runtime.
