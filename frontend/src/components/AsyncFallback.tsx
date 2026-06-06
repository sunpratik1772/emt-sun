import { ArcIcon, Loader2 } from '../icons/arc'

export default function AsyncFallback({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      className="flex flex-1 min-h-0 items-center justify-center gap-2"
      style={{ color: 'var(--text-3)', fontSize: 12, padding: 24 }}
      role="status"
      aria-live="polite"
    >
      <ArcIcon icon={Loader2} size={14} className="animate-spin" />
      <span>{label}</span>
    </div>
  )
}
