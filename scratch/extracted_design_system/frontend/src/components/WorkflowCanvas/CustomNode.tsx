/**
 * Visual representation of a single node on the canvas.
 *
 * Pulls colour/icon from `nodeRegistryStore` (live node-manifest).
 * React.memo wraps the
 * component because React Flow re-renders on every drag frame; without
 * it a 30-node DAG drops below 60fps.
 *
 * Live run state (running / ok / error pulse) comes from
 * `useNodeRunStatus(id)`, which subscribes to SSE events the backend
 * pushes during /run/stream — so the graph animates as a workflow runs.
 */
import { memo, useMemo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { AlertTriangle } from '../../icons/arc'
import { getNodeDisplayName, useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType, type NodeUIMeta } from '../../nodes'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRunStatus } from '../../store/useNodeRunStatus'

interface NodeData {
  label: string
  nodeType: NodeType
  config: Record<string, unknown>
  disabled?: boolean
}

function formatMs(ms?: number): string {
  if (ms == null) return '0.0 s'
  if (ms < 1000) return `${(ms / 1000).toFixed(1)} s`
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`
}

const STATUS_COLOR: Record<string, string> = {
  idle: 'var(--border-strong)',
  running: 'var(--running)',
  ok: 'var(--success)',
  error: 'var(--danger)',
}

export const CustomNode = memo(({ id, data }: NodeProps<NodeData>) => {
  const meta: NodeUIMeta = useNodeRegistryStore((s) => s.nodeUI[data.nodeType] ?? UNKNOWN_NODE_UI)
  const IconComp = meta.Icon
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId)
  const selectNode = useWorkflowStore((s) => s.selectNode)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const run = useNodeRunStatus(id)

  const nodeValidationErrors = useMemo(
    () => validationIssues?.filter((issue) => issue.node_id === id && issue.severity === 'error') ?? [],
    [validationIssues, id],
  )
  const hasValidationError = nodeValidationErrors.length > 0

  const isSelected = selectedNodeId === id
  const isRunning = run.status === 'running'
  const isOk = run.status === 'ok'
  const isError = run.status === 'error'
  const hasRun = isRunning || isOk || isError

  const ringColor = STATUS_COLOR[run.status]

  // Border: run state > selection > rest.
  // Run-state borders take precedence so the user always sees what is live.
  const borderColor = isRunning
    ? 'var(--running)'
    : isOk
    ? 'var(--success)'
    : isError
    ? 'var(--danger)'
    : hasValidationError
    ? 'var(--danger)'
    : isSelected
    ? meta.color
    : 'var(--border)'

  // Flat cards — state via border only (no drop shadow).
  const boxShadow = isRunning
    ? '0 0 0 2px color-mix(in srgb, var(--running) 40%, transparent)'
    : isSelected
      ? `0 0 0 2px color-mix(in srgb, ${meta.color} 35%, transparent)`
      : 'none'

  const elapsed = isRunning ? run.live_ms : run.duration_ms

  const isDisabled = !!data.disabled

  return (
    <div
      onClick={() => {
        selectNode(id)
        useWorkflowStore.getState().setRightPanelMode('config')
      }}
      className="relative cursor-pointer"
      style={{
        width: 240,
        borderRadius: 10,
        background: 'var(--bg-node)',
        border: `1px solid ${borderColor}`,
        boxShadow,
        transition:
          'border-color 180ms var(--ease-out), box-shadow 180ms var(--ease-out), background 180ms var(--ease-out), opacity 180ms var(--ease-out)',
        zIndex: isRunning ? 10 : 1,
        opacity: isDisabled ? 0.5 : 1,
        filter: isDisabled ? 'grayscale(0.6)' : undefined,
      }}
    >
      {/* Hairline left accent (Railway-style identifier instead of full top stripe) */}
      <div
        aria-hidden
        className={isRunning ? 'scan-sweep relative overflow-hidden' : ''}
        style={{
          position: 'absolute',
          left: 0,
          top: 8,
          bottom: 8,
          width: 2,
          borderRadius: 2,
          background: isOk
            ? 'var(--success)'
            : isError
              ? 'var(--danger)'
              : isRunning
                ? 'var(--running)'
                : meta.color,
          opacity: isSelected || hasRun ? 0.95 : 0.55,
        }}
      />

      {/* Header row */}
      <div className="flex items-center gap-2.5 px-3.5 pt-3 pb-2 pr-16">
        <div
          className="flex items-center justify-center shrink-0"
          style={{
            width: 22,
            height: 22,
            borderRadius: 5,
            background: 'transparent',
            color: meta.color,
          }}
        >
          <IconComp size={14} strokeWidth={1.9} />
        </div>
        <div className="flex-1 min-w-0">
          <div
            className="truncate display"
            style={{
              color: 'var(--text-0)',
              fontSize: 13,
              fontWeight: 530,
              lineHeight: 1.25,
              letterSpacing: '-0.012em',
            }}
            title={data.label}
          >
            {data.label}
          </div>
        </div>
      </div>

      {/* Status row — always present so nodes don't jump in height */}
      <div
        className="flex items-center justify-between gap-2 px-3 py-1.5 border-t"
        style={{ borderColor: 'var(--border-soft)', minHeight: 28 }}
      >
        <div className="flex items-center gap-1.5 min-w-0">
          <StatusDot status={run.status} />
          <span
            className="eyebrow"
            style={{ color: ringColor, fontSize: 9.5, letterSpacing: '0.08em' }}
          >
            {statusLabel(run.status)}
          </span>
          {isRunning && run.index != null && run.total != null && (
            <span className="num" style={{ color: 'var(--text-2)', fontSize: 10 }}>
              · {run.index}/{run.total}
            </span>
          )}
        </div>
        {hasRun && (
          <span
            className="num"
            style={{
              color: isError ? 'var(--danger)' : isRunning ? 'var(--running)' : 'var(--text-1)',
              fontSize: 10.5,
              fontWeight: 600,
            }}
          >
            {formatMs(elapsed)}
          </span>
        )}
      </div>

      {/* Config tags — declarative, driven by the node registry's
          `configTags` list so adding/removing a tag is a one-line change
          in backend/engine/registry.py. */}
      {meta.configTags.some((k) => data.config[k] != null) && (
        <div className="flex flex-wrap gap-1 px-3 pb-2.5 pt-0.5">
          {meta.configTags.map((k) => {
            const v = data.config[k]
            if (v == null) return null
            const tone = k === 'signal_type' ? 'danger' : k === 'output_name' ? 'muted' : 'default'
            const label = k === 'output_name' ? `→ ${String(v)}` : String(v)
            return <Tag key={k} label={label} tone={tone} />
          })}
        </div>
      )}

      {/* Validation badge */}
      {hasValidationError && !hasRun && (
        <div
          className="absolute flex items-center gap-0.5"
          style={{
            left: 8,
            top: 6,
            padding: '1px 5px',
            borderRadius: 4,
            background: 'color-mix(in srgb, var(--danger) 14%, var(--bg-node))',
            border: '1px solid color-mix(in srgb, var(--danger) 35%, transparent)',
            color: 'var(--danger)',
            fontSize: 8.5,
            fontWeight: 650,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            maxWidth: 120,
          }}
          title={nodeValidationErrors.map((i) => i.message).join('\n')}
        >
          <AlertTriangle size={9} strokeWidth={2.2} />
          <span className="truncate">{nodeValidationErrors.length > 1 ? `${nodeValidationErrors.length} issues` : 'Invalid'}</span>
        </div>
      )}

      {/* Node category, top-right */}
      <div
        className="absolute num"
        style={{
          right: 8,
          top: 8,
          maxWidth: 112,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          fontSize: 8.5,
          fontWeight: 650,
          color: 'var(--text-3)',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
        }}
        title={getNodeDisplayName(data.nodeType)}
      >
        {data.nodeType}
      </div>

      {/* Handles. Border picks up `--bg-node` so the dot looks like
          it's punched out of the node card in either theme. */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: isRunning ? 'var(--running)' : isSelected ? meta.color : 'var(--text-3)',
          border: '2px solid var(--bg-node)',
          width: 8,
          height: 8,
          left: -4,
          boxShadow: isRunning
            ? '0 0 0 3px color-mix(in srgb, var(--running) 30%, transparent)'
            : isSelected
              ? `0 0 0 2px color-mix(in srgb, ${meta.color} 35%, transparent)`
              : undefined,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: isRunning
            ? 'var(--running)'
            : isOk
              ? 'var(--success)'
              : isSelected
                ? meta.color
                : 'var(--text-3)',
          border: '2px solid var(--bg-node)',
          width: 8,
          height: 8,
          right: -4,
          boxShadow: isRunning
            ? '0 0 0 3px color-mix(in srgb, var(--running) 30%, transparent)'
            : isSelected
              ? `0 0 0 2px color-mix(in srgb, ${meta.color} 35%, transparent)`
              : undefined,
        }}
      />
    </div>
  )
})

CustomNode.displayName = 'CustomNode'

function statusLabel(s: string): string {
  switch (s) {
    case 'running': return 'Running'
    case 'ok': return 'Complete'
    case 'error': return 'Error'
    default: return 'Idle'
  }
}

function StatusDot({ status }: { status: string }) {
  if (status === 'running') {
    return (
      <span className="relative inline-flex" style={{ width: 8, height: 8 }}>
        <span
          className="absolute inset-0 rounded-full"
          style={{ background: 'var(--running)' }}
        />
        <span
          className="absolute inset-0 rounded-full live-blink"
          style={{ background: 'var(--running)', filter: 'blur(4px)' }}
        />
      </span>
    )
  }
  const color =
    status === 'ok' ? 'var(--success)' :
    status === 'error' ? 'var(--danger)' :
    'var(--text-3)'
  return (
    <span
      className="inline-block rounded-full"
      style={{ width: 7, height: 7, background: color }}
    />
  )
}

function Tag({ label, tone = 'default' }: { label: string; tone?: 'default' | 'danger' | 'muted' }) {
  // Use CSS variables so chips invert cleanly with the theme — no
  // hardcoded indigo that disappears on white backgrounds.
  const styles = {
    default: {
      bg: 'var(--bg-3)',
      fg: 'var(--text-1)',
      br: 'var(--border)',
    },
    danger: {
      bg: 'color-mix(in srgb, var(--danger) 10%, transparent)',
      fg: 'var(--danger)',
      br: 'color-mix(in srgb, var(--danger) 30%, transparent)',
    },
    muted: {
      bg: 'var(--bg-3)',
      fg: 'var(--text-2)',
      br: 'var(--border-soft)',
    },
  }[tone]
  return (
    <span
      className="num"
      style={{
        fontSize: 10,
        padding: '2px 6px',
        borderRadius: 4,
        background: styles.bg,
        color: styles.fg,
        border: `1px solid ${styles.br}`,
      }}
    >
      {label}
    </span>
  )
}
