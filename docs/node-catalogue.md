# Node Catalogue

> **36 active nodes** in the Studio palette (May 2026). Legacy n8n types removed.
>
> **Source of truth:** `backend/engine/nodes/<type_id>.yaml` + `<type_id>.py`  
> **Dataset schemas:** `backend/connectors/metadata/*.yaml`  
> **Auto-generated catalogue:** `node_detail.md` (run `python backend/scripts/gen_artifacts.py`)  
> **MCP credentials, bridge endpoints, tools:** [MCP & Microsoft integrations](./mcp-integrations.md)

---

## Backend restructure (May 2026)

- **Nodes** — YAML + Python pairs under `engine/nodes/` (this catalogue).
- **Datasets** — catalog ids like `leads.csv`, `hs_alerts` come from `connectors/metadata/`, not `data_sources/`.
- **Copilot guardrails** — `generation/generation_guardrails.md`.
- **Vetted demo workflows** — `good_examples/studio_*.json` (not `backend/workflows/`).

---

## How to read this catalogue

Each node entry includes:

| Field | Meaning |
|-------|---------|
| **type_id** | The internal identifier used in workflow JSON and the registry |
| **Display name** | What appears on the canvas card |
| **Palette section** | Which sidebar group the node lives in |
| **Input ports** | What data the node receives (type + optional flag) |
| **Output ports** | What data the node produces |
| **Params** | Configuration fields shown in the right-panel inspector |

**Port types:** `dataframe` (table of rows), `text` (string), `object` (dict/JSON), `scalar` (number), `any` (passthrough)

**Widget types:** `text`, `textarea`, `number`, `select`, `switch`, `checkbox`, `code`, `starlark`, `json`, `password`

---

## Quick reference (all 36 nodes)

| Section | type_id | Display name |
|---------|---------|--------------|
| **Triggers** | `manual_trigger` | Manual Trigger |
| | `api_trigger` | API Trigger |
| | `webhook_trigger` | Webhook |
| | `schedule` | Schedule |
| **Data** | `csv_extract` | CSV Extract |
| | `db_query` | DB Query |
| | `http` | HTTP Request |
| | `pdf_extract` | PDF Extract |
| **Transform** | `join` | Join |
| | `data_merge` | Merge |
| | `map_transform` | Map / Transform |
| | `filter` | Filter |
| | `sort` | Sort |
| | `group_by` | Group By |
| | `deduplicate` | Deduplicate |
| | `select_columns` | Select Columns |
| **Logic** | `code` | Transform (Starlark) |
| | `condition` | Condition |
| | `router` | Router |
| | `function` | Function |
| | `loop` | Loop |
| | `pause` | Pause |
| **AI** | `agent` | AI Agent |
| | `evaluator` | Evaluator |
| **Integrations** | `jira_mcp` | Jira MCP |
| | `confluence_mcp` | Confluence MCP |
| | `github_mcp` | GitHub MCP |
| | `mcp` | MCP Tool (legacy) |
| | `github` | GitHub |
| | `gmail` | Gmail |
| | `outlook` | Outlook |
| | `slack` | Slack |
| | `teams` | Microsoft Teams |
| | `telegram` | Telegram |
| | `notion` | Notion |
| **Output** | `csv_output` | CSV Output |
| | `excel_output` | Excel Export |
| | `response` | Response |
| | `note` | Note |

**Copilot-approved subset:** `backend/engine/studio_nodes.py` — used for generation guardrails and demo workflows.

---

## Triggers

Trigger nodes **start** a workflow. They have no input ports and produce an
initial payload that flows downstream.

---

### Manual Trigger

| | |
|---|---|
| **type_id** | `manual_trigger` |
| **Icon** | Play |
| **Color** | `#7c3aed` (purple) |
| **Inputs** | *(none)* |
| **Outputs** | `payload` (object) — stored at `alert_payload` |
| **Params** | *(none)* |

**When to use:** The default starting point for any interactive or demo workflow.
Click "Run" in the Studio UI and the workflow begins. The payload object is
available to downstream nodes via the run context.

---

### API Trigger

| | |
|---|---|
| **type_id** | `api_trigger` |
| **Icon** | Webhook |
| **Color** | `#7c3aed` |
| **Inputs** | *(none)* |
| **Outputs** | `payload` (object) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `/webhook` | The webhook path to listen on |

**When to use:** When an external system (CI pipeline, monitoring tool, another
service) sends a POST request to start the workflow. The request body becomes
the output payload.

---

### Webhook

| | |
|---|---|
| **type_id** | `webhook_trigger` |
| **Icon** | Zap |
| **Color** | `#7c3aed` |
| **Inputs** | *(none)* |
| **Outputs** | `payload` (object) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `secret` | string | No | Shared secret for webhook verification |

**When to use:** Similar to API Trigger but with secret-based authentication.
Use when the webhook source supports HMAC or shared-secret validation.

**API Trigger vs Webhook:** API Trigger is path-based routing; Webhook adds
a secret verification layer. For simple integrations, API Trigger suffices.

---

### Schedule

| | |
|---|---|
| **type_id** | `schedule` |
| **Icon** | Clock |
| **Color** | `#7c3aed` |
| **Inputs** | *(none)* |
| **Outputs** | `payload` (object) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `cron` | string | `0 * * * *` | Cron expression (standard 5-field) |

**When to use:** Recurring batch jobs — daily reports, hourly data syncs,
periodic health checks. Common cron patterns:

| Pattern | Schedule |
|---------|----------|
| `0 * * * *` | Every hour |
| `0 9 * * 1-5` | Weekdays at 9am |
| `0 0 * * *` | Daily at midnight |
| `*/15 * * * *` | Every 15 minutes |

---

## Data

Data nodes **read** from sources — CSVs, databases, PDFs, or HTTP APIs. They
typically have no input ports and produce a `rows` dataframe.

---

### CSV Extract

| | |
|---|---|
| **type_id** | `csv_extract` |
| **Icon** | Table2 |
| **Color** | `#0ea5e9` (blue) |
| **Inputs** | *(none)* |
| **Outputs** | `rows` (dataframe) — stored at `datasets.<source>` |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | enum | Yes | Dataset filename — see available sources below |
| `limit` | number | No | Max rows to return |

**Available sources:**

| Source | Contents |
|--------|----------|
| `leads.csv` | Sales leads with names, companies, scores |
| `products.csv` | Product catalogue with SKUs, prices |
| `orders.csv` | Order records with quantities, dates |
| `employees.csv` | Employee directory |
| `transactions.csv` | Financial transactions |
| `hs_trades` | Surveillance trade data (SQLite) |
| `hs_alerts` | Surveillance alerts (SQLite) |
| `comms_messages` | Communications messages (SQLite) |

**When to use:** The primary way to load tabular data into a pipeline. For
demo/development workflows, the mock data is sufficient. For production, swap
to `db_query` or `http` with real endpoints.

---

### DB Query

| | |
|---|---|
| **type_id** | `db_query` |
| **Icon** | Database |
| **Color** | `#0ea5e9` |
| **Inputs** | *(none)* |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string (textarea) | Yes | SQL SELECT statement |
| `source` | enum | No | Source dataset (same list as CSV Extract) |

**When to use:** When you need SQL-style filtering, projection, or joins at
the source level rather than using transform nodes downstream.

```sql
-- Example queries
SELECT * FROM leads WHERE score > 80
SELECT region, COUNT(*) as cnt FROM orders GROUP BY region
SELECT * FROM hs_trades WHERE trader_id = 'T001'
```

---

### HTTP Request

| | |
|---|---|
| **type_id** | `http` |
| **Icon** | Globe |
| **Color** | `#0ea5e9` |
| **Inputs** | *(none)* |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Full URL to fetch |
| `method` | enum | No | `GET` (default), `POST`, `PUT`, `DELETE`, `PATCH` |
| `headers` | json | No | Request headers as JSON object |
| `body` | string (textarea) | No | Request body (for POST/PUT/PATCH) |

**When to use:** Pulling data from REST APIs, public datasets, or any HTTP
endpoint. The response is parsed as JSON and flattened into rows.

---

### PDF Extract

| | |
|---|---|
| **type_id** | `pdf_extract` |
| **Icon** | FileText |
| **Color** | `#0ea5e9` |
| **Inputs** | *(none)* |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | No | PDF filename (default: `default`) |

**When to use:** Ingesting unstructured document content — contracts, reports,
research papers. Returns rows with extracted text. Currently uses mock content;
wire to a real PDF parser for production.

---

## Transform

Transform nodes **reshape** data — filtering, sorting, grouping, joining,
renaming, deduplicating. They take `rows` in and produce `rows` out.

---

### Filter

| | |
|---|---|
| **type_id** | `filter` |
| **Icon** | Filter |
| **Color** | `#f59e0b` (amber) |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `expression` | expression (code editor) | Yes | Row-level predicate |

**Expression examples:**
```javascript
row.score >= 75
row.status === 'active'
row.amount > 1000 && row.region === 'US'
row.email !== null
```

**When to use:** Removing rows that don't meet criteria. For simple threshold
checks, this is more readable than a Starlark code node.

---

### Sort

| | |
|---|---|
| **type_id** | `sort` |
| **Icon** | ArrowUpDown |
| **Color** | `#f59e0b` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sortBy` | string | *(required)* | Column name to sort by |
| `order` | enum | `asc` | `asc` or `desc` |

**When to use:** Ordering data before display, export, or top-N selection.
Chain with a Starlark `code` node slicing `[:10]` for "top 10" patterns.

---

### Group By

| | |
|---|---|
| **type_id** | `group_by` |
| **Icon** | BarChart3 |
| **Color** | `#f59e0b` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `groupBy` | string | Yes | Column to group by (e.g. `region`) |
| `aggregateCol` | string | Yes | Column to aggregate (e.g. `revenue`) |
| `aggregateFn` | enum | Yes | `sum`, `avg`, `min`, `max`, or `count` |
| `alias` | string | No | Output column name (defaults to `aggregateCol_aggregateFn`) |

**When to use:** Summary statistics — total revenue by region, average score
by tier, count of orders by status. The output is one row per group.

---

### Join

| | |
|---|---|
| **type_id** | `join` |
| **Icon** | Merge |
| **Color** | `#f59e0b` |
| **Inputs** | `left` (dataframe), `right` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `leftKey` | string | *(required)* | Key column on the left input |
| `rightKey` | string | *(required)* | Key column on the right input |
| `joinType` | enum | `inner` | `inner`, `left`, `right`, or `outer` |

**When to use:** Combining two related tables — orders with products (by SKU),
leads with scores (by email), trades with alerts (by trader_id).

**Important:** This is a **multi-input** node. It needs exactly two upstream
edges — one for `left`, one for `right`. Edge order in the workflow JSON
determines which is which.

---

### Map / Transform

| | |
|---|---|
| **type_id** | `map_transform` |
| **Icon** | Wand2 |
| **Color** | `#f59e0b` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `mappings` | json (json editor) | Yes | Array of mapping objects |

**Mapping format:**
```json
[
  { "from": "old_name", "to": "new_name" },
  { "to": "revenue", "expression": "row.qty * row.price" },
  { "to": "full_name", "expression": "row.first + ' ' + row.last" }
]
```

**When to use:** Column renaming (`from`/`to`) and derived columns (`expression`).
For simple transforms, this is cleaner than a full Starlark code node.

---

### Select Columns

| | |
|---|---|
| **type_id** | `select_columns` |
| **Icon** | Columns |
| **Color** | `#f59e0b` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `columns` | string | Yes | Comma-separated column names |

**When to use:** Narrowing wide tables before export or display. Removes
clutter and reduces payload size.

```
name,email,score,region
```

---

### Deduplicate

| | |
|---|---|
| **type_id** | `deduplicate` |
| **Icon** | Copy |
| **Color** | `#f59e0b` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | string | Yes | Column to deduplicate on |

**When to use:** Data cleaning — removing duplicate contacts (by email),
duplicate orders (by order_id), duplicate records after merging sources.

---

### Merge

| | |
|---|---|
| **type_id** | `data_merge` |
| **Icon** | Layers |
| **Color** | `#f59e0b` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | enum | `concat` | `concat` (append rows) or `union` (deduplicate) |

**When to use:** Combining parallel branches back into one table. If a
Condition node split data into true/false branches that were processed
separately, Merge brings them back together.

---

### CSV Output

| | |
|---|---|
| **type_id** | `csv_output` |
| **Icon** | Download |
| **Color** | `#f59e0b` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `csv` (text) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `filename` | string | `output.csv` | Output filename |

**When to use:** Serializing rows to CSV text mid-pipeline or as a lightweight
export. For full spreadsheet exports with tabs and formatting, use Excel Export.

---

## Logic

Logic nodes **control flow** — branching, looping, custom code, and timing.

---

### Transform (Starlark)

| | |
|---|---|
| **type_id** | `code` |
| **Icon** | Code2 |
| **Color** | `#06b6d4` (cyan) |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Widget | Description |
|-------|------|----------|--------|-------------|
| `code` | code | Yes | Starlark editor | The Starlark script |
| `code_summary` | string | No | textarea | Plain-language explanation |

**Starlark rules:**
- **No** `import`, `while`, or recursion
- **No** filesystem or network access (hermetic sandbox)
- Upstream rows available as `input_data["rows"]` and `rows`
- Assign result to `output` (preferred) or `result`
- Use `def`, `for`, list comprehensions, `if/else`

**Examples:**

```python
# Keep top 5 by score
output = sorted(input_data["rows"], key=lambda r: r.get("score", 0), reverse=True)[:5]
```

```python
# Add a computed column
output = [
    {**r, "revenue": r.get("qty", 0) * r.get("price", 0)}
    for r in input_data["rows"]
]
```

```python
# Pivot: group by region, sum revenue
def group_sum(rows, key, val):
    acc = {}
    for r in rows:
        k = r.get(key, "")
        acc[k] = acc.get(k, 0) + r.get(val, 0)
    return [{"region": k, "total": v} for k, v in acc.items()]

output = group_sum(input_data["rows"], "region", "revenue")
```

**When to use:** The workhorse node for custom data transformations that don't
fit a built-in node. Especially valuable for AI-generated logic — the Copilot
writes Starlark scripts and fills `code_summary` automatically.

---

### Condition

| | |
|---|---|
| **type_id** | `condition` |
| **Icon** | GitBranch |
| **Color** | `#06b6d4` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `true_branch` (dataframe), `false_branch` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `expression` | expression (code editor) | Yes | Row-level predicate |

**When to use:** If/else routing — send high-score leads to enrichment,
low-score to a different path. Each downstream edge connects to either the
`true` or `false` output handle.

```javascript
row.score >= 80        // true = hot leads, false = cold leads
row.status === 'vip'   // true = VIP flow, false = standard flow
```

**Condition vs Filter:** Filter removes rows entirely. Condition keeps all
rows but routes them to different downstream paths.

---

### Router

| | |
|---|---|
| **type_id** | `router` |
| **Icon** | Share2 |
| **Color** | `#06b6d4` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `expression` | expression (code editor) | Yes | Expression returning a route label |

**When to use:** Multi-way routing — split by region, category, tier. Unlike
Condition (binary true/false), Router can send rows to N different branches.

```javascript
row.region      // routes: "US", "EU", "APAC"
row.tier        // routes: "gold", "silver", "bronze"
```

---

### Function

| | |
|---|---|
| **type_id** | `function` |
| **Icon** | FunctionSquare |
| **Color** | `#06b6d4` |
| **Inputs** | `any` (any, optional) |
| **Outputs** | `any` (any) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | code (code editor) | Yes | Python snippet |

**When to use:** Escape hatch for logic that needs full Python — calling
libraries, complex math, or accessing previous node outputs. Use sparingly;
prefer Starlark for data transforms (it's sandboxed and safer for AI generation).

```python
result = {'value': prevOutput.get('rowCount', 0) * 2}
```

---

### Loop

| | |
|---|---|
| **type_id** | `loop` |
| **Icon** | RefreshCw |
| **Color** | `#06b6d4` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `maxIterations` | number | 1000 | Safety cap on iterations |

**When to use:** When downstream nodes need iteration context or metadata.
The loop node is a pass-through that surfaces iteration state.

---

### Pause

| | |
|---|---|
| **type_id** | `pause` |
| **Icon** | PauseCircle |
| **Color** | `#06b6d4` |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `durationMs` | number | 500 | Milliseconds to wait |

**When to use:** Rate-limiting API calls, sequencing timed operations,
or waiting for external systems to process.

---

## AI

AI-powered nodes that call LLMs or evaluate data quality.

---

### AI Agent

| | |
|---|---|
| **type_id** | `agent` |
| **Icon** | Bot |
| **Color** | `#8b5cf6` (violet) |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `response` (text) |

| Param | Type | Default | Widget | Description |
|-------|------|---------|--------|-------------|
| `prompt` | string | | textarea | System instruction for the AI |
| `task` | string | | textarea | What the AI should do |
| `perRow` | boolean | `false` | switch | Process each row individually |
| `rowTemplate` | string | | textarea | Template with `{{column}}` placeholders (shown when `perRow=true`) |
| `outputColumn` | string | `_ai_response` | text | Column name for per-row results (shown when `perRow=true`) |
| `maxRows` | number | `5` | number | Cap rows for per-row calls (shown when `perRow=true`) |
| `model` | string | `gemini-2.5-flash` | text | Gemini model name |
| `emitPublishRow` | boolean | `false` | switch | Output a Confluence-ready `{title, body_markdown}` row |
| `pageTitle` | string | | text | Confluence page title (shown when `emitPublishRow=true`) |

**Requires:** `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in `backend/.env`

**Mode 1 — Bulk summary (default):**
Sends all rows (up to 50) plus the prompt/task to Gemini. Returns a single
summary response. Great for "summarize these leads" or "analyze this data."

**Mode 2 — Per-row enrichment (`perRow=true`):**
Calls Gemini once per row using the `rowTemplate`. Adds the AI response as a
new column. Great for "classify each lead" or "generate a tagline for each product."

```
rowTemplate: "Lead: {{first_name}} from {{company}}, score {{score}}"
```

**Mode 3 — Confluence publish (`emitPublishRow=true`):**
Replaces output with a single row containing `{title, body_markdown}` that
can be piped directly into an MCP `confluence_publish_report` tool call.

---

### Evaluator

| | |
|---|---|
| **type_id** | `evaluator` |
| **Icon** | CheckSquare |
| **Color** | `#8b5cf6` |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `criteria` | expression (code editor) | *(required)* | Pass/fail expression |
| `label` | string | `passed` | Column name for the result label |

**When to use:** Data quality gates, SLA validation, threshold checks. Each
row gets a pass/fail label, and the node reports the overall pass rate.

```javascript
row.score >= 80
row.response_time < 200
row.status !== 'error'
```

---

## Integrations

Nodes that connect to external services — Confluence, Jira, GitHub, Slack,
Gmail, Telegram, Notion.

---

### MCP integrations (Atlassian + GitHub) {#mcp-integrations-atlassian--github}

> **Full guide:** [MCP & Microsoft integrations](./mcp-integrations.md) — credentials, `POST /tools/{name}/run`, demo vs live, Teams/Outlook status.

Studio MCP nodes call the **HTTP MCP bridge** (`http://127.0.0.1:8765` by default), not stdio MCP servers. **Credentials are defined only in `backend/.env`** — inspector fields are read-only (`locked_env`); saved workflows cannot store tokens (`engine/integration_locked.py`).

#### Credential environment variables

| Provider | Variables | Used by |
|----------|-----------|---------|
| **Atlassian** (Jira + Confluence) | `ATLASSIAN_SITE_URL`, `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`, `CONFLUENCE_SPACE_KEY`, `JIRA_PROJECT_KEY` | `jira_mcp`, `confluence_mcp`, legacy `mcp` |
| **GitHub** | `GITHUB_TOKEN` (or `GITHUB_PERSONAL_ACCESS_TOKEN`), `GITHUB_REPO` | `github_mcp`, legacy `mcp` |
| **Bridge** | `MCP_SERVER_URL`, `MCP_BRIDGE_MODE` (`demo` \| live), `MCP_BRIDGE_AUTOSTART` | All MCP nodes |

**HTTP contract:** `POST {MCP_SERVER_URL}/tools/{tool}/run` with JSON `{ params, credentials }`. See [mcp-integrations.md §3](./mcp-integrations.md#3-http-endpoints).

#### Typed nodes (preferred)

| type_id | Display name | Tools (enum) | Notes |
|---------|--------------|--------------|-------|
| `jira_mcp` | Jira MCP | `jira_create_issue`, `jira_list_issues`, `jira_create_epics_from_confluence`, `tasks_bulk_create` | Atlassian env |
| `confluence_mcp` | Confluence MCP | `confluence_search_pages`, `confluence_extract_action_items`, `confluence_publish_report`, `studio_publish_architecture_doc` | Search/extract are **demo-first**; publish is **live** when creds set |
| `github_mcp` | GitHub MCP | `github_list_commits`, `github_implement_fixes`, `github_fix_jira_and_update` | `github_fix_jira_and_update` is the **live** Jira+PR path |

Shared params: `serverUrl` (optional), locked credential mirrors, `tool`, `params` (JSON; upstream rows → `params.data`).

Implementation: `engine/nodes/mcp_common.py` → `mcp_bridge/server.py` → `integrations/mcp/*` (live) or `mcp_bridge/tools.py` (demo).

#### Legacy MCP Tool

| | |
|---|---|
| **type_id** | `mcp` |
| **Status** | Legacy — `normalize_mcp_workflow()` upgrades to `jira_mcp` / `confluence_mcp` / `github_mcp` by `config.tool` |
| **Inputs / outputs** | `rows` → `rows` |

Still accepts `integration: atlassian \| github` and the combined tool list from `engine/nodes/mcp.yaml`. Prefer typed nodes for new workflows and Copilot examples.

#### Tool quick reference

| Tool | Demo | Live API |
|------|------|----------|
| `confluence_search_pages` | Yes | No |
| `confluence_extract_action_items` | Yes | No |
| `confluence_publish_report` | Yes | Yes |
| `studio_publish_architecture_doc` | — | Yes |
| `tasks_bulk_create` | Yes | No |
| `jira_create_issue` / `jira_list_issues` | Yes | Yes |
| `jira_create_epics_from_confluence` | — | Yes (live mode) |
| `github_list_commits` | Yes | Yes |
| `github_implement_fixes` | Yes | No |
| `github_fix_jira_and_update` | — | Yes |

Set `MCP_BRIDGE_MODE=live` in `backend/.env` and restart the bridge for live rows. Default `demo` needs no tokens (fixtures in `mcp_bridge/demo_data.py`).

---

### GitHub

| | |
|---|---|
| **type_id** | `github` |
| **Icon** | Github |
| **Color** | `#24292e` |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Shown when |
|-------|------|----------|------------|
| `action` | enum | Yes | Always |
| `repo` | string | Varies | Most actions |
| `state` | enum (`open`/`closed`/`all`) | No | `list-issues`, `list-prs` |
| `title` | string | Yes | `create-issue` |
| `body` | string (textarea) | No | `create-issue` |
| `labels` | string | No | `create-issue` |
| `filePath` | string | Yes | `push-file` |
| `fileContent` | string (textarea) | Yes | `push-file` |
| `fileFormat` | enum (`json`/`csv`) | No | `push-file` |
| `branch` | string | No | `push-file` |
| `commitMessage` | string | No | `push-file` |

**Actions:** `list-repos`, `list-issues`, `list-prs`, `list-commits`,
`get-repo`, `create-issue`, `push-file`

**When to use:** Direct GitHub REST without the MCP bridge — list/create/push file.
For Jira-linked PR flows and commit briefings, use **`github_mcp`** and see [MCP Integrations](./mcp-integrations.md).

**Credentials:** same `GITHUB_TOKEN` / `GITHUB_REPO` in `backend/.env` (not locked in workflow JSON for `repo` when set on node).

---

### Gmail

| | |
|---|---|
| **type_id** | `gmail` |
| **Icon** | Mail |
| **Color** | `#ea4335` |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `result` (object) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `to` | string | Yes | Recipient email |
| `subject` | string | Yes | Email subject |
| `body` | string (textarea) | No | Email body |

**Requires:** `GMAIL_CLIENT_SECRET` in environment (stubs when missing).

---

### Slack

| | |
|---|---|
| **type_id** | `slack` |
| **Icon** | MessageSquare |
| **Color** | `#4a154b` |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `result` (object) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `channel` | string | `#general` | Slack channel |
| `message` | string (textarea) | | Message text |
| `webhookUrl` | string | | Optional incoming webhook URL (fallback if no bot token) |

**Requires:** `SLACK_BOT_TOKEN` in environment, or provide `webhookUrl`.

---

### Telegram

| | |
|---|---|
| **type_id** | `telegram` |
| **Icon** | Send |
| **Color** | `#229ED9` |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `result` (object) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `chatId` | string | | Chat or group ID (or set `TELEGRAM_CHAT_ID`) |
| `message` | string (textarea) | | Message text |
| `parseMode` | string | `Markdown` | `Markdown`, `HTML`, or empty |
| `botToken` | string | | Override `TELEGRAM_BOT_TOKEN` env var |

---

### Notion

| | |
|---|---|
| **type_id** | `notion` |
| **Icon** | BookOpen |
| **Color** | `#000000` |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `rows` (dataframe) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `databaseId` | string | Yes | Notion database ID |
| `action` | enum | No | Currently `query` only |

**Requires:** `NOTION_API_KEY` in environment.

---

### Microsoft Teams

| | |
|---|---|
| **type_id** | `teams` |
| **Palette** | `studio_active: false` — manual palette / saved workflows; Copilot does not generate by default |
| **Protocol** | **Not MCP** — direct `httpx` POST to incoming webhook |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `result` (object) |

| Param | Type | Description |
|-------|------|-------------|
| `deliveryMode` | enum | `incoming_webhook` (**implemented**) or `graph` (**not implemented**) |
| `webhookUrl` | string | Override `TEAMS_INCOMING_WEBHOOK_URL` |
| `message` | textarea | Body; defaults from first upstream row |
| `teamId` / `channelId` | string | Reserved for future Graph mode |

**Credentials (`backend/.env`):**

```bash
TEAMS_INCOMING_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

**Done today:** Incoming webhook send (`engine/nodes/teams.py`).  
**Not done:** Graph API mode, Adaptive Cards, locked_env UI, `studio_active: true` for Sherpa generation.

See [MCP doc §8 — Teams](./mcp-integrations.md#8-microsoft-teams-not-mcp). Demo: `good_examples/studio_11_teams_risk_digest.json`.

---

### Outlook

| | |
|---|---|
| **type_id** | `outlook` |
| **Palette** | `studio_active: false` — placeholder; Sherpa may suggest email but send is not wired |
| **Protocol** | **Not MCP** — intended Microsoft Graph mail send |
| **Inputs** | `rows` (dataframe, optional) |
| **Outputs** | `result` (object) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `to` | string | Yes | Recipient email |
| `subject` | string | Yes | Subject |
| `body` | textarea | No | Body |
| `tenantId` | string | No | Override `OUTLOOK_TENANT_ID` |

**Credentials (`backend/.env`):**

```bash
OUTLOOK_TENANT_ID=...
OUTLOOK_CLIENT_ID=...
OUTLOOK_CLIENT_SECRET=...
```

**Done today:** `require_outlook()` validates the three vars; node fails fast with a clear error if missing.  
**Not done:** OAuth/token acquisition, `sendMail` Graph call — `run()` raises *“Outlook Graph send is not implemented yet”* after cred check.

Sherpa: `follow_up_outlook_unavailable_override` and run analyst copy guide users to `.env` when they ask for Outlook on locked integrations.

See [MCP doc §9 — Outlook](./mcp-integrations.md#9-microsoft-outlook-not-mcp).

---

## Output

Output nodes produce **final artifacts** or annotations.

---

### Excel Export

| | |
|---|---|
| **type_id** | `excel_output` |
| **Icon** | FileSpreadsheet |
| **Color** | `#16a34a` (green) |
| **Inputs** | `rows` (dataframe) |
| **Outputs** | `file` (object) |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `filename` | string | `output.xlsx` | Output filename |
| `tabNames` | string | | Tab names: `"Tab1,Tab2"` or `["Tab1","Tab2"]` |

**Multi-tab pattern:** Connect multiple upstream edges — one per tab. The
`tabNames` param maps each edge to a tab name in order.

---

### Response

| | |
|---|---|
| **type_id** | `response` |
| **Icon** | ArrowRight |
| **Color** | `#b45309` |
| **Inputs** | `any` (any) |
| **Outputs** | `response` (text) |

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string (textarea) | No | Optional static content |

**When to use:** Terminal node to surface a human-readable result from the
workflow. If `content` is empty, passes through upstream text.

---

### Note

| | |
|---|---|
| **type_id** | `note` |
| **Icon** | StickyNote |
| **Color** | `#475569` |
| **Inputs** | *(none)* |
| **Outputs** | *(none)* |

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | string (textarea) | | Markdown annotation text |

**When to use:** Canvas comments — explaining why a branch exists, documenting
business rules, leaving notes for collaborators. No runtime effect.

---

## Node selection guide

| I want to... | Use this node |
|--------------|--------------|
| Start a workflow manually | `manual_trigger` |
| Start from an external POST | `api_trigger` or `webhook_trigger` |
| Run on a schedule | `schedule` |
| Load tabular data | `csv_extract` or `db_query` |
| Call a REST API | `http` |
| Filter rows by condition | `filter` |
| Sort rows | `sort` |
| Aggregate (sum, avg, count) | `group_by` |
| Combine two tables | `join` |
| Rename/compute columns | `map_transform` |
| Custom data transform | `code` (Starlark) |
| If/else branching | `condition` |
| Multi-way routing | `router` |
| AI summarization | `agent` |
| AI per-row enrichment | `agent` with `perRow=true` |
| Quality gate | `evaluator` |
| Publish to Confluence | `mcp` with `confluence_publish_report` |
| Create Jira tickets | `mcp` with `jira_create_issue` |
| Push to GitHub | `github` with `push-file` |
| Send Slack message | `slack` |
| Send email | `gmail` |
| Export to Excel | `excel_output` |
| Export to CSV | `csv_output` |
| Add a canvas comment | `note` |
