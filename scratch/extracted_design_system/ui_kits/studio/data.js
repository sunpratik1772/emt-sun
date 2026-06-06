/* Mock data for the dbSherpa Studio recreation.
   Mirrors frontend/src/components/dashboard/mockData.ts + nodes/generated.ts. */

/* ── Node registry (verbatim colors/icons/groups from nodes/generated.ts) ── */
window.PALETTE_SECTIONS = [
  { id: 'triggers', label: 'Triggers', color: '#0EA5E9' },
  { id: 'data', label: 'Data', color: '#10B981' },
  { id: 'transform', label: 'Transform', color: '#6366F1' },
  { id: 'logic', label: 'Logic', color: '#F59E0B' },
  { id: 'integrations', label: 'Integrations', color: '#14B8A6' },
  { id: 'ai', label: 'AI', color: '#8B5CF6' },
  { id: 'output', label: 'Output', color: '#EC4899' },
];

// type: [displayName, color, lucideIcon, group, description]
window.NODE_UI = {
  manual_trigger: ['Manual Trigger', '#7c3aed', 'play', 'triggers', 'Start workflow manually.'],
  api_trigger: ['API Trigger', '#7c3aed', 'webhook', 'triggers', 'Trigger via HTTP webhook.'],
  webhook_trigger: ['Webhook', '#7c3aed', 'zap', 'triggers', 'Listen for incoming webhooks.'],
  schedule: ['Schedule', '#7c3aed', 'clock', 'triggers', 'Run on a cron schedule.'],
  db_query: ['DB Query', '#0ea5e9', 'database', 'data', 'Run a SELECT against an Oracle-backed dataset.'],
  csv_extract: ['Data Extract', '#0ea5e9', 'table-2', 'data', 'Load rows from a dataset.'],
  http: ['HTTP Request', '#0ea5e9', 'globe', 'data', 'Fetch data from any HTTP URL.'],
  pdf_extract: ['PDF Extract', '#0ea5e9', 'file-text', 'data', 'Extract text from a PDF.'],
  filter: ['Filter', '#f59e0b', 'filter', 'transform', 'Filter rows by an expression.'],
  sort: ['Sort', '#f59e0b', 'arrow-up-down', 'transform', 'Sort rows by a column.'],
  group_by: ['Group By', '#f59e0b', 'bar-chart-3', 'transform', 'Aggregate rows by a column.'],
  join: ['Join', '#f59e0b', 'merge', 'transform', 'Join two upstream datasets.'],
  map_transform: ['Map / Transform', '#f59e0b', 'wand-2', 'transform', 'Rename or compute columns.'],
  select_columns: ['Select Columns', '#f59e0b', 'columns', 'transform', 'Pick a subset of columns.'],
  deduplicate: ['Deduplicate', '#f59e0b', 'copy', 'transform', 'Remove duplicate rows by key.'],
  data_merge: ['Merge', '#f59e0b', 'layers', 'transform', 'Concatenate or union datasets.'],
  csv_output: ['CSV Output', '#f59e0b', 'download', 'transform', 'Serialize rows to a CSV string.'],
  code: ['Transform (Starlark)', '#06b6d4', 'code-2', 'logic', 'Run sandboxed Starlark on rows.'],
  condition: ['Condition', '#06b6d4', 'git-branch', 'logic', 'Branch rows by an expression.'],
  router: ['Router', '#06b6d4', 'share-2', 'logic', 'Route rows to labelled branches.'],
  loop: ['Loop', '#06b6d4', 'refresh-cw', 'logic', 'Iterate over rows.'],
  pause: ['Pause', '#06b6d4', 'pause-circle', 'logic', 'Wait before continuing.'],
  function: ['Function', '#06b6d4', 'function-square', 'logic', 'Run Python with input/output.'],
  jira_mcp: ['Jira MCP', '#0052CC', 'ticket', 'integrations', 'Create issues, list tickets, epics.'],
  confluence_mcp: ['Confluence MCP', '#172B4D', 'scroll-text', 'integrations', 'Search pages, publish reports.'],
  github_mcp: ['GitHub MCP', '#24292F', 'git-pull-request', 'integrations', 'Implement fixes, open PRs.'],
  github: ['GitHub', '#24292e', 'git-branch', 'integrations', 'GitHub API actions.'],
  agent: ['AI Agent', '#8b5cf6', 'bot', 'ai', 'Call Gemini with rows + prompt.'],
  evaluator: ['Evaluator', '#8b5cf6', 'check-square', 'ai', 'Evaluate rows; report pass/fail rate.'],
  excel_output: ['Excel Export', '#16a34a', 'file-spreadsheet', 'output', 'Write multi-tab Excel.'],
  response: ['Response', '#b45309', 'arrow-right', 'output', 'Return a final workflow response.'],
  note: ['Note', '#475569', 'sticky-note', 'output', 'Canvas comment / annotation.'],
};

/* ── A sample workflow DAG for the canvas (status reflects a recent run) ── */
window.WORKFLOW = {
  name: 'Lead scoring pipeline',
  nodes: [
    { id: 'n1', type: 'manual_trigger', label: 'Start run',       x: 40,  y: 60,  status: 'ok',      ms: 12 },
    { id: 'n2', type: 'db_query',       label: 'Load leads',      x: 40,  y: 210, status: 'ok',      ms: 340, tags: ['leads.csv'] },
    { id: 'n3', type: 'filter',         label: 'Score ≥ 70',      x: 360, y: 210, status: 'ok',      ms: 28,  tags: ['row.score >= 70'] },
    { id: 'n4', type: 'agent',          label: 'Summarize lead',  x: 680, y: 120, status: 'running', ms: 1840, idx: 4, total: 6 },
    { id: 'n5', type: 'jira_mcp',       label: 'Create tickets',  x: 680, y: 300, status: 'idle' },
    { id: 'n6', type: 'excel_output',   label: 'Export report',   x: 1000, y: 210, status: 'idle',   tags: ['→ leads.xlsx'] },
  ],
  edges: [
    { from: 'n1', to: 'n2', state: 'done' },
    { from: 'n2', to: 'n3', state: 'done' },
    { from: 'n3', to: 'n4', state: 'running' },
    { from: 'n3', to: 'n5', state: 'idle' },
    { from: 'n4', to: 'n6', state: 'idle' },
    { from: 'n5', to: 'n6', state: 'idle' },
  ],
};

/* ── Agent (sherpa copilot) sample thread ── */
window.AGENT_THREAD = [
  { role: 'user', text: 'Build a workflow that loads leads, keeps the high scorers, summarizes each with AI, and files Jira tickets.' },
  { role: 'thinking', steps: [
    { kind: 'plan', label: 'Planning workflow', detail: 'Trigger → DB query → filter → agent → Jira MCP → Excel' },
    { kind: 'build', label: 'Adding 6 nodes', detail: 'Wiring ports and validating contracts' },
    { kind: 'check', label: 'Validating', detail: 'All ports typed · no cycles' },
  ] },
  { role: 'assistant', text: 'Done — I built **Lead scoring pipeline** with 6 nodes. It loads `leads.csv`, filters to `score ≥ 70`, summarizes each lead with the AI Agent, then creates Jira tickets and exports an Excel report. Hit **Run** to try it with sample data.' },
];

window.AGENT_ROUTES = [
  { command: '/run', label: 'Run with sample data' },
  { command: '/build', label: 'Generate a workflow' },
  { command: '/check-run', label: 'Explain last run' },
  { command: '/fix', label: 'Fix validation errors' },
];

/* ── Run history ── */
window.RUNS = [
  { id: 'r1', wf: 'Lead scoring pipeline', status: 'success', when: '2h ago', dur: '3.2s', nodes: 6, rows: 248 },
  { id: 'r2', wf: 'Daily data sync', status: 'error', when: '5h ago', dur: '1.1s', nodes: 5, rows: 0, err: 'db_query: source not found' },
  { id: 'r3', wf: 'Quarterly report generator', status: 'success', when: '1d ago', dur: '8.7s', nodes: 11, rows: 1204 },
  { id: 'r4', wf: 'Lead scoring pipeline', status: 'success', when: '1d ago', dur: '3.0s', nodes: 6, rows: 240 },
  { id: 'r5', wf: 'Trade anomaly detection', status: 'success', when: '2d ago', dur: '5.4s', nodes: 9, rows: 512 },
  { id: 'r6', wf: 'Daily data sync', status: 'success', when: '2d ago', dur: '1.4s', nodes: 5, rows: 96 },
  { id: 'r7', wf: 'Quarterly report generator', status: 'running', when: 'now', dur: '—', nodes: 11, rows: null },
];

/* ── Automations (scheduled workflows) ── */
window.AUTOMATIONS = [
  { id: 'a1', wf: 'Daily data sync', cron: '0 6 * * *', human: 'Every day at 6:00 AM', active: true, last: 'Succeeded 5h ago', next: 'in 19h' },
  { id: 'a2', wf: 'Quarterly report generator', cron: '0 9 1 */3 *', human: 'First of every quarter, 9:00 AM', active: true, last: 'Succeeded 1d ago', next: 'in 12d' },
  { id: 'a3', wf: 'Trade anomaly detection', cron: '*/30 * * * *', human: 'Every 30 minutes', active: false, last: 'Paused', next: '—' },
];

window.STUDIO_DATA = {
  user: { name: 'John', initials: 'JD' },
  nav: [
    { id: 'dashboard', label: 'Dashboard', icon: 'layout-grid' },
    { id: 'workflow', label: 'Workflow', icon: 'workflow' },
    { id: 'agent', label: 'Sherpa Copilot', icon: 'sparkles' },
    { id: 'nodes', label: 'Node Library', icon: 'boxes' },
    { id: 'runs', label: 'Run History', icon: 'activity' },
    { id: 'automations', label: 'Automations', icon: 'zap' },
    { id: 'data', label: 'Data Sources', icon: 'database' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
  ],
  suggestions: [
    'Create an Excel report from orders.csv with sorted top contributors.',
    'Run "Trade Anomaly Detection" with sample alert context.',
    'Flag accounts with attrition risk by office.',
  ],
  stats: [
    { label: 'Workflows', value: '4', sub: '2 drafts ready to open', spark: [4,5,5,7,6,8,8], up: false },
    { label: 'Runs this month', value: '12', sub: '+2 vs last month', spark: [2,4,3,6,8,9,12], up: true },
    { label: 'Automations', value: '2', sub: '2 scheduled — on autopilot', spark: [0,1,1,1,2,2,2], up: false },
  ],
  health: { rate: '92%', summary: '12 runs · 1 failed', online: true,
    heat: [1,3,2,0,4,1,2, 2,1,3,0,1,4,2, 0,2,1,3,1,0,2] },
  workflows: [
    { id: 'leads', name: 'Lead scoring pipeline', time: '2h ago', status: 'success',
      statusLabel: 'Succeeded 2h ago', nodes: 8, chips: ['DB query','Agent','Jira MCP'] },
    { id: 'sync', name: 'Daily data sync', time: '5h ago', status: 'error',
      statusLabel: 'Failed 5h ago', nodes: 5, chips: ['CSV extract','Transform','Output'] },
    { id: 'report', name: 'Quarterly report generator', time: '1d ago', status: 'success',
      statusLabel: 'Succeeded 1d ago', nodes: 11, chips: ['DB query','Agent','Sheets'] },
    { id: 'draft', name: 'Untitled workflow', time: '1d ago', status: 'draft',
      statusLabel: 'Not run yet', nodes: 2, chips: ['Trigger','Agent'], draft: true },
  ],
};
