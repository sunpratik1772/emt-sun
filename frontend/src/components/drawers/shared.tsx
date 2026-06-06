import type { CSSProperties, ReactNode } from 'react'
import { Button } from '../ui/Button'
import {
  ArcIcon,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  CircleDashed,
} from '../../icons/arc'

export function PanelLoading() {
  return (
    <div className="flex items-center justify-center" style={{ padding: 32, color: 'var(--text-3)' }}>
      <ArcIcon icon={Loader2} size={14} className="animate-spin" />
    </div>
  )
}

export function PanelError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center"
      style={{ padding: 32, color: 'var(--text-2)', fontSize: 12 }}
    >
      <ArcIcon icon={AlertTriangle} size={18} style={{ color: 'var(--danger)', marginBottom: 8 }} />
      <div style={{ color: 'var(--text-0)', fontWeight: 500, marginBottom: 4 }}>Could not load</div>
      <div style={{ color: 'var(--text-2)', maxWidth: 280, lineHeight: 1.5 }}>{message}</div>
      {onRetry && (
        <Button variant="secondary" size="sm" className="font-mono mt-3" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

export function PanelEmpty({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center"
      style={{ padding: 40, color: 'var(--text-3)', fontSize: 12 }}
    >
      <div style={{ marginBottom: 6 }}>{icon}</div>
      {children}
    </div>
  )
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <label className="studio-label">{children}</label>
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  icon,
  className = '',
  style,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  icon: ReactNode
  className?: string
  style?: CSSProperties
}) {
  return (
    <div className={`studio-search-wrap ${className}`.trim()} style={style}>
      <span style={{ display: 'flex', alignItems: 'center', color: 'var(--text-3)', flexShrink: 0 }}>{icon}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
    </div>
  )
}

export function ListRow({
  selected,
  accentColor,
  onClick,
  children,
  className = '',
  testId,
}: {
  selected?: boolean
  accentColor?: string
  onClick: () => void
  children: ReactNode
  className?: string
  testId?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className={`studio-list-row${selected ? ' studio-list-row--selected' : ''} ${className}`.trim()}
      style={selected && accentColor ? { borderLeftColor: accentColor } : undefined}
    >
      {children}
    </button>
  )
}

export function BackendChip({ label }: { label: string }) {
  return <span className="studio-chip">{label}</span>
}


export function ToolbarButton({
  onClick,
  icon,
  children,
}: {
  onClick: () => void
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      className="font-normal"
      style={{
        height: 26,
        padding: '0 10px',
        fontSize: 11.5,
        fontWeight: 500,
        letterSpacing: '-0.005em',
        color: 'var(--text-1)',
      }}
    >
      {icon}
      <span>{children}</span>
    </Button>
  )
}

export function Stat({ label, value, color = 'var(--text-0)' }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="num" style={{ color, fontSize: 13, fontWeight: 540 }}>
        {value}
      </span>
      <span className="studio-meta">{label}</span>
    </div>
  )
}

export function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="studio-label" style={{ marginBottom: 2 }}>{label}</div>
      <div className={mono ? 'font-mono' : ''} style={{ fontSize: 12, color: 'var(--text-1)', letterSpacing: mono ? '0.02em' : '-0.005em' }}>
        {value}
      </div>
    </div>
  )
}

export function StatusIcon({ status, large }: { status: string; large?: boolean }) {
  const size = large ? 14 : 11
  if (status === 'success')
    return <ArcIcon icon={CheckCircle2} size={size} strokeWidth={2} style={{ color: 'var(--success)', marginTop: 2 }} />
  if (status === 'error') return <ArcIcon icon={XCircle} size={size} strokeWidth={2} style={{ color: 'var(--danger)', marginTop: 2 }} />
  if (status === 'warning') return <ArcIcon icon={AlertTriangle} size={size} strokeWidth={2} style={{ color: 'var(--warning)', marginTop: 2 }} />
  if (status === 'running')
    return <ArcIcon icon={Loader2} size={size} className="animate-spin" style={{ color: 'var(--running)', marginTop: 2 }} />
  return <ArcIcon icon={CircleDashed} size={size} strokeWidth={2} style={{ color: 'var(--text-3)', marginTop: 2 }} />
}

export function statusColor(status: string): string {
  if (status === 'success') return 'var(--success)'
  if (status === 'error') return 'var(--danger)'
  if (status === 'warning') return 'var(--warning)'
  if (status === 'running') return 'var(--running)'
  return 'var(--text-3)'
}

export function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    const now = new Date()
    const diff = (now.getTime() - d.getTime()) / 1000
    if (diff < 60) return `${Math.floor(diff)}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return d.toLocaleString()
  } catch {
    return iso
  }
}

export function formatDur(ms?: number | null): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

export const thStyle: CSSProperties = {
  textAlign: 'left',
  padding: '8px 12px',
  fontSize: 10,
  fontWeight: 500,
  color: 'var(--text-3)',
  letterSpacing: '0.10em',
  textTransform: 'uppercase',
}
export const tdNameStyle: CSSProperties = { padding: '7px 12px', color: 'var(--text-0)', fontSize: 11.5, letterSpacing: '0.005em' }
export const tdTypeStyle: CSSProperties = { padding: '7px 12px', color: 'var(--text-2)', fontSize: 11, letterSpacing: '0.02em' }
export const tdDescStyle: CSSProperties = { padding: '7px 12px', color: 'var(--text-1)', fontSize: 11.5, lineHeight: 1.5 }

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const STATUS_MAP: Record<string, [string, string]> = {
    paused: ['paused', 'Paused'],
    success: ['ok', 'Succeeded'],
    error: ['err', 'Failed'],
    syncing: ['run', 'Syncing'],
    running: ['run', 'Running'],
  }
  const [tone, text] = STATUS_MAP[status] || ['paused', status]
  return (
    <span className={`sbadge sbadge--${tone}`}>
      <span className="sbadge__dot" />
      {label || text}
    </span>
  )
}

export function DSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="dsec__label">{label}</div>
      {children}
    </div>
  )
}

export function DCell({ k, v, mono }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="dcell">
      <div className="dcell__k">{k}</div>
      <div className="dcell__v">{mono ? <code>{v}</code> : v}</div>
    </div>
  )
}
