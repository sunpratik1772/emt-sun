import type { WorkflowNode, NodeType } from '../../types'
import { getNodeDisplayName } from '../../nodes'

export function generateSessionId(): string {
  return 'sess-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)
}

export function nextNodeId(existing: WorkflowNode[]): string {
  let n = 1
  const seen = new Set(existing.map((x) => x.id))
  while (seen.has(`n${String(n).padStart(2, '0')}`)) n++
  return `n${String(n).padStart(2, '0')}`
}

export function defaultNodeLabel(type: NodeType, existing: WorkflowNode[]): string {
  const base = getNodeDisplayName(type)
  const sameType = existing.filter((n) => n.type === type).length
  return sameType > 0 ? `${base} ${sameType + 1}` : base
}
