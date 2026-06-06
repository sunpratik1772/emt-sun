# Node Detail

Generated from the live backend `NodeSpec` registry (`engine.registry.studio_manifest`).
This file documents every node: what it does, inputs, outputs, static UI metadata, and config parameters.

## Node Index

| Node | Display | Section | Use |
| --- | --- | --- | --- |
| `agent` | AI Agent | `ai` | Call Gemini with rows + prompt (requires GEMINI_API_KEY in backend/.env). |
| `api_trigger` | API Trigger | `triggers` | Trigger via HTTP webhook (returns the request payload). |
| `code` | Transform (Starlark) | `logic` | Run sandboxed Starlark on the incoming rows. Assign the transformed table to `output` (preferred) or `result`. No imports, while loops, or filesystem/network access — safe for AI-generated logic. |
| `condition` | Condition | `logic` | Branch rows into true / false outputs by an expression. |
| `confluence_mcp` | Confluence MCP | `integrations` | Call Confluence MCP bridge tools — search pages, extract action items, publish reports. |
| `csv_extract` | Data Extract | `data` | Load rows from an Oracle-backed dataset (alias for table extract). |
| `csv_output` | CSV Output | `transform` | Serialize rows to a CSV string. |
| `data_merge` | Merge | `transform` | Concatenate or union multiple datasets. |
| `db_query` | DB Query | `data` | Run a SELECT against an Oracle-backed dataset. |
| `deduplicate` | Deduplicate | `transform` | Remove duplicate rows by a key column. |
| `evaluator` | Evaluator | `ai` | Evaluate rows against criteria; reports pass / fail rate. |
| `excel_output` | Excel Export | `output` | Write multi-tab Excel from each upstream dataset. |
| `filter` | Filter | `transform` | Filter rows by an expression (row.column accessible). |
| `function` | Function | `logic` | Run Python code with access to input and previous output. |
| `github` | GitHub | `integrations` | GitHub API actions. Requires GITHUB_TOKEN and GITHUB_REPO (or config.repo). |
| `github_mcp` | GitHub MCP | `integrations` | Call GitHub MCP bridge tools — implement fixes, open PRs linked to Jira issues. |
| `group_by` | Group By | `transform` | Aggregate rows by a column. |
| `http` | HTTP Request | `data` | Fetch data from any HTTP URL. |
| `jira_mcp` | Jira MCP | `integrations` | Call Jira MCP bridge tools — create issues, list tickets, epics from Confluence. |
| `join` | Join | `transform` | Join two upstream datasets on key columns. |
| `loop` | Loop | `logic` | Iterate over rows (pass-through; surfaces iteration metadata). |
| `manual_trigger` | Manual Trigger | `triggers` | Start workflow manually. |
| `map_transform` | Map / Transform | `transform` | Rename columns or compute new ones from row expressions. |
| `note` | Note | `output` | Canvas comment / annotation. Pass-through with text. |
| `pause` | Pause | `logic` | Wait for a number of milliseconds before continuing. |
| `pdf_extract` | PDF Extract | `data` | Extract text from a PDF (mock content by default). |
| `response` | Response | `output` | Return a final workflow response. |
| `router` | Router | `logic` | Route rows to labelled branches by an expression returning a label. |
| `schedule` | Schedule | `triggers` | Run on a cron schedule. |
| `select_columns` | Select Columns | `transform` | Pick a specific subset of columns. |
| `sort` | Sort | `transform` | Sort rows by a column. |
| `webhook_trigger` | Webhook | `triggers` | Listen for incoming webhooks. |

## `agent` — AI Agent

**Use:** Call Gemini with rows + prompt (requires GEMINI_API_KEY in backend/.env).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `agent` |
| Display name | AI Agent |
| UI section | `ai` |
| Palette order | `0` |
| Color | `#8b5cf6` |
| Icon | `Bot` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `response` | `text` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `prompt` | `string` | no | `textarea` |  |  |  |
| `task` | `string` | no | `textarea` |  |  |  |
| `perRow` | `boolean` | no | `switch` | `False` |  |  |
| `rowTemplate` | `string` | no | `textarea` |  |  |  |
| `outputColumn` | `string` | no | `text` | `_ai_response` |  |  |
| `maxRows` | `number` | no | `number` | `5` |  | Cap rows for per-row AI calls. Keep low (≤10) for snappy demos. |
| `model` | `string` | no | `text` | `gemini-2.5-flash` |  |  |
| `emitPublishRow` | `boolean` | no | `switch` | `False` |  | Replace output rows with one Confluence-ready {title, body_markdown} row. |
| `pageTitle` | `string` | no | `text` |  |  |  |

## `api_trigger` — API Trigger

**Use:** Trigger via HTTP webhook (returns the request payload).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `api_trigger` |
| Display name | API Trigger |
| UI section | `triggers` |
| Palette order | `0` |
| Color | `#7c3aed` |
| Icon | `Webhook` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `payload` | `object` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `path` | `string` | no | `text` | `/webhook` |  | Webhook path |

## `code` — Transform (Starlark)

**Use:** Run sandboxed Starlark on the incoming rows. Assign the transformed table to `output` (preferred) or `result`. No imports, while loops, or filesystem/network access — safe for AI-generated logic.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `code` |
| Display name | Transform (Starlark) |
| UI section | `logic` |
| Palette order | `0` |
| Color | `#06b6d4` |
| Icon | `Code2` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes | Table rows from the upstream node. |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` | Transformed rows produced by your Starlark script. |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `code_summary` | `string` | no | `textarea` |  |  | Plain-language explanation of what the Starlark script does (for non-technical readers). Usually filled by the AI when code is generated. |
| `code` | `code` | yes | `starlark` |  |  |  |

**Constraints**

- Do not use import, while, or recursion in Starlark.
- Prefer assigning `output`; `result` is accepted for older workflows.
- Upstream rows are available as `input_data["rows"]` and as `rows`.

## `condition` — Condition

**Use:** Branch rows into true / false outputs by an expression.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `condition` |
| Display name | Condition |
| UI section | `logic` |
| Palette order | `0` |
| Color | `#06b6d4` |
| Icon | `GitBranch` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `true_branch` | `dataframe` | no | `` |  |  |
| `false_branch` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `expression` | `expression` | yes | `code` |  |  |  |

## `confluence_mcp` — Confluence MCP

**Use:** Call Confluence MCP bridge tools — search pages, extract action items, publish reports.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `confluence_mcp` |
| Display name | Confluence MCP |
| UI section | `integrations` |
| Palette order | `11` |
| Color | `#172B4D` |
| Icon | `ScrollText` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `serverUrl` | `string` | no | `text` |  |  | Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL). |
| `confluenceSiteUrl` | `string` | no | `locked_env` |  |  | Confluence site URL (from backend/.env — locked). |
| `confluenceEmail` | `string` | no | `locked_env` |  |  | Confluence account email (from backend/.env — locked). |
| `confluenceApiToken` | `string` | no | `locked_env` |  |  | Confluence API token (from backend/.env — locked). |
| `confluenceSpaceKey` | `string` | no | `locked_env` |  |  | Confluence space key (from backend/.env — locked). |
| `pageTitle` | `string` | no | `text` |  |  | Confluence page title override (defaults to generated name). |
| `tool` | `enum` | yes | `select` | `confluence_publish_report` | `confluence_search_pages`, `confluence_extract_action_items`, `confluence_publish_report`, `studio_publish_architecture_doc` | Confluence MCP tool to invoke. |
| `params` | `json` | no | `json` |  |  | Tool arguments (JSON). Upstream rows are passed as params.data automatically. |

## `csv_extract` — Data Extract

**Use:** Load rows from an Oracle-backed dataset (alias for table extract).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `csv_extract` |
| Display name | Data Extract |
| UI section | `data` |
| Palette order | `0` |
| Color | `#0ea5e9` |
| Icon | `Table2` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `datasets.<source>` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `enum` | yes | `select` |  | `leads.csv`, `products.csv`, `orders.csv`, `hs_trades`, `hs_alerts`, `hs_orders`, `hs_exec`, `market_ticks`, `comms_messages` | Dataset id |
| `limit` | `number` | no | `number` |  |  | Row limit (optional) |

## `csv_output` — CSV Output

**Use:** Serialize rows to a CSV string.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `csv_output` |
| Display name | CSV Output |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `Download` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `csv` | `text` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `filename` | `string` | yes | `text` | `output.csv` |  |  |

## `data_merge` — Merge

**Use:** Concatenate or union multiple datasets.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `data_merge` |
| Display name | Merge |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `Layers` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `strategy` | `enum` | yes | `select` | `concat` | `concat`, `union` |  |

## `db_query` — DB Query

**Use:** Run a SELECT against an Oracle-backed dataset.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `db_query` |
| Display name | DB Query |
| UI section | `data` |
| Palette order | `0` |
| Color | `#0ea5e9` |
| Icon | `Database` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `query` | `string` | yes | `textarea` |  |  | SELECT * FROM comms_messages LIMIT 20 |
| `source` | `enum` | no | `select` |  | `leads.csv`, `products.csv`, `orders.csv`, `hs_trades`, `hs_alerts`, `hs_orders`, `hs_exec`, `market_ticks`, `comms_messages` | Source dataset |

## `deduplicate` — Deduplicate

**Use:** Remove duplicate rows by a key column.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `deduplicate` |
| Display name | Deduplicate |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `Copy` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `key` | `string` | yes | `text` |  |  |  |

## `evaluator` — Evaluator

**Use:** Evaluate rows against criteria; reports pass / fail rate.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `evaluator` |
| Display name | Evaluator |
| UI section | `ai` |
| Palette order | `0` |
| Color | `#8b5cf6` |
| Icon | `CheckSquare` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `criteria` | `expression` | yes | `code` |  |  |  |
| `label` | `string` | yes | `text` | `passed` |  |  |

## `excel_output` — Excel Export

**Use:** Write multi-tab Excel from each upstream dataset.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `excel_output` |
| Display name | Excel Export |
| UI section | `output` |
| Palette order | `0` |
| Color | `#16a34a` |
| Icon | `FileSpreadsheet` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `file` | `object` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `filename` | `string` | yes | `text` | `output.xlsx` |  |  |
| `tabNames` | `string` | no | `text` |  |  |  |
| `highlightColumn` | `string` | no | `text` |  |  |  |
| `highlightMapping` | `string` | no | `text` |  |  |  |

## `filter` — Filter

**Use:** Filter rows by an expression (row.column accessible).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `filter` |
| Display name | Filter |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `Filter` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `expression` | `expression` | yes | `code` |  |  |  |

## `function` — Function

**Use:** Run Python code with access to input and previous output.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `function` |
| Display name | Function |
| UI section | `logic` |
| Palette order | `0` |
| Color | `#06b6d4` |
| Icon | `FunctionSquare` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `any` | `any` | no |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `any` | `any` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `code` | `code` | yes | `code` |  |  |  |

## `github` — GitHub

**Use:** GitHub API actions. Requires GITHUB_TOKEN and GITHUB_REPO (or config.repo).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `github` |
| Display name | GitHub |
| UI section | `integrations` |
| Palette order | `0` |
| Color | `#24292e` |
| Icon | `Github` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `action` | `enum` | yes | `select` | `list-repos` | `list-repos`, `list-issues`, `list-prs`, `list-commits`, `get-repo`, `create-issue`, `push-file` |  |
| `repo` | `string` | yes | `text` |  |  |  |
| `state` | `enum` | yes | `select` | `open` | `open`, `closed`, `all` |  |
| `title` | `string` | yes | `text` |  |  |  |
| `body` | `string` | yes | `textarea` |  |  |  |
| `labels` | `string` | yes | `text` |  |  |  |
| `filePath` | `string` | yes | `text` |  |  |  |
| `fileContent` | `string` | yes | `textarea` |  |  |  |
| `fileFormat` | `enum` | yes | `select` | `json` | `json`, `csv` |  |
| `branch` | `string` | yes | `text` | `main` |  |  |
| `commitMessage` | `string` | yes | `text` |  |  |  |

## `github_mcp` — GitHub MCP

**Use:** Call GitHub MCP bridge tools — implement fixes, open PRs linked to Jira issues.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `github_mcp` |
| Display name | GitHub MCP |
| UI section | `integrations` |
| Palette order | `12` |
| Color | `#24292F` |
| Icon | `GitPullRequest` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `serverUrl` | `string` | no | `text` |  |  | Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL). |
| `githubToken` | `string` | no | `locked_env` |  |  | GitHub PAT (from backend/.env — locked). |
| `githubRepo` | `string` | no | `locked_env` |  |  | Target repository (from backend/.env — locked). |
| `tool` | `enum` | yes | `select` | `github_implement_fixes` | `github_implement_fixes`, `github_fix_jira_and_update` | GitHub MCP tool to invoke. |
| `params` | `json` | no | `json` |  |  | Tool arguments (JSON). Upstream rows are passed as params.data automatically. |

## `group_by` — Group By

**Use:** Aggregate rows by a column.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `group_by` |
| Display name | Group By |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `BarChart3` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `groupBy` | `string` | yes | `text` |  |  |  |
| `aggregateCol` | `string` | yes | `text` |  |  |  |
| `aggregateFn` | `enum` | yes | `select` | `sum` | `sum`, `avg`, `min`, `max`, `count` |  |
| `alias` | `string` | no | `text` |  |  |  |

## `http` — HTTP Request

**Use:** Fetch data from any HTTP URL.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `http` |
| Display name | HTTP Request |
| UI section | `data` |
| Palette order | `0` |
| Color | `#0ea5e9` |
| Icon | `Globe` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `url` | `string` | yes | `text` |  |  |  |
| `method` | `enum` | yes | `select` | `GET` | `GET`, `POST`, `PUT`, `DELETE`, `PATCH` |  |
| `headers` | `json` | no | `json` |  |  |  |
| `body` | `string` | no | `textarea` |  |  |  |

## `jira_mcp` — Jira MCP

**Use:** Call Jira MCP bridge tools — create issues, list tickets, epics from Confluence.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `jira_mcp` |
| Display name | Jira MCP |
| UI section | `integrations` |
| Palette order | `10` |
| Color | `#0052CC` |
| Icon | `Ticket` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `serverUrl` | `string` | no | `text` |  |  | Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL). |
| `jiraSiteUrl` | `string` | no | `locked_env` |  |  | Jira site URL (from backend/.env — locked). |
| `jiraEmail` | `string` | no | `locked_env` |  |  | Jira account email (from backend/.env — locked). |
| `jiraApiToken` | `string` | no | `locked_env` |  |  | Jira API token (from backend/.env — locked). |
| `jiraProjectKey` | `string` | no | `locked_env` |  |  | Jira project key (from backend/.env — locked). |
| `tool` | `enum` | yes | `select` | `jira_create_issue` | `jira_create_issue`, `jira_list_issues`, `jira_create_epics_from_confluence`, `tasks_bulk_create` | Jira MCP tool to invoke. |
| `params` | `json` | no | `json` |  |  | Tool arguments (JSON). Upstream rows are passed as params.data automatically. |

## `join` — Join

**Use:** Join two upstream datasets on key columns.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `join` |
| Display name | Join |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `Merge` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `left` | `dataframe` | yes |  |  |
| `right` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `leftKey` | `string` | yes | `text` |  |  |  |
| `rightKey` | `string` | yes | `text` |  |  |  |
| `joinType` | `enum` | yes | `select` | `inner` | `inner`, `left`, `right`, `outer` |  |

## `loop` — Loop

**Use:** Iterate over rows (pass-through; surfaces iteration metadata).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `loop` |
| Display name | Loop |
| UI section | `logic` |
| Palette order | `0` |
| Color | `#06b6d4` |
| Icon | `RefreshCw` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `maxIterations` | `number` | yes | `number` | `1000` |  |  |

## `manual_trigger` — Manual Trigger

**Use:** Start workflow manually.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `manual_trigger` |
| Display name | Manual Trigger |
| UI section | `triggers` |
| Palette order | `0` |
| Color | `#7c3aed` |
| Icon | `Play` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `payload` | `object` | no | `alert_payload` |  |  |

**Config parameters**

No config parameters.

## `map_transform` — Map / Transform

**Use:** Rename columns or compute new ones from row expressions.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `map_transform` |
| Display name | Map / Transform |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `Wand2` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `mappings` | `json` | yes | `json` |  |  | [{ to: 'revenue', expression: 'row.qty * row.price' }, { from: 'old', to: 'new' }] |

## `note` — Note

**Use:** Canvas comment / annotation. Pass-through with text.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `note` |
| Display name | Note |
| UI section | `output` |
| Palette order | `0` |
| Color | `#475569` |
| Icon | `StickyNote` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

No declared outputs.

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `content` | `string` | yes | `textarea` | `""` |  |  |

## `pause` — Pause

**Use:** Wait for a number of milliseconds before continuing.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `pause` |
| Display name | Pause |
| UI section | `logic` |
| Palette order | `0` |
| Color | `#06b6d4` |
| Icon | `PauseCircle` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `durationMs` | `number` | yes | `number` | `500` |  |  |

## `pdf_extract` — PDF Extract

**Use:** Extract text from a PDF (mock content by default).

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `pdf_extract` |
| Display name | PDF Extract |
| UI section | `data` |
| Palette order | `0` |
| Color | `#0ea5e9` |
| Icon | `FileText` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `string` | yes | `text` | `default` |  | PDF filename |

## `response` — Response

**Use:** Return a final workflow response.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `response` |
| Display name | Response |
| UI section | `output` |
| Palette order | `0` |
| Color | `#b45309` |
| Icon | `ArrowRight` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `any` | `any` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `response` | `text` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `content` | `string` | no | `textarea` |  |  |  |

## `router` — Router

**Use:** Route rows to labelled branches by an expression returning a label.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `router` |
| Display name | Router |
| UI section | `logic` |
| Palette order | `0` |
| Color | `#06b6d4` |
| Icon | `Share2` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `expression` | `expression` | yes | `code` |  |  |  |

## `schedule` — Schedule

**Use:** Run on a cron schedule.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `schedule` |
| Display name | Schedule |
| UI section | `triggers` |
| Palette order | `0` |
| Color | `#7c3aed` |
| Icon | `Clock` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `payload` | `object` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `cron` | `string` | yes | `text` | `0 * * * *` |  | Cron expression |

## `select_columns` — Select Columns

**Use:** Pick a specific subset of columns.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `select_columns` |
| Display name | Select Columns |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `Columns` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `columns` | `string` | yes | `text` |  |  |  |

## `sort` — Sort

**Use:** Sort rows by a column.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `sort` |
| Display name | Sort |
| UI section | `transform` |
| Palette order | `0` |
| Color | `#f59e0b` |
| Icon | `ArrowUpDown` |
| Config tags |  |

**Inputs**

| Name | Type | Required | Description | Requirements |
| --- | --- | --- | --- | --- |
| `rows` | `dataframe` | yes |  |  |

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `rows` | `dataframe` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `sortBy` | `string` | yes | `text` |  |  |  |
| `order` | `enum` | yes | `select` | `asc` | `asc`, `desc` |  |

## `webhook_trigger` — Webhook

**Use:** Listen for incoming webhooks.

**Static metadata**

| Field | Value |
| --- | --- |
| Type | `webhook_trigger` |
| Display name | Webhook |
| UI section | `triggers` |
| Palette order | `0` |
| Color | `#7c3aed` |
| Icon | `Zap` |
| Config tags |  |

**Inputs**

No declared inputs.

**Outputs**

| Name | Type | Optional | Stored at | Description | Requirements |
| --- | --- | --- | --- | --- | --- |
| `payload` | `object` | no | `` |  |  |

**Config parameters**

| Name | Type | Required | Widget | Default | Enum/options | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `secret` | `string` | no | `text` |  |  | Optional shared secret |
