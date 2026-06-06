/**
 * AUTO-GENERATED — do not edit by hand.
 * Run `python backend/scripts/gen_artifacts.py` to regenerate.
 * Source: backend/engine/registry.py
 */
import type { LucideIcon } from 'lucide-react'
import { LUCIDE_ICON_MAP } from './lucideIconMap'

export type NodeType =
  | 'agent'
  | 'api_trigger'
  | 'code'
  | 'condition'
  | 'confluence_mcp'
  | 'csv_extract'
  | 'csv_output'
  | 'data_merge'
  | 'db_query'
  | 'deduplicate'
  | 'evaluator'
  | 'excel_output'
  | 'filter'
  | 'function'
  | 'github'
  | 'github_mcp'
  | 'group_by'
  | 'http'
  | 'jira_mcp'
  | 'join'
  | 'loop'
  | 'manual_trigger'
  | 'map_transform'
  | 'note'
  | 'pause'
  | 'pdf_extract'
  | 'response'
  | 'router'
  | 'schedule'
  | 'select_columns'
  | 'sort'
  | 'webhook_trigger'

export interface NodeUIMeta {
  color: string
  Icon: LucideIcon
  description: string
  /** Config keys whose values are rendered as chips on the node card. */
  configTags: readonly string[]
  /** Palette group id — must match PaletteSection.id */
  paletteGroup: string
  /** Sort key within the palette group (lower first). */
  paletteOrder: number
  /** Short card title; when omitted, UI title-cases type_id. */
  displayName?: string
  placeholder?: boolean
}

export interface PaletteSection {
  id: string
  label: string
  order: number
  color: string
}

export const PALETTE_SECTIONS: readonly PaletteSection[] = [
  {
    "id": "triggers",
    "label": "Triggers",
    "order": 5,
    "color": "#0EA5E9"
  },
  {
    "id": "data",
    "label": "Data",
    "order": 10,
    "color": "#10B981"
  },
  {
    "id": "transform",
    "label": "Transform",
    "order": 15,
    "color": "#6366F1"
  },
  {
    "id": "logic",
    "label": "Logic",
    "order": 20,
    "color": "#F59E0B"
  },
  {
    "id": "integrations",
    "label": "Integrations",
    "order": 25,
    "color": "#14B8A6"
  },
  {
    "id": "ai",
    "label": "AI",
    "order": 30,
    "color": "#8B5CF6"
  },
  {
    "id": "output",
    "label": "Output",
    "order": 35,
    "color": "#EC4899"
  }
] as const

export const NODE_UI: Record<NodeType, NodeUIMeta> = {
  agent: {
    color: '#8b5cf6',
    Icon: LUCIDE_ICON_MAP["Bot"],
    description: "Call Gemini with rows + prompt (requires GEMINI_API_KEY in backend/.env).",
    configTags: [] as const,
    paletteGroup: "ai",
    paletteOrder: 0,
    displayName: "AI Agent",
  },
  api_trigger: {
    color: '#7c3aed',
    Icon: LUCIDE_ICON_MAP["Webhook"],
    description: "Trigger via HTTP webhook (returns the request payload).",
    configTags: [] as const,
    paletteGroup: "triggers",
    paletteOrder: 0,
    displayName: "API Trigger",
  },
  code: {
    color: '#06b6d4',
    Icon: LUCIDE_ICON_MAP["Code2"],
    description: "Run sandboxed Starlark on the incoming rows. Assign the transformed table to `output` (preferred) or `result`. No imports, while loops, or filesystem/network access \u2014 safe for AI-generated logic.",
    configTags: [] as const,
    paletteGroup: "logic",
    paletteOrder: 0,
    displayName: "Transform (Starlark)",
  },
  condition: {
    color: '#06b6d4',
    Icon: LUCIDE_ICON_MAP["GitBranch"],
    description: "Branch rows into true / false outputs by an expression.",
    configTags: [] as const,
    paletteGroup: "logic",
    paletteOrder: 0,
    displayName: "Condition",
  },
  confluence_mcp: {
    color: '#172B4D',
    Icon: LUCIDE_ICON_MAP["ScrollText"],
    description: "Call Confluence MCP bridge tools \u2014 search pages, extract action items, publish reports.",
    configTags: [] as const,
    paletteGroup: "integrations",
    paletteOrder: 11,
    displayName: "Confluence MCP",
  },
  csv_extract: {
    color: '#0ea5e9',
    Icon: LUCIDE_ICON_MAP["Table2"],
    description: "Load rows from an Oracle-backed dataset (alias for table extract).",
    configTags: [] as const,
    paletteGroup: "data",
    paletteOrder: 0,
    displayName: "Data Extract",
  },
  csv_output: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["Download"],
    description: "Serialize rows to a CSV string.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "CSV Output",
  },
  data_merge: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["Layers"],
    description: "Concatenate or union multiple datasets.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Merge",
  },
  db_query: {
    color: '#0ea5e9',
    Icon: LUCIDE_ICON_MAP["Database"],
    description: "Run a SELECT against an Oracle-backed dataset.",
    configTags: [] as const,
    paletteGroup: "data",
    paletteOrder: 0,
    displayName: "DB Query",
  },
  deduplicate: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["Copy"],
    description: "Remove duplicate rows by a key column.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Deduplicate",
  },
  evaluator: {
    color: '#8b5cf6',
    Icon: LUCIDE_ICON_MAP["CheckSquare"],
    description: "Evaluate rows against criteria; reports pass / fail rate.",
    configTags: [] as const,
    paletteGroup: "ai",
    paletteOrder: 0,
    displayName: "Evaluator",
  },
  excel_output: {
    color: '#16a34a',
    Icon: LUCIDE_ICON_MAP["FileSpreadsheet"],
    description: "Write multi-tab Excel from each upstream dataset.",
    configTags: [] as const,
    paletteGroup: "output",
    paletteOrder: 0,
    displayName: "Excel Export",
  },
  filter: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["Filter"],
    description: "Filter rows by an expression (row.column accessible).",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Filter",
  },
  function: {
    color: '#06b6d4',
    Icon: LUCIDE_ICON_MAP["FunctionSquare"],
    description: "Run Python code with access to input and previous output.",
    configTags: [] as const,
    paletteGroup: "logic",
    paletteOrder: 0,
    displayName: "Function",
  },
  github: {
    color: '#24292e',
    Icon: LUCIDE_ICON_MAP["Github"],
    description: "GitHub API actions. Requires GITHUB_TOKEN and GITHUB_REPO (or config.repo).",
    configTags: [] as const,
    paletteGroup: "integrations",
    paletteOrder: 0,
    displayName: "GitHub",
  },
  github_mcp: {
    color: '#24292F',
    Icon: LUCIDE_ICON_MAP["GitPullRequest"],
    description: "Call GitHub MCP bridge tools \u2014 implement fixes, open PRs linked to Jira issues.",
    configTags: [] as const,
    paletteGroup: "integrations",
    paletteOrder: 12,
    displayName: "GitHub MCP",
  },
  group_by: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["BarChart3"],
    description: "Aggregate rows by a column.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Group By",
  },
  http: {
    color: '#0ea5e9',
    Icon: LUCIDE_ICON_MAP["Globe"],
    description: "Fetch data from any HTTP URL.",
    configTags: [] as const,
    paletteGroup: "data",
    paletteOrder: 0,
    displayName: "HTTP Request",
  },
  jira_mcp: {
    color: '#0052CC',
    Icon: LUCIDE_ICON_MAP["Ticket"],
    description: "Call Jira MCP bridge tools \u2014 create issues, list tickets, epics from Confluence.",
    configTags: [] as const,
    paletteGroup: "integrations",
    paletteOrder: 10,
    displayName: "Jira MCP",
  },
  join: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["Merge"],
    description: "Join two upstream datasets on key columns.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Join",
  },
  loop: {
    color: '#06b6d4',
    Icon: LUCIDE_ICON_MAP["RefreshCw"],
    description: "Iterate over rows (pass-through; surfaces iteration metadata).",
    configTags: [] as const,
    paletteGroup: "logic",
    paletteOrder: 0,
    displayName: "Loop",
  },
  manual_trigger: {
    color: '#7c3aed',
    Icon: LUCIDE_ICON_MAP["Play"],
    description: "Start workflow manually.",
    configTags: [] as const,
    paletteGroup: "triggers",
    paletteOrder: 0,
    displayName: "Manual Trigger",
  },
  map_transform: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["Wand2"],
    description: "Rename columns or compute new ones from row expressions.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Map / Transform",
  },
  note: {
    color: '#475569',
    Icon: LUCIDE_ICON_MAP["StickyNote"],
    description: "Canvas comment / annotation. Pass-through with text.",
    configTags: [] as const,
    paletteGroup: "output",
    paletteOrder: 0,
    displayName: "Note",
  },
  pause: {
    color: '#06b6d4',
    Icon: LUCIDE_ICON_MAP["PauseCircle"],
    description: "Wait for a number of milliseconds before continuing.",
    configTags: [] as const,
    paletteGroup: "logic",
    paletteOrder: 0,
    displayName: "Pause",
  },
  pdf_extract: {
    color: '#0ea5e9',
    Icon: LUCIDE_ICON_MAP["FileText"],
    description: "Extract text from a PDF (mock content by default).",
    configTags: [] as const,
    paletteGroup: "data",
    paletteOrder: 0,
    displayName: "PDF Extract",
  },
  response: {
    color: '#b45309',
    Icon: LUCIDE_ICON_MAP["ArrowRight"],
    description: "Return a final workflow response.",
    configTags: [] as const,
    paletteGroup: "output",
    paletteOrder: 0,
    displayName: "Response",
  },
  router: {
    color: '#06b6d4',
    Icon: LUCIDE_ICON_MAP["Share2"],
    description: "Route rows to labelled branches by an expression returning a label.",
    configTags: [] as const,
    paletteGroup: "logic",
    paletteOrder: 0,
    displayName: "Router",
  },
  schedule: {
    color: '#7c3aed',
    Icon: LUCIDE_ICON_MAP["Clock"],
    description: "Run on a cron schedule.",
    configTags: [] as const,
    paletteGroup: "triggers",
    paletteOrder: 0,
    displayName: "Schedule",
  },
  select_columns: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["Columns"],
    description: "Pick a specific subset of columns.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Select Columns",
  },
  sort: {
    color: '#f59e0b',
    Icon: LUCIDE_ICON_MAP["ArrowUpDown"],
    description: "Sort rows by a column.",
    configTags: [] as const,
    paletteGroup: "transform",
    paletteOrder: 0,
    displayName: "Sort",
  },
  webhook_trigger: {
    color: '#7c3aed',
    Icon: LUCIDE_ICON_MAP["Zap"],
    description: "Listen for incoming webhooks.",
    configTags: [] as const,
    paletteGroup: "triggers",
    paletteOrder: 0,
    displayName: "Webhook",
  },
}

export const NODE_TYPES: readonly NodeType[] = [
  'agent',
  'api_trigger',
  'code',
  'condition',
  'confluence_mcp',
  'csv_extract',
  'csv_output',
  'data_merge',
  'db_query',
  'deduplicate',
  'evaluator',
  'excel_output',
  'filter',
  'function',
  'github',
  'github_mcp',
  'group_by',
  'http',
  'jira_mcp',
  'join',
  'loop',
  'manual_trigger',
  'map_transform',
  'note',
  'pause',
  'pdf_extract',
  'response',
  'router',
  'schedule',
  'select_columns',
  'sort',
  'webhook_trigger',
] as const

/** Schema + constraints for a node type, surfaced in the Config inspector. */
export interface NodeContract {
  description: string
  inputs: Record<string, string>
  outputs: Record<string, string>
  configSchema: Record<string, string>
  constraints: readonly string[]
}

export const NODE_CONTRACTS: Record<NodeType, NodeContract> = {
  agent: {
    description: "Call Gemini with rows + prompt (requires GEMINI_API_KEY in backend/.env).",
    inputs: {
          "rows": ""
    },
    outputs: {
          "response": ""
    },
    configSchema: {
          "prompt": "",
          "task": "",
          "perRow": "",
          "rowTemplate": "",
          "outputColumn": "",
          "maxRows": "Cap rows for per-row AI calls. Keep low (\u226410) for snappy demos.",
          "model": "",
          "emitPublishRow": "Replace output rows with one Confluence-ready {title, body_markdown} row.",
          "pageTitle": ""
    },
    constraints: [] as const,
  },
  api_trigger: {
    description: "Trigger via HTTP webhook (returns the request payload).",
    inputs: {},
    outputs: {
          "payload": ""
    },
    configSchema: {
          "path": "Webhook path"
    },
    constraints: [] as const,
  },
  code: {
    description: "Run sandboxed Starlark on the incoming rows. Assign the transformed table to `output` (preferred) or `result`. No imports, while loops, or filesystem/network access \u2014 safe for AI-generated logic.",
    inputs: {
          "rows": "Table rows from the upstream node."
    },
    outputs: {
          "rows": "Transformed rows produced by your Starlark script."
    },
    configSchema: {
          "code_summary": "Plain-language explanation of what the Starlark script does (for non-technical readers). Usually filled by the AI when code is generated.",
          "code": ""
    },
    constraints: ["Do not use import, while, or recursion in Starlark.", "Prefer assigning `output`; `result` is accepted for older workflows.", "Upstream rows are available as `input_data[\"rows\"]` and as `rows`."] as const,
  },
  condition: {
    description: "Branch rows into true / false outputs by an expression.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "true_branch": "",
          "false_branch": ""
    },
    configSchema: {
          "expression": ""
    },
    constraints: [] as const,
  },
  confluence_mcp: {
    description: "Call Confluence MCP bridge tools \u2014 search pages, extract action items, publish reports.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "serverUrl": "Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL).",
          "confluenceSiteUrl": "Confluence site URL (from backend/.env \u2014 locked).",
          "confluenceEmail": "Confluence account email (from backend/.env \u2014 locked).",
          "confluenceApiToken": "Confluence API token (from backend/.env \u2014 locked).",
          "confluenceSpaceKey": "Confluence space key (from backend/.env \u2014 locked).",
          "pageTitle": "Confluence page title override (defaults to generated name).",
          "tool": "Confluence MCP tool to invoke.",
          "params": "Tool arguments (JSON). Upstream rows are passed as params.data automatically."
    },
    constraints: [] as const,
  },
  csv_extract: {
    description: "Load rows from an Oracle-backed dataset (alias for table extract).",
    inputs: {},
    outputs: {
          "rows": ""
    },
    configSchema: {
          "source": "Dataset id",
          "limit": "Row limit (optional)"
    },
    constraints: [] as const,
  },
  csv_output: {
    description: "Serialize rows to a CSV string.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "csv": ""
    },
    configSchema: {
          "filename": ""
    },
    constraints: [] as const,
  },
  data_merge: {
    description: "Concatenate or union multiple datasets.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "strategy": ""
    },
    constraints: [] as const,
  },
  db_query: {
    description: "Run a SELECT against an Oracle-backed dataset.",
    inputs: {},
    outputs: {
          "rows": ""
    },
    configSchema: {
          "query": "SELECT * FROM comms_messages LIMIT 20",
          "source": "Source dataset"
    },
    constraints: [] as const,
  },
  deduplicate: {
    description: "Remove duplicate rows by a key column.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "key": ""
    },
    constraints: [] as const,
  },
  evaluator: {
    description: "Evaluate rows against criteria; reports pass / fail rate.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "criteria": "",
          "label": ""
    },
    constraints: [] as const,
  },
  excel_output: {
    description: "Write multi-tab Excel from each upstream dataset.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "file": ""
    },
    configSchema: {
          "filename": "",
          "tabNames": "",
          "highlightColumn": "",
          "highlightMapping": ""
    },
    constraints: [] as const,
  },
  filter: {
    description: "Filter rows by an expression (row.column accessible).",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "expression": ""
    },
    constraints: [] as const,
  },
  function: {
    description: "Run Python code with access to input and previous output.",
    inputs: {
          "any": ""
    },
    outputs: {
          "any": ""
    },
    configSchema: {
          "code": ""
    },
    constraints: [] as const,
  },
  github: {
    description: "GitHub API actions. Requires GITHUB_TOKEN and GITHUB_REPO (or config.repo).",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "action": "",
          "repo": "",
          "state": "",
          "title": "",
          "body": "",
          "labels": "",
          "filePath": "",
          "fileContent": "",
          "fileFormat": "",
          "branch": "",
          "commitMessage": ""
    },
    constraints: [] as const,
  },
  github_mcp: {
    description: "Call GitHub MCP bridge tools \u2014 implement fixes, open PRs linked to Jira issues.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "serverUrl": "Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL).",
          "githubToken": "GitHub PAT (from backend/.env \u2014 locked).",
          "githubRepo": "Target repository (from backend/.env \u2014 locked).",
          "tool": "GitHub MCP tool to invoke.",
          "params": "Tool arguments (JSON). Upstream rows are passed as params.data automatically."
    },
    constraints: [] as const,
  },
  group_by: {
    description: "Aggregate rows by a column.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "groupBy": "",
          "aggregateCol": "",
          "aggregateFn": "",
          "alias": ""
    },
    constraints: [] as const,
  },
  http: {
    description: "Fetch data from any HTTP URL.",
    inputs: {},
    outputs: {
          "rows": ""
    },
    configSchema: {
          "url": "",
          "method": "",
          "headers": "",
          "body": ""
    },
    constraints: [] as const,
  },
  jira_mcp: {
    description: "Call Jira MCP bridge tools \u2014 create issues, list tickets, epics from Confluence.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "serverUrl": "Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL).",
          "jiraSiteUrl": "Jira site URL (from backend/.env \u2014 locked).",
          "jiraEmail": "Jira account email (from backend/.env \u2014 locked).",
          "jiraApiToken": "Jira API token (from backend/.env \u2014 locked).",
          "jiraProjectKey": "Jira project key (from backend/.env \u2014 locked).",
          "tool": "Jira MCP tool to invoke.",
          "params": "Tool arguments (JSON). Upstream rows are passed as params.data automatically."
    },
    constraints: [] as const,
  },
  join: {
    description: "Join two upstream datasets on key columns.",
    inputs: {
          "left": "",
          "right": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "leftKey": "",
          "rightKey": "",
          "joinType": ""
    },
    constraints: [] as const,
  },
  loop: {
    description: "Iterate over rows (pass-through; surfaces iteration metadata).",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "maxIterations": ""
    },
    constraints: [] as const,
  },
  manual_trigger: {
    description: "Start workflow manually.",
    inputs: {},
    outputs: {
          "payload": ""
    },
    configSchema: {},
    constraints: [] as const,
  },
  map_transform: {
    description: "Rename columns or compute new ones from row expressions.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "mappings": "[{ to: 'revenue', expression: 'row.qty * row.price' }, { from: 'old', to: 'new' }]"
    },
    constraints: [] as const,
  },
  note: {
    description: "Canvas comment / annotation. Pass-through with text.",
    inputs: {},
    outputs: {},
    configSchema: {
          "content": ""
    },
    constraints: [] as const,
  },
  pause: {
    description: "Wait for a number of milliseconds before continuing.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "durationMs": ""
    },
    constraints: [] as const,
  },
  pdf_extract: {
    description: "Extract text from a PDF (mock content by default).",
    inputs: {},
    outputs: {
          "rows": ""
    },
    configSchema: {
          "source": "PDF filename"
    },
    constraints: [] as const,
  },
  response: {
    description: "Return a final workflow response.",
    inputs: {
          "any": ""
    },
    outputs: {
          "response": ""
    },
    configSchema: {
          "content": ""
    },
    constraints: [] as const,
  },
  router: {
    description: "Route rows to labelled branches by an expression returning a label.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "expression": ""
    },
    constraints: [] as const,
  },
  schedule: {
    description: "Run on a cron schedule.",
    inputs: {},
    outputs: {
          "payload": ""
    },
    configSchema: {
          "cron": "Cron expression"
    },
    constraints: [] as const,
  },
  select_columns: {
    description: "Pick a specific subset of columns.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "columns": ""
    },
    constraints: [] as const,
  },
  sort: {
    description: "Sort rows by a column.",
    inputs: {
          "rows": ""
    },
    outputs: {
          "rows": ""
    },
    configSchema: {
          "sortBy": "",
          "order": ""
    },
    constraints: [] as const,
  },
  webhook_trigger: {
    description: "Listen for incoming webhooks.",
    inputs: {},
    outputs: {
          "payload": ""
    },
    configSchema: {
          "secret": "Optional shared secret"
    },
    constraints: [] as const,
  },
}

/** Typed port — what flows along an edge. */
export interface NodePortSpec {
  name: string
  type: 'dataframe' | 'scalar' | 'object' | 'text' | 'any'
  description: string
  optional: boolean
  required_columns?: readonly string[]
  required_keys?: readonly string[]
  source_config_key?: string
  store_at?: string
}

/** Typed config param with UI hint. */
export interface NodeParamSpec {
  name: string
  type:
    | 'string'
    | 'integer'
    | 'number'
    | 'boolean'
    | 'enum'
    | 'string_list'
    | 'object'
    | 'array'
    | 'input_ref'
    | 'code'
    | 'expression'
    | 'json'
  description: string
  required: boolean
  widget:
    | 'text'
    | 'textarea'
    | 'number'
    | 'checkbox'
    | 'select'
    | 'chips'
    | 'json'
    | 'input_ref'
    | 'code'
    | 'password'
    | 'switch'
    | 'starlark'
    | 'starlark_editor'
    | 'locked_env'
  default?: unknown
  enum?: readonly string[]
  visible_if?: Record<string, string | boolean | readonly string[] | readonly boolean[]>
  locked_from_env?: boolean
  env_key?: string
}

export interface NodeTypedSpec {
  inputPorts: readonly NodePortSpec[]
  outputPorts: readonly NodePortSpec[]
  params: readonly NodeParamSpec[]
}

export const NODE_TYPED: Record<NodeType, NodeTypedSpec> = {
  agent: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": true}] as const,
    outputPorts: [{"name": "response", "type": "text", "description": "", "optional": false}] as const,
    params: [{"name": "prompt", "type": "string", "description": "", "required": false, "widget": "textarea"}, {"name": "task", "type": "string", "description": "", "required": false, "widget": "textarea"}, {"name": "perRow", "type": "boolean", "description": "", "required": false, "widget": "switch", "default": false}, {"name": "rowTemplate", "type": "string", "description": "", "required": false, "widget": "textarea", "visible_if": {"perRow": true}}, {"name": "outputColumn", "type": "string", "description": "", "required": false, "widget": "text", "default": "_ai_response", "visible_if": {"perRow": true}}, {"name": "maxRows", "type": "number", "description": "Cap rows for per-row AI calls. Keep low (\u226410) for snappy demos.", "required": false, "widget": "number", "default": 5, "visible_if": {"perRow": true}}, {"name": "model", "type": "string", "description": "", "required": false, "widget": "text", "default": "gemini-2.5-flash"}, {"name": "emitPublishRow", "type": "boolean", "description": "Replace output rows with one Confluence-ready {title, body_markdown} row.", "required": false, "widget": "switch", "default": false}, {"name": "pageTitle", "type": "string", "description": "", "required": false, "widget": "text", "visible_if": {"emitPublishRow": true}}] as const,
  },
  api_trigger: {
    inputPorts: [] as const,
    outputPorts: [{"name": "payload", "type": "object", "description": "", "optional": false}] as const,
    params: [{"name": "path", "type": "string", "description": "Webhook path", "required": false, "widget": "text", "default": "/webhook"}] as const,
  },
  code: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "Table rows from the upstream node.", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "Transformed rows produced by your Starlark script.", "optional": false}] as const,
    params: [{"name": "code_summary", "type": "string", "description": "Plain-language explanation of what the Starlark script does (for non-technical readers). Usually filled by the AI when code is generated.", "required": false, "widget": "textarea"}, {"name": "code", "type": "code", "description": "", "required": true, "widget": "starlark"}] as const,
  },
  condition: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "true_branch", "type": "dataframe", "description": "", "optional": false}, {"name": "false_branch", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "expression", "type": "expression", "description": "", "required": true, "widget": "code"}] as const,
  },
  confluence_mcp: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": true}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "serverUrl", "type": "string", "description": "Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL).", "required": false, "widget": "text"}, {"name": "confluenceSiteUrl", "type": "string", "description": "Confluence site URL (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "ATLASSIAN_SITE_URL"}, {"name": "confluenceEmail", "type": "string", "description": "Confluence account email (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "ATLASSIAN_EMAIL"}, {"name": "confluenceApiToken", "type": "string", "description": "Confluence API token (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "ATLASSIAN_API_TOKEN"}, {"name": "confluenceSpaceKey", "type": "string", "description": "Confluence space key (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "CONFLUENCE_SPACE_KEY"}, {"name": "pageTitle", "type": "string", "description": "Confluence page title override (defaults to generated name).", "required": false, "widget": "text"}, {"name": "tool", "type": "enum", "description": "Confluence MCP tool to invoke.", "required": true, "widget": "select", "default": "confluence_publish_report", "enum": ["confluence_search_pages", "confluence_extract_action_items", "confluence_publish_report", "studio_publish_architecture_doc"]}, {"name": "params", "type": "json", "description": "Tool arguments (JSON). Upstream rows are passed as params.data automatically.", "required": false, "widget": "json"}] as const,
  },
  csv_extract: {
    inputPorts: [] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false, "store_at": "datasets.<source>"}] as const,
    params: [{"name": "source", "type": "enum", "description": "Dataset id", "required": true, "widget": "select", "enum": ["leads.csv", "products.csv", "orders.csv", "hs_trades", "hs_alerts", "hs_orders", "hs_exec", "market_ticks", "comms_messages"]}, {"name": "limit", "type": "number", "description": "Row limit (optional)", "required": false, "widget": "number"}] as const,
  },
  csv_output: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "csv", "type": "text", "description": "", "optional": false}] as const,
    params: [{"name": "filename", "type": "string", "description": "", "required": true, "widget": "text", "default": "output.csv"}] as const,
  },
  data_merge: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "strategy", "type": "enum", "description": "", "required": true, "widget": "select", "default": "concat", "enum": ["concat", "union"]}] as const,
  },
  db_query: {
    inputPorts: [] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "query", "type": "string", "description": "SELECT * FROM comms_messages LIMIT 20", "required": true, "widget": "textarea"}, {"name": "source", "type": "enum", "description": "Source dataset", "required": false, "widget": "select", "enum": ["leads.csv", "products.csv", "orders.csv", "hs_trades", "hs_alerts", "hs_orders", "hs_exec", "market_ticks", "comms_messages"]}] as const,
  },
  deduplicate: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "key", "type": "string", "description": "", "required": true, "widget": "text"}] as const,
  },
  evaluator: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "criteria", "type": "expression", "description": "", "required": true, "widget": "code"}, {"name": "label", "type": "string", "description": "", "required": true, "widget": "text", "default": "passed"}] as const,
  },
  excel_output: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "file", "type": "object", "description": "", "optional": false}] as const,
    params: [{"name": "filename", "type": "string", "description": "", "required": true, "widget": "text", "default": "output.xlsx"}, {"name": "tabNames", "type": "string", "description": "", "required": false, "widget": "text"}, {"name": "highlightColumn", "type": "string", "description": "", "required": false, "widget": "text"}, {"name": "highlightMapping", "type": "string", "description": "", "required": false, "widget": "text"}] as const,
  },
  filter: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "expression", "type": "expression", "description": "", "required": true, "widget": "code"}] as const,
  },
  function: {
    inputPorts: [{"name": "any", "type": "any", "description": "", "optional": true}] as const,
    outputPorts: [{"name": "any", "type": "any", "description": "", "optional": false}] as const,
    params: [{"name": "code", "type": "code", "description": "", "required": true, "widget": "code"}] as const,
  },
  github: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": true}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "action", "type": "enum", "description": "", "required": true, "widget": "select", "default": "list-repos", "enum": ["list-repos", "list-issues", "list-prs", "list-commits", "get-repo", "create-issue", "push-file"]}, {"name": "repo", "type": "string", "description": "", "required": true, "widget": "text", "visible_if": {"action": ["list-issues", "list-prs", "list-commits", "get-repo", "create-issue", "push-file"]}}, {"name": "state", "type": "enum", "description": "", "required": true, "widget": "select", "default": "open", "enum": ["open", "closed", "all"], "visible_if": {"action": ["list-issues", "list-prs"]}}, {"name": "title", "type": "string", "description": "", "required": true, "widget": "text", "visible_if": {"action": "create-issue"}}, {"name": "body", "type": "string", "description": "", "required": true, "widget": "textarea", "visible_if": {"action": "create-issue"}}, {"name": "labels", "type": "string", "description": "", "required": true, "widget": "text", "visible_if": {"action": "create-issue"}}, {"name": "filePath", "type": "string", "description": "", "required": true, "widget": "text", "visible_if": {"action": "push-file"}}, {"name": "fileContent", "type": "string", "description": "", "required": true, "widget": "textarea", "visible_if": {"action": "push-file"}}, {"name": "fileFormat", "type": "enum", "description": "", "required": true, "widget": "select", "default": "json", "enum": ["json", "csv"], "visible_if": {"action": "push-file"}}, {"name": "branch", "type": "string", "description": "", "required": true, "widget": "text", "default": "main", "visible_if": {"action": "push-file"}}, {"name": "commitMessage", "type": "string", "description": "", "required": true, "widget": "text", "visible_if": {"action": "push-file"}}] as const,
  },
  github_mcp: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": true}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "serverUrl", "type": "string", "description": "Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL).", "required": false, "widget": "text"}, {"name": "githubToken", "type": "string", "description": "GitHub PAT (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "GITHUB_TOKEN"}, {"name": "githubRepo", "type": "string", "description": "Target repository (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "GITHUB_REPO"}, {"name": "tool", "type": "enum", "description": "GitHub MCP tool to invoke.", "required": true, "widget": "select", "default": "github_implement_fixes", "enum": ["github_implement_fixes", "github_fix_jira_and_update"]}, {"name": "params", "type": "json", "description": "Tool arguments (JSON). Upstream rows are passed as params.data automatically.", "required": false, "widget": "json"}] as const,
  },
  group_by: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "groupBy", "type": "string", "description": "", "required": true, "widget": "text"}, {"name": "aggregateCol", "type": "string", "description": "", "required": true, "widget": "text"}, {"name": "aggregateFn", "type": "enum", "description": "", "required": true, "widget": "select", "default": "sum", "enum": ["sum", "avg", "min", "max", "count"]}, {"name": "alias", "type": "string", "description": "", "required": false, "widget": "text"}] as const,
  },
  http: {
    inputPorts: [] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "url", "type": "string", "description": "", "required": true, "widget": "text"}, {"name": "method", "type": "enum", "description": "", "required": true, "widget": "select", "default": "GET", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]}, {"name": "headers", "type": "json", "description": "", "required": false, "widget": "json"}, {"name": "body", "type": "string", "description": "", "required": false, "widget": "textarea"}] as const,
  },
  jira_mcp: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": true}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "serverUrl", "type": "string", "description": "Optional bridge URL override (default http://127.0.0.1:8765 or MCP_SERVER_URL).", "required": false, "widget": "text"}, {"name": "jiraSiteUrl", "type": "string", "description": "Jira site URL (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "ATLASSIAN_SITE_URL"}, {"name": "jiraEmail", "type": "string", "description": "Jira account email (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "ATLASSIAN_EMAIL"}, {"name": "jiraApiToken", "type": "string", "description": "Jira API token (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "ATLASSIAN_API_TOKEN"}, {"name": "jiraProjectKey", "type": "string", "description": "Jira project key (from backend/.env \u2014 locked).", "required": false, "widget": "locked_env", "locked_from_env": true, "env_key": "JIRA_PROJECT_KEY"}, {"name": "tool", "type": "enum", "description": "Jira MCP tool to invoke.", "required": true, "widget": "select", "default": "jira_create_issue", "enum": ["jira_create_issue", "jira_list_issues", "jira_create_epics_from_confluence", "tasks_bulk_create"]}, {"name": "params", "type": "json", "description": "Tool arguments (JSON). Upstream rows are passed as params.data automatically.", "required": false, "widget": "json"}] as const,
  },
  join: {
    inputPorts: [{"name": "left", "type": "dataframe", "description": "", "optional": false}, {"name": "right", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "leftKey", "type": "string", "description": "", "required": true, "widget": "text"}, {"name": "rightKey", "type": "string", "description": "", "required": true, "widget": "text"}, {"name": "joinType", "type": "enum", "description": "", "required": true, "widget": "select", "default": "inner", "enum": ["inner", "left", "right", "outer"]}] as const,
  },
  loop: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "maxIterations", "type": "number", "description": "", "required": true, "widget": "number", "default": 1000}] as const,
  },
  manual_trigger: {
    inputPorts: [] as const,
    outputPorts: [{"name": "payload", "type": "object", "description": "", "optional": false, "store_at": "alert_payload"}] as const,
    params: [] as const,
  },
  map_transform: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "mappings", "type": "json", "description": "[{ to: 'revenue', expression: 'row.qty * row.price' }, { from: 'old', to: 'new' }]", "required": true, "widget": "json"}] as const,
  },
  note: {
    inputPorts: [] as const,
    outputPorts: [] as const,
    params: [{"name": "content", "type": "string", "description": "", "required": true, "widget": "textarea", "default": ""}] as const,
  },
  pause: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": true}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "durationMs", "type": "number", "description": "", "required": true, "widget": "number", "default": 500}] as const,
  },
  pdf_extract: {
    inputPorts: [] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "source", "type": "string", "description": "PDF filename", "required": true, "widget": "text", "default": "default"}] as const,
  },
  response: {
    inputPorts: [{"name": "any", "type": "any", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "response", "type": "text", "description": "", "optional": false}] as const,
    params: [{"name": "content", "type": "string", "description": "", "required": false, "widget": "textarea"}] as const,
  },
  router: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "expression", "type": "expression", "description": "", "required": true, "widget": "code"}] as const,
  },
  schedule: {
    inputPorts: [] as const,
    outputPorts: [{"name": "payload", "type": "object", "description": "", "optional": false}] as const,
    params: [{"name": "cron", "type": "string", "description": "Cron expression", "required": true, "widget": "text", "default": "0 * * * *"}] as const,
  },
  select_columns: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "columns", "type": "string", "description": "", "required": true, "widget": "text"}] as const,
  },
  sort: {
    inputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    outputPorts: [{"name": "rows", "type": "dataframe", "description": "", "optional": false}] as const,
    params: [{"name": "sortBy", "type": "string", "description": "", "required": true, "widget": "text"}, {"name": "order", "type": "enum", "description": "", "required": true, "widget": "select", "default": "asc", "enum": ["asc", "desc"]}] as const,
  },
  webhook_trigger: {
    inputPorts: [] as const,
    outputPorts: [{"name": "payload", "type": "object", "description": "", "optional": false}] as const,
    params: [{"name": "secret", "type": "string", "description": "Optional shared secret", "required": false, "widget": "text"}] as const,
  },
}
