# Demo showcase (authoring)

**Studio users:** open workflows from the parent folder — `studio_01_*.json` … `studio_07_*.json`. See [STUDIO_DEMOS.md](../STUDIO_DEMOS.md).

## Run in Studio only

1. `GEMINI_API_KEY` in `backend/.env` (required for AI Agent nodes).
2. Open a `studio_*.json` workflow in the UI → **Run**.
3. MCP bridge starts with the backend automatically.

Do not rely on `scripts/run_demo_workflow.py` for demos (developer convenience only).

## Catalog

| Demo | Studio file | Highlights |
|------|-------------|------------|
| MCP ticket swarm | `studio_01_mcp_ticket_swarm.json` | 4× MCP → Excel |
| Revenue AI pipeline | `studio_02_revenue_ai_pipeline.json` | group_by + agent + evaluator |
| Hot vs cold leads | `studio_03_hot_cold_leads_branch.json` | condition + agent |
| Product 360 join | `studio_04_product_360_join.json` | dual csv_extract + join |
| Web + MCP briefing | `studio_05_web_github_mcp_briefing.json` | http + mcp + data_merge + agent |
| Transform obstacle course | `studio_06_transform_obstacle_course.json` | transform nodes |
| Join → AI → Confluence | `studio_07_join_analyze_confluence.json` | join + agent + MCP publish |

All demos use **Studio-approved nodes only** (`engine/studio_nodes.py`).
