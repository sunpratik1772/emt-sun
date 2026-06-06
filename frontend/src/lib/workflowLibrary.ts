import { api } from '../services/api'
import type { Workflow } from '../types'

/** Mirrors GET /workflows/catalog — one canonical display name per library row. */
export type WorkflowCatalogEntry = {
  canonical_name: string
  filename: string
  kind: 'saved' | 'draft'
  workflow_id: string | null
  updated_ms: number
}

export type WorkflowCatalogResolve = {
  action: 'load' | 'not_found'
  query: string
  canonical_name?: string
  filename?: string
  kind?: 'saved' | 'draft'
  workflow?: Workflow
}

const QUOTED_NAME_RE = /"([^"]{2,})"/g

export function extractQuotedWorkflowNames(text: string): string[] {
  const out: string[] = []
  for (const m of (text || '').matchAll(QUOTED_NAME_RE)) {
    const name = m[1]?.trim()
    if (name && !out.includes(name)) out.push(name)
  }
  return out
}

export function catalogCanonicalNames(entries: WorkflowCatalogEntry[]): string[] {
  return entries.map((e) => e.canonical_name).filter(Boolean)
}

export function catalogNameKey(name: string): string {
  return name.trim().toLowerCase()
}

export function catalogHasExactName(
  entries: WorkflowCatalogEntry[],
  name: string,
): boolean {
  const key = catalogNameKey(name)
  if (!key) return false
  return entries.some((e) => catalogNameKey(e.canonical_name) === key)
}

/** Same resolver the agent harness uses — GET /workflows/resolve. */
export async function resolveWorkflowFromCatalog(
  name: string,
): Promise<WorkflowCatalogResolve> {
  const q = name.trim()
  if (!q) return { action: 'not_found', query: q }
  return api.resolveWorkflowByName(q)
}

/** Load workflow JSON by display name, or null when not in catalog. */
export async function loadWorkflowFromCatalog(name: string): Promise<{
  canonicalName: string
  workflow: Workflow
} | null> {
  const resolved = await resolveWorkflowFromCatalog(name)
  if (resolved.action !== 'load' || !resolved.workflow || !resolved.canonical_name) {
    return null
  }
  return {
    canonicalName: resolved.canonical_name,
    workflow: {
      ...resolved.workflow,
      name: resolved.canonical_name,
    },
  }
}

/** Pick the first quoted name in a message that resolves via the catalog. */
export async function resolveFirstQuotedWorkflowInMessage(
  message: string,
): Promise<{ quoted: string; canonicalName: string; workflow: Workflow } | null> {
  for (const quoted of extractQuotedWorkflowNames(message)) {
    const loaded = await loadWorkflowFromCatalog(quoted)
    if (loaded) {
      return { quoted, canonicalName: loaded.canonicalName, workflow: loaded.workflow }
    }
  }
  return null
}
