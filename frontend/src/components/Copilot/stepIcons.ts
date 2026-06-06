/** Cursor AI timeline step kinds (open-design signature colors). */
export type StepKind = 'thinking' | 'grep' | 'read' | 'edit' | 'default'

export const STEP_KIND_COLOR: Record<StepKind, string> = {
  thinking: 'var(--cursor-tl-thinking)',
  grep: 'var(--cursor-tl-grep)',
  read: 'var(--cursor-tl-read)',
  edit: 'var(--cursor-tl-edit)',
  default: 'var(--cursor-muted)',
}

/** Map pipeline step copy → Cursor timeline kind. */
export function stepKindFor(text: string): StepKind {
  const t = text.toLowerCase()
  if (
    t.includes('gemini') ||
    t.includes('plan') ||
    t.includes('asking') ||
    t.includes('think') ||
    t.includes('pars') ||
    t.includes('analyz') ||
    t.includes('request')
  ) {
    return 'thinking'
  }
  if (
    t.includes('grep') ||
    t.includes('search') ||
    t.includes('lookup') ||
    t.includes('schema') ||
    t.includes('retriev') ||
    t.includes('memory') ||
    t.includes('template') ||
    t.includes('resolv')
  ) {
    return 'grep'
  }
  if (
    t.includes('read') ||
    t.includes('dry') ||
    t.includes('simul') ||
    t.includes('valid') ||
    t.includes('fetch') ||
    t.includes('verify') ||
    t.includes('health')
  ) {
    return 'read'
  }
  if (
    t.includes('heal') ||
    t.includes('repair') ||
    t.includes('fix') ||
    t.includes('draft') ||
    t.includes('edit') ||
    t.includes('connect') ||
    t.includes('node') ||
    t.includes('trigger') ||
    t.includes('config') ||
    t.includes('stage') ||
    t.includes('deploy') ||
    t.includes('link') ||
    t.includes('variab')
  ) {
    return 'edit'
  }
  return 'default'
}

export function formatStepSeconds(sec?: number): string {
  if (sec == null || Number.isNaN(sec)) return '—'
  if (sec < 0.05) return '<0.1s'
  if (sec < 10) return `${sec.toFixed(1)}s`
  return `${Math.round(sec)}s`
}

/** Short label for compact timeline row. */
export function stepLabel(text: string): string {
  const t = text.trim()
  if (t.length <= 52) return t
  return `${t.slice(0, 49)}…`
}
