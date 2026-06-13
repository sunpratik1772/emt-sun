/**
 * StatusPill — a token-driven status badge with a colored dot, label, and
 * optional trailing meta (e.g. duration). Used across Run History, Dashboard,
 * Automations, Topbar — Vercel/Linear/Railway style.
 *
 * Tone maps directly to theme tokens, so the pill adapts to every theme.
 */
import type { CSSProperties, ReactNode } from 'react'

export type StatusTone =
  | 'success'
  | 'danger'
  | 'warning'
  | 'info'
  | 'running'
  | 'neutral'

const TONE_CSS_VAR: Record<StatusTone, string> = {
  success: 'var(--success)',
  danger: 'var(--danger)',
  warning: 'var(--warning)',
  info: 'var(--info)',
  running: 'var(--running, var(--accent))',
  neutral: 'var(--text-3)',
}

export interface StatusPillProps {
  tone?: StatusTone
  label: ReactNode
  /** Trailing tabular-numerics meta (e.g. duration, "12s ago"). */
  meta?: ReactNode
  /** Solid filled style instead of soft tinted background. */
  solid?: boolean
  /** Hide the leading dot. */
  hideDot?: boolean
  /** Animate the dot (used for `running`). */
  pulse?: boolean
  className?: string
  style?: CSSProperties
  testid?: string
}

export default function StatusPill({
  tone = 'neutral',
  label,
  meta,
  solid,
  hideDot,
  pulse,
  className,
  style,
  testid,
}: StatusPillProps) {
  const color = TONE_CSS_VAR[tone]
  const pulseClass = pulse || tone === 'running' ? ' status-pill__dot--pulse' : ''
  const classes = `status-pill status-pill--${tone}${solid ? ' status-pill--solid' : ''}${
    className ? ` ${className}` : ''
  }`
  return (
    <span
      className={classes}
      data-testid={testid}
      style={{ ['--pill-color' as string]: color, ...style }}
    >
      {!hideDot ? <span className={`status-pill__dot${pulseClass}`} aria-hidden /> : null}
      <span className="status-pill__label">{label}</span>
      {meta != null ? <span className="status-pill__meta">{meta}</span> : null}
    </span>
  )
}

/** Convenience map for common run statuses. */
export function statusToneFromRun(status: string | null | undefined): StatusTone {
  switch ((status || '').toLowerCase()) {
    case 'success':
    case 'ready':
    case 'completed':
    case 'ok':
      return 'success'
    case 'failed':
    case 'error':
    case 'cancelled':
    case 'canceled':
      return 'danger'
    case 'warning':
    case 'partial':
      return 'warning'
    case 'running':
    case 'pending':
    case 'queued':
    case 'in_progress':
    case 'building':
      return 'running'
    case 'info':
    case 'started':
      return 'info'
    default:
      return 'neutral'
  }
}
