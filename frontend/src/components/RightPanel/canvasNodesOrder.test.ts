import { describe, it, expect } from 'vitest'
import type { WorkflowEdge, WorkflowNode } from '../../types'

/** Mirror of orderWorkflowNodes in CanvasNodesSummary for unit testing. */
function orderWorkflowNodes(nodes: WorkflowNode[], edges: WorkflowEdge[]): WorkflowNode[] {
  if (nodes.length === 0) return []
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const indegree = new Map<string, number>()
  for (const n of nodes) indegree.set(n.id, 0)
  for (const e of edges) {
    if (byId.has(e.from) && byId.has(e.to)) {
      indegree.set(e.to, (indegree.get(e.to) ?? 0) + 1)
    }
  }
  const queue = nodes.filter((n) => (indegree.get(n.id) ?? 0) === 0).map((n) => n.id)
  const ordered: WorkflowNode[] = []
  const seen = new Set<string>()
  while (queue.length > 0) {
    const id = queue.shift()!
    if (seen.has(id)) continue
    seen.add(id)
    const node = byId.get(id)
    if (node) ordered.push(node)
    for (const e of edges) {
      if (e.from !== id || !byId.has(e.to)) continue
      const next = (indegree.get(e.to) ?? 0) - 1
      indegree.set(e.to, next)
      if (next <= 0) queue.push(e.to)
    }
  }
  for (const n of nodes) {
    if (!seen.has(n.id)) ordered.push(n)
  }
  return ordered
}

describe('orderWorkflowNodes', () => {
  it('orders nodes by edge dependencies', () => {
    const nodes: WorkflowNode[] = [
      { id: 'a', type: 'sql', label: 'A', config: {} },
      { id: 'b', type: 'sql', label: 'B', config: {} },
      { id: 'c', type: 'sql', label: 'C', config: {} },
    ]
    const edges: WorkflowEdge[] = [
      { from: 'a', to: 'b' },
      { from: 'b', to: 'c' },
    ]
    expect(orderWorkflowNodes(nodes, edges).map((n) => n.id)).toEqual(['a', 'b', 'c'])
  })
})
