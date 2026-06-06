# Skill: Studio Workflow Builder

Use this skill on every Copilot generation or edit request. Guardrails: `backend/generation/generation_guardrails.md`. Dataset ids: `backend/connectors/metadata/*.yaml`.

## Core rule

Build with **Studio palette nodes only** (`manual_trigger`, `csv_extract`, `filter`, `join`, `agent`, `mcp`, `csv_output`, …). Do not emit retired n8n/dbSherpa types.

## Preferred patterns

### ETL + report
```text
manual_trigger → csv_extract → map_transform/filter → group_by → sort → csv_output | excel_output
```

### Branching
```text
manual_trigger → csv_extract → condition | router → branch outputs (csv_output per branch)
```

### AI summary
```text
manual_trigger → csv_extract → agent → evaluator (optional) → excel_output
```

### MCP publish chain
```text
manual_trigger → mcp (atlassian) → mcp (github) → csv_output
```

### Surveillance anomaly report (hs_alerts)
```text
manual_trigger → db_query (hs_alerts) → filter (scenario) → evaluator → code (Starlark summary row)
  → condition → confluence_mcp | response
```
Parallel export: wire evaluator → csv_output. Reference: `studio_16_hs_alerts_anomaly_report.json`.
Demo scenarios: `front_running_positive`, `front_running_negative`.

### HTTP + merge
```text
manual_trigger → http → code → data_merge → agent → csv_output
```

## Node selection

| Need | Node |
|------|------|
| Start run | `manual_trigger` |
| Load CSV fixture | `csv_extract` (`source` = catalog id, e.g. `leads.csv`) |
| SQL over demo DB | `db_query` (SQLite tables from connectors catalog) |
| Row filter | `filter` |
| Join datasets | `join` |
| Concat streams | `data_merge` |
| Group/aggregate | `group_by` |
| Starlark script | `code` (globals: `input_data`, `rows`, `output` only — no `workflow_run_id`) |
| QA gate | `evaluator` (forwards passed rows only; sets `_eval`, not `_passed`) |
| If/else branch | `condition` |
| Multi-route | `router` |
| LLM step | `agent` |
| Per-row LLM (poem, opener, score) | `agent` with `perRow: true`, `rowTemplate: "{{company}} in {{region}}..."`, `outputColumn`, `maxRows` |
| Confluence/Jira/GitHub | `jira_mcp`, `confluence_mcp`, `github_mcp` |
| GitHub REST (legacy) | `github` — hidden from palette; use `github_mcp` instead |
| Export CSV | `csv_output` |
| Export Excel | `excel_output` |

## Editing mode

- Preserve existing node ids and labels when fixing errors.
- Make the smallest change that satisfies the user request.

## Validation

- Every `type` must exist in Node I/O Contracts.
- Required config params must be present.
- Edges must reference valid node ids.
