import { useMemo } from 'react'
import type { RunLogEntry, Workflow, WorkflowEdge, WorkflowNode } from '../../types'
import { ArcIcon, Layers } from '../../icons/arc'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType } from '../../nodes'
import type { OutputSummarySource } from '../../lib/openOutputPanel'
import { SectionHeader } from './Shell'

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

function sourceCaption(source: OutputSummarySource | null, refreshedAt: number | null): string {
  if (!source) return 'Nodes on the canvas right now.'
  const when =
    refreshedAt != null
      ? new Date(refreshedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
      : null
  const suffix = when ? ` · ${when}` : ''
  switch (source) {
    case 'save':
      return `Saved to library — refreshed node list${suffix}`
    case 'copilot':
      return `Sherpa updated the canvas — refreshed node list${suffix}`
    case 'run':
      return `Run in progress or finished — canvas stages${suffix}`
    default:
      return 'Nodes on the canvas right now.'
  }
}

function NodeSummaryCard({
  node,
  index,
  runEntry,
}: {
  node: WorkflowNode
  index: number
  runEntry?: RunLogEntry
}) {
  const meta = useNodeRegistryStore((s) => s.nodeUI[node.type as NodeType] ?? UNKNOWN_NODE_UI)
  const IconComp = meta.Icon
  const runTone =
    runEntry?.status === 'error'
      ? 'var(--danger)'
      : runEntry?.status === 'running'
        ? 'var(--running)'
        : runEntry?.status === 'ok'
          ? 'var(--success)'
          : null

  return (
    <div
      className="rounded overflow-hidden"
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--border-soft)',
      }}
    >
      <div className="w-full flex items-center gap-2 px-2.5 py-1.5">
        <span className="num" style={{ fontSize: 9.5, color: 'var(--text-3)', width: 16, textAlign: 'right' }}>
          {index}
        </span>
        {IconComp && meta && (
          <span
            className="shrink-0 flex items-center justify-center rounded"
            style={{ width: 18, height: 18, background: `${meta.color}14`, color: meta.color }}
          >
            <IconComp size={11} strokeWidth={2} />
          </span>
        )}
        <div className="flex-1 min-w-0">
          <div className="truncate" style={{ fontSize: 11.5, color: 'var(--text-0)', fontWeight: 500 }}>
            {node.label || node.id}
          </div>
          <div className="truncate num" style={{ fontSize: 10, color: 'var(--text-3)' }}>
            {node.type}
            {node.disabled ? ' · skipped' : ''}
          </div>
        </div>
        {runTone && runEntry && (
          <span className="num shrink-0" style={{ fontSize: 10, color: runTone, fontWeight: 600 }}>
            {runEntry.status === 'running' ? 'running…' : runEntry.status}
          </span>
        )}
      </div>
    </div>
  )
}

export interface CanvasNodesSummaryProps {
  workflow: Workflow | null
  source: OutputSummarySource | null
  refreshedAt: number | null
  runLog?: RunLogEntry[]
}

export function CanvasNodesSummary({ workflow, source, refreshedAt, runLog = [] }: CanvasNodesSummaryProps) {
  const ordered = useMemo(
    () => (workflow ? orderWorkflowNodes(workflow.nodes, workflow.edges) : []),
    [workflow],
  )
  const runByNode = useMemo(() => {
    const m = new Map<string, RunLogEntry>()
    for (const e of runLog) m.set(e.node_id, e)
    return m
  }, [runLog])

  if (!workflow || ordered.length === 0) {
    return (
      <div className="px-4 py-6 text-center" style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.55 }}>
        <ArcIcon icon={Layers} size={20} strokeWidth={1.6} style={{ color: 'var(--text-3)', marginBottom: 8 }} />
        <div style={{ fontWeight: 500, color: 'var(--text-1)', marginBottom: 4 }}>No nodes on canvas</div>
        <div>Add steps in Sherpa or drag nodes from the palette.</div>
      </div>
    )
  }

  return (
    <div className="px-3 pb-3">
      <div className="px-1 pt-3 pb-2">
        <SectionHeader accent="var(--text-1)">Canvas nodes</SectionHeader>
        <p style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.5, marginTop: -4 }}>
          {sourceCaption(source, refreshedAt)}
        </p>
        {workflow.name && (
          <p className="truncate mt-1" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
            {workflow.name} · {ordered.length} step{ordered.length === 1 ? '' : 's'}
          </p>
        )}
      </div>
      <div className="space-y-2">
        {ordered.map((node, i) => (
          <NodeSummaryCard
            key={node.id}
            node={node}
            index={i + 1}
            runEntry={runByNode.get(node.id)}
          />
        ))}
      </div>
    </div>
  )
}

/** Store-bound wrapper for OutputView. */
export default function CanvasNodesSummaryFromStore() {
  const workflow = useWorkflowStore((s) => s.workflow)
  const source = useWorkflowStore((s) => s.outputSummarySource)
  const refreshedAt = useWorkflowStore((s) => s.outputSummaryAt)
  const runLog = useWorkflowStore((s) => s.runLog)
  return (
    <CanvasNodesSummary
      workflow={workflow}
      source={source}
      refreshedAt={refreshedAt}
      runLog={runLog}
    />
  )
}
