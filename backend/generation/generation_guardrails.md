Studio generation guardrails — keep graphs minimal, schema-valid, and executable.

1) Graph shape
- Every edge uses `{"from":"<id>","to":"<id>"}` (not `source`/`target` alone).
- Node ids: stable `n01`, `n02`, … in creation mode.
- Acyclic only; every non-trigger node must sit on a path to an output.
- Do **not** emit `note` nodes — put setup hints in node labels or workflow `description` instead. Notes disjoint the canvas and are not wired into the DAG.

2) Studio node types only
- Triggers: `manual_trigger`, `api_trigger`, `webhook_trigger`, `schedule`.
- Data: `csv_extract`, `db_query`, `pdf_extract`, `join`, `data_merge`.
- Transform: `filter`, `map_transform`, `group_by`, `sort`, `deduplicate`, `select_columns`, `code`.
- Logic: `condition`, `router`, `loop`, `evaluator`.
- Integrations: `http`, `jira_mcp`, `confluence_mcp`, `github_mcp`.
- AI: `agent` (Gemini).
- Output: `csv_output`, `excel_output`, `response`.
- Do not emit retired n8n/dbSherpa types (`SET`, `MERGE`, `LLM_BASIC`, `ALERT_TRIGGER`, …).
- Do not emit legacy combined `mcp`, `outlook`, or `teams` nodes (inactive / deprecated).

3) `code` node (Starlark)
- Assign to `output` (or `result`); read rows via `input_data["rows"]`.
- Sandbox globals are only `input_data`, `rows`, and `output`/`result` — **never** reference `workflow_run_id`, `run_id`, or other undeclared names.
- No imports, network, or filesystem access.
- Never emit Python syntax (`import`, `from ... import`, `try/except`, `class`).
- Include `code_summary` for non-technical readers.
- Include inline `#` comments in code so reviewers can follow each step.
- Reference: `backend/good_examples/studio_10_leads_tier_mcp_publish.json`, `studio_16_hs_alerts_anomaly_report.json`.

4) `evaluator`
- Config: `criteria` (row expression) and optional `label` (default `passed`).
- Passing rows get `_eval` set to the label; failing rows get `_eval: "failed"`.
- **Only rows that pass criteria are forwarded downstream** — do not expect failed rows or `_passed` in later nodes.
- Do not count pass/fail downstream unless you validate in `filter`/`code` instead. Use evaluator as a QA gate before export or publish.
- Reference: `backend/good_examples/studio_06_transform_obstacle_course.json`, `studio_16_hs_alerts_anomaly_report.json`.

5) `filter` / `condition` / `router`
- Use runtime condition objects with `leftValue`, `rightValue`, `operator.operation`.
- Prefer `condition` or `router` for branching; use `filter` for row subsets.

6) Artifacts
- CSV/Excel asks → end with `csv_output` or `excel_output` using concrete filenames.
- MCP/GitHub → use `jira_mcp`, `confluence_mcp`, or `github_mcp` with valid config keys from contracts.
- GitHub **repo activity** (commits, issues, PRs): use `github_mcp` with `tool: github_list_commits`, then `agent` (`emitPublishRow: true`) and `confluence_mcp` (`params: {}`). See `studio_17_github_activity_briefing.json`.
- Do **not** emit legacy `github` REST nodes or combined `mcp` nodes.
- Use `github_implement_fixes` / `github_fix_jira_and_update` only for Jira-linked PR automation — not activity summaries.

7) Data grounding
- Dataset ids and column names must come from the connectors catalog (`connectors/metadata/*.yaml`): e.g. `leads.csv`, `orders.csv`, `comms_messages`, `hs_alerts`.
- Load catalog data with `csv_extract` (inline CSV ids) or `db_query` (SQLite table ids). Use the metadata `id` as `source` / table reference — do not invent columns or retired n8n connector types.
- **hs_alerts** (demo SQLite): columns include `alert_id`, `trader_id`, `trader_name`, `keyword`, `alert_date`, `scenario`, `description`. Demo `scenario` values are `front_running_positive` and `front_running_negative` — do not invent labels like `Layering`, `Spoofing`, or `Front-Running`. Avoid hard-coded stale dates in SQL unless the user specifies one; prefer `LIMIT` or filter on `scenario`/`keyword`.
- Surveillance anomaly + Confluence pattern: `db_query` → `filter` → `evaluator` → Starlark `code` summary row → `condition` → `confluence_mcp` (`params: {}`) or `response`. See `studio_16_hs_alerts_anomaly_report.json`.

8) Agent node
- Set `prompt` and `task` for aggregate (one LLM call on all rows).
- For per-row enrichment (poem, opener, score, classify each row): set `perRow: true`,
  `outputColumn`, `maxRows`, and `rowTemplate` with flat placeholders — `{{company}}`,
  `{{region}}`, `{{score}}` — not `{{row.company}}` (MCP-style; auto-fixed if emitted).
- Example rowTemplate: `{{company}} in {{region}} scored {{score}} at stage {{stage}}`.
- Per-row mode sends `prompt`, `task`, and `rowTemplate` (each interpolated per row).

9) MCP nodes (`jira_mcp`, `confluence_mcp`, `github_mcp`)
- Set `tool` and optional `params` only — never emit credential fields (locked from backend/.env).
- Upstream rows pass automatically as `params.data`.
- String fields in `params` may use row templates: `{{company}}` or `{{row.company}}` (rendered per row at runtime).
- Jira `jira_create_issue` reads `summary` and `description`; aliases apply (`poem`→`description`, `company`→`summary`, `title`→`summary`).
- Example: `"params": {"project": "DEMO", "summary": "Poem for {{row.company}}", "description": "{{row.poem}}"}`.
