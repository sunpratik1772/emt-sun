import type { StoredWorkflow } from '../services/api'

export type WorkflowNameConflict = {
  filename: string
  name: string
  node_count?: number
  modified_ms?: number
}

export function normalizeWorkflowDisplayName(name: string): string {
  return name.trim().toLocaleLowerCase()
}

/** Saved workflows that already use this display name (excluding the file being written). */
export function findWorkflowNameConflicts(
  workflows: StoredWorkflow[],
  displayName: string,
  excludeFilename?: string | null,
): WorkflowNameConflict[] {
  const needle = normalizeWorkflowDisplayName(displayName)
  if (!needle) return []
  return workflows
    .filter((w) => {
      if (!w.filename || w.filename === excludeFilename) return false
      const existing = normalizeWorkflowDisplayName(w.name || '')
      return existing === needle
    })
    .map((w) => ({
      filename: w.filename,
      name: w.name || displayName,
      node_count: w.node_count,
      modified_ms: w.modified_ms,
    }))
}
