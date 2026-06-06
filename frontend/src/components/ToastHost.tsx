import { ArcIcon, CheckCircle2, AlertTriangle, CircleDashed, XCircle, X } from '../icons/arc'
import { useToastStore, type ToastVariant } from '../store/toastStore'

const VARIANT: Record<
  ToastVariant,
  { icon: typeof CheckCircle2; color: string; bg: string; border: string }
> = {
  success: {
    icon: CheckCircle2,
    color: 'var(--success)',
    bg: 'color-mix(in srgb, var(--success) 10%, var(--bg-1))',
    border: 'color-mix(in srgb, var(--success) 35%, var(--border-soft))',
  },
  error: {
    icon: XCircle,
    color: 'var(--danger)',
    bg: 'color-mix(in srgb, var(--danger) 10%, var(--bg-1))',
    border: 'color-mix(in srgb, var(--danger) 35%, var(--border-soft))',
  },
  warning: {
    icon: AlertTriangle,
    color: 'var(--warning)',
    bg: 'color-mix(in srgb, var(--warning) 10%, var(--bg-1))',
    border: 'color-mix(in srgb, var(--warning) 35%, var(--border-soft))',
  },
  info: {
    icon: CircleDashed,
    color: 'var(--info)',
    bg: 'color-mix(in srgb, var(--info) 10%, var(--bg-1))',
    border: 'color-mix(in srgb, var(--info) 35%, var(--border-soft))',
  },
}

export default function ToastHost() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  if (toasts.length === 0) return null

  return (
    <div
      className="toast-host fixed z-[260] flex flex-col gap-2 pointer-events-none"
      style={{
        right: 16,
        bottom: 'max(16px, env(safe-area-inset-bottom, 0px))',
        maxWidth: 380,
        width: 'min(380px, calc(100vw - 32px))',
      }}
      aria-live="polite"
      aria-relevant="additions"
    >
      {toasts.map((t) => {
        const v = VARIANT[t.variant]
        const Icon = v.icon
        return (
          <div
            key={t.id}
            className="panel-glass pointer-events-auto flex items-start gap-2.5"
            style={{
              padding: '10px 12px',
              borderRadius: 10,
              border: `1px solid ${v.border}`,
              background: v.bg,
              boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
            }}
          >
            <ArcIcon icon={Icon} size={15} strokeWidth={2} style={{ color: v.color, marginTop: 1, flexShrink: 0 }} />
            <div className="flex-1 min-w-0" style={{ fontSize: 12.5, color: 'var(--text-0)', lineHeight: 1.45 }}>
              {t.message}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
              className="shrink-0 flex items-center justify-center"
              style={{
                width: 22,
                height: 22,
                borderRadius: 5,
                border: 'none',
                background: 'transparent',
                color: 'var(--text-3)',
                cursor: 'pointer',
              }}
            >
              <X size={12} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
