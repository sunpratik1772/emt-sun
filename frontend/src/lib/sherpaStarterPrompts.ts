import {
  catalogCanonicalNames,
  catalogHasExactName,
  catalogNameKey,
  type WorkflowCatalogEntry,
} from './workflowLibrary'

export type CopilotDraftRequest = {
  text: string
  autoSend?: boolean
}

export type SherpaStarterPrompt = {
  label: string
  text: string
  fromAi: boolean
}

const TAG_FALLBACKS: Record<string, string> = {
  excel: 'Create an Excel report from orders.csv with sorted top contributors.',
  csv: 'Load leads.csv, filter high-risk rows, and export a CSV summary.',
  github: 'Use github_mcp (github_list_commits), summarize with agent (emitPublishRow), publish via confluence_mcp.',
  mcp: 'Publish a Confluence digest via confluence_mcp after processing hs_trades.',
}

const DISCOVERY_ASK_FALLBACKS: SherpaStarterPrompt[] = [
  {
    label: 'export',
    text: 'How do I export workflow results to CSV or Excel?',
    fromAi: false,
  },
  {
    label: 'nodes',
    text: 'Which node types are best for filtering, branching, and exporting data?',
    fromAi: false,
  },
  {
    label: 'data',
    text: 'What data sources are available in Studio, and how do I load one into a workflow?',
    fromAi: false,
  },
  {
    label: 'integrations',
    text: 'How do I decide between CSV, Excel, and MCP publishing outputs?',
    fromAi: false,
  },
  {
    label: 'build',
    text: 'What can I build with the nodes and data sources available in Studio?',
    fromAi: false,
  },
  {
    label: 'skills',
    text: 'Which surveillance or analytics skills can Sherpa use when building workflows?',
    fromAi: false,
  },
]

const VAGUE_SUGGESTION_PHRASES = [
  /\bfinish my draft\b/i,
  /\bconnect the open nodes\b/i,
  /\badd a csv export at the end\b/i,
  /\bwire (up )?(the )?nodes\b/i,
  /\bconnect the nodes\b/i,
  /\bfinish (my |the )?(draft |unfinished )?workflow\b/i,
  /\bcomplete (my |the )?draft\b/i,
  /\bopen nodes\b/i,
  /\bedit this workflow\b/i,
  /\bthis workflow on (the )?canvas\b/i,
  /\bthe workflow on (the )?canvas\b/i,
]

const WORKFLOW_ACTION_RE =
  /\b(improve|edit|extend|review|run|load|fix|automate|analy[sz]e|summari[zs]e)\b/i
const RUN_ANALYSIS_RE =
  /\b(review|analy[sz]e|summari[zs]e|check-?run|latest run|last run|run summary|execution summary|reliability|suggest.*change|did it analy[sz]e|analy[sz]ed the last run)\b/i
const EDIT_WORKFLOW_RE =
  /\b(improve|edit|extend|fix|connect|finish|complete|wire|follow-?up|automate)\b/i
const QUOTED_NAME_RE = /"([^"]{2,})"/g

export function isVagueSherpaSuggestion(text: string): boolean {
  const t = text.trim()
  if (!t) return true
  if (VAGUE_SUGGESTION_PHRASES.some((re) => re.test(t))) return true

  const quoted = /"[^"]{3,}"/.test(t)
  const dataset =
    /\b[a-z][a-z0-9_]*\.(csv|json|xlsx|yaml)\b/i.test(t) || /\bhs_[a-z0-9_]+\b/i.test(t)
  const integration = /\b(outlook|github|confluence|teams|jira|excel|mcp)\b/i.test(t)
  const artifact = /\b(csv|excel|xlsx|report|digest|briefing|surveillance)\b/i.test(t)
  const specificity = [quoted, dataset, integration, artifact].filter(Boolean).length

  if (/\b(finish|complete|connect|wire)\b/i.test(t) && /\b(workflow|draft|nodes)\b/i.test(t)) {
    if (!quoted && specificity < 2) return true
  }

  if (specificity === 0 && t.length < 72) return true

  return false
}

export function filterConcreteSherpaPrompts(prompts: SherpaStarterPrompt[]): SherpaStarterPrompt[] {
  return prompts.filter((p) => !isVagueSherpaSuggestion(p.text))
}

export type SherpaDashboardContext = {
  savedCount: number
  draftCount: number
  runsThisMonth: number
  /** Canonical library names — same source as GET /workflows/catalog and harness resolve. */
  catalog: WorkflowCatalogEntry[]
  workflowsWithRuns: string[]
}

export type SherpaStarterContext = SherpaDashboardContext & {
  hasCanvasWorkflow?: boolean
}

/** @deprecated Use catalog canonical names — kept for tests migrating off topWorkflowNames. */
export function topWorkflowNamesFromContext(ctx?: SherpaStarterContext): string[] {
  return catalogCanonicalNames(ctx?.catalog ?? [])
}

export function isSherpaWorkspaceEmpty(ctx?: SherpaStarterContext): boolean {
  if (!ctx) return false
  return (ctx.catalog?.length ?? 0) === 0
}

function workflowsWithRunsSet(ctx?: SherpaStarterContext): Set<string> {
  const names = new Set<string>()
  if (!ctx) return names
  for (const n of ctx.workflowsWithRuns ?? []) {
    const t = catalogNameKey(n)
    if (t) names.add(t)
  }
  return names
}

export function canSuggestWorkflowEdits(ctx?: SherpaStarterContext): boolean {
  if (!ctx || isSherpaWorkspaceEmpty(ctx)) return false
  return (ctx.catalog?.length ?? 0) > 0
}

export function canSuggestRunReview(ctx?: SherpaStarterContext): boolean {
  return topWorkflowWithRuns(ctx) !== undefined
}

function topWorkflowWithRuns(ctx?: SherpaStarterContext): string | undefined {
  if (!ctx) return undefined
  const withRuns = workflowsWithRunsSet(ctx)
  if (!withRuns.size || !ctx.catalog?.length) return undefined
  for (const entry of ctx.catalog) {
    const key = catalogNameKey(entry.canonical_name)
    if (withRuns.has(key)) return entry.canonical_name
  }
  for (const name of ctx.workflowsWithRuns ?? []) {
    if (catalogHasExactName(ctx.catalog, name)) return name
  }
  return undefined
}

/** Drop prompts that quote workflow names absent from the canonical catalog. */
export function referencesMissingWorkflow(text: string, ctx?: SherpaStarterContext): boolean {
  const t = text.trim()
  if (!t) return true
  const catalog = ctx?.catalog ?? []

  if (isSherpaWorkspaceEmpty(ctx)) {
    if (WORKFLOW_ACTION_RE.test(t) || RUN_ANALYSIS_RE.test(t) || EDIT_WORKFLOW_RE.test(t)) {
      return true
    }
  }

  if (/\b(this workflow|the workflow on (the )?canvas|edit this workflow)\b/i.test(t)) {
    return true
  }

  if (EDIT_WORKFLOW_RE.test(t) && !canSuggestWorkflowEdits(ctx)) return true

  if (RUN_ANALYSIS_RE.test(t)) {
    if (!canSuggestRunReview(ctx)) return true
    const withRuns = workflowsWithRunsSet(ctx)
    for (const m of t.matchAll(QUOTED_NAME_RE)) {
      const key = catalogNameKey(m[1])
      if (!catalogHasExactName(catalog, m[1]) || !withRuns.has(key)) return true
    }
    if (!QUOTED_NAME_RE.test(t)) return true
    return false
  }

  if (!WORKFLOW_ACTION_RE.test(t)) return false

  if (!catalog.length) return true

  for (const m of t.matchAll(QUOTED_NAME_RE)) {
    if (!catalogHasExactName(catalog, m[1])) return true
  }

  if (/\b(run|load|improve|fix|automate)\b/i.test(t) && !QUOTED_NAME_RE.test(t)) {
    return true
  }

  return false
}

export function filterPromptsForWorkspace(
  prompts: SherpaStarterPrompt[],
  ctx?: SherpaStarterContext,
): SherpaStarterPrompt[] {
  return filterConcreteSherpaPrompts(prompts).filter(
    (p) => !referencesMissingWorkflow(p.text, ctx),
  )
}

function rowToPrompt(row: { text: string; tag?: string }, fromAi: boolean): SherpaStarterPrompt {
  const text = row.text.trim()
  const tag = row.tag?.trim().toLowerCase()
  return {
    label: tag || shortenLabel(text),
    text,
    fromAi,
  }
}

export function resolveStarterPrompts(
  build: Array<{ text: string; tag?: string }> = [],
  ask: Array<{ text: string; tag?: string }> = [],
  limit = 5,
  opts?: { allowRegistryFallbacks?: boolean },
): SherpaStarterPrompt[] {
  const rows: SherpaStarterPrompt[] = []

  for (let i = 0; i < 4 && rows.length < limit; i += 1) {
    if (build[i]?.text?.trim()) {
      rows.push(rowToPrompt(build[i], true))
    }
    if (ask[i]?.text?.trim() && rows.length < limit) {
      rows.push(rowToPrompt(ask[i], true))
    }
  }

  if (rows.length > 0) return filterConcreteSherpaPrompts(rows).slice(0, limit)

  if (opts?.allowRegistryFallbacks === false) return []

  return Object.entries(TAG_FALLBACKS)
    .slice(0, limit)
    .map(([tag, text]) => ({
      label: tag,
      text,
      fromAi: false,
    }))
}

export function buildSherpaStarterContext(
  catalog: WorkflowCatalogEntry[],
  runLogs: Array<{ started_at: string; workflow?: string; status?: string }>,
  opts?: { hasCanvasWorkflow?: boolean },
): SherpaStarterContext {
  const now = new Date()
  const runsThisMonth = runLogs.filter((r) => {
    const t = Date.parse(r.started_at)
    if (!Number.isFinite(t)) return false
    const d = new Date(t)
    return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()
  }).length

  const catalogKeys = new Set(catalog.map((e) => catalogNameKey(e.canonical_name)))
  const runNames = runLogs
    .map((r) => (r.workflow || '').replace(/\.json$/i, '').trim())
    .filter(Boolean)
  const workflowsWithRuns = [...new Set(runNames)]
    .filter((n) => catalogKeys.has(catalogNameKey(n)))
    .slice(0, 8)

  return {
    savedCount: catalog.filter((e) => e.kind === 'saved').length,
    draftCount: catalog.filter((e) => e.kind === 'draft').length,
    runsThisMonth,
    catalog,
    workflowsWithRuns,
    hasCanvasWorkflow: Boolean(opts?.hasCanvasWorkflow),
  }
}

function registryBuildFallbacks(limit: number): SherpaStarterPrompt[] {
  return Object.entries(TAG_FALLBACKS)
    .slice(0, limit)
    .map(([tag, text]) => ({
      label: tag,
      text,
      fromAi: false,
    }))
}

function discoveryFallbackPool(context?: SherpaStarterContext): SherpaStarterPrompt[] {
  const ask = [...DISCOVERY_ASK_FALLBACKS]
  const build = registryBuildFallbacks(8)
  if (isSherpaWorkspaceEmpty(context)) {
    return [...ask, ...build]
  }
  return [...build, ...ask]
}

export function ensureStarterPromptCount(
  prompts: SherpaStarterPrompt[],
  limit: number,
  context?: SherpaStarterContext,
): SherpaStarterPrompt[] {
  const out = filterPromptsForWorkspace(prompts, context)
  const seen = new Set(out.map((p) => p.text.toLowerCase()))

  for (const fallback of discoveryFallbackPool(context)) {
    if (out.length >= limit) break
    const key = fallback.text.toLowerCase()
    if (seen.has(key)) continue
    if (referencesMissingWorkflow(fallback.text, context)) continue
    if (isVagueSherpaSuggestion(fallback.text)) continue
    seen.add(key)
    out.push(fallback)
  }

  return out.slice(0, limit)
}

export function personalizeStarterPrompts(
  base: SherpaStarterPrompt[],
  context: SherpaStarterContext | undefined,
  limit: number,
): SherpaStarterPrompt[] {
  const picked: SherpaStarterPrompt[] = []
  const seen = new Set<string>()

  const push = (prompt: SherpaStarterPrompt) => {
    if (picked.length >= limit) return
    if (isVagueSherpaSuggestion(prompt.text)) return
    if (referencesMissingWorkflow(prompt.text, context)) return
    const key = prompt.text.toLowerCase()
    if (seen.has(key)) return
    seen.add(key)
    picked.push(prompt)
  }

  const empty = isSherpaWorkspaceEmpty(context)
  const top = context?.catalog?.[0]?.canonical_name
  const runTarget = topWorkflowWithRuns(context)
  const canEdit = canSuggestWorkflowEdits(context)

  if (!empty && canEdit && top) {
    push({
      label: 'extend',
      text: `Improve "${top}" with validation, a branch for failures, and a Confluence summary when the run completes.`,
      fromAi: false,
    })
  }

  if (!empty && canEdit && context && context.runsThisMonth === 0 && top) {
    push({
      label: 'run',
      text: `Run "${top}" with sample alert context and explain anything that fails.`,
      fromAi: false,
    })
  } else if (!empty && canEdit && runTarget) {
    push({
      label: 'iterate',
      text: `Review the latest run of "${runTarget}" and suggest one change to improve reliability.`,
      fromAi: false,
    })
  }

  for (const prompt of base) {
    push(prompt)
  }

  if (empty) {
    for (const prompt of DISCOVERY_ASK_FALLBACKS) {
      push(prompt)
    }
    for (const prompt of registryBuildFallbacks(limit)) {
      push(prompt)
    }
  }

  return picked.slice(0, limit)
}

function shortenLabel(text: string, max = 42): string {
  const oneLine = text.replace(/\s+/g, ' ').trim()
  if (oneLine.length <= max) return oneLine
  return `${oneLine.slice(0, max - 1)}…`
}
