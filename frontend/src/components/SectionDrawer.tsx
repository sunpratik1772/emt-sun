/**
 * Slide-over content drawer used for Skills / Data Sources / Logs.
 */
import { useRef, type ReactNode } from 'react'
import { ArcIcon, X as XIcon } from '../icons/arc'
import { useEscapeKey, useFocusTrap } from '../hooks/useFocusTrap'

interface Props {
  open: boolean
  onClose: () => void
  title: string
  eyebrow?: string
  subtitle?: string
  badge?: string
  width?: number | string
  children: ReactNode
  toolbar?: ReactNode
  hideHeaderTitle?: boolean
}

export default function SectionDrawer({
  open,
  onClose,
  title,
  eyebrow,
  subtitle,
  badge,
  width = '100%',
  children,
  toolbar,
  hideHeaderTitle = false,
}: Props) {
  const drawerRef = useRef<HTMLDivElement>(null)
  useFocusTrap(drawerRef, open)
  useEscapeKey(onClose, open)

  if (!open) return null
  return (
    <>
      <button
        type="button"
        className="drawer-backdrop"
        aria-label="Close drawer"
        onClick={onClose}
      />
      <div
        ref={drawerRef}
        className="drawer panel-glass flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        style={{
          width,
          maxWidth: '100%',
          borderRight: '1px solid var(--border-strong)',
          boxShadow: '12px 0 32px -16px rgba(0,0,0,.35)',
        }}
      >
        <div
          className="shrink-0 flex items-center justify-between px-4 drawer__header"
          style={{
            height: 48,
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div className="flex items-center gap-2 min-w-0 flex-1">
            {!hideHeaderTitle && (
              <div className="flex items-center gap-2 min-w-0">
                {eyebrow && (
                  <span className="screen__eyebrow">{eyebrow}</span>
                )}
                <span className="eyebrow" style={{ color: 'var(--text-0)' }}>
                  {title}
                </span>
                {badge && (
                  <span
                    className="num shrink-0"
                    style={{
                      fontSize: 10.5,
                      color: 'var(--text-2)',
                      background: 'var(--bg-0)',
                      border: '1px solid var(--border)',
                      padding: '1px 6px',
                      borderRadius: 999,
                    }}
                  >
                    {badge}
                  </span>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {toolbar}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="lift flex items-center justify-center drawer-close-btn"
              style={{
                width: 26,
                height: 26,
                borderRadius: 6,
                background: 'transparent',
                color: 'var(--text-2)',
                border: '1px solid transparent',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLElement).style.background = 'var(--bg-2)'
                ;(e.currentTarget as HTMLElement).style.color = 'var(--text-0)'
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLElement).style.background = 'transparent'
                ;(e.currentTarget as HTMLElement).style.color = 'var(--text-2)'
              }}
            >
              <ArcIcon icon={XIcon} size={14} />
            </button>
          </div>
        </div>
        {subtitle && !hideHeaderTitle && (
          <div
            className="shrink-0 studio-meta"
            style={{
              padding: '8px 16px',
              borderBottom: '1px solid var(--border-soft)',
              lineHeight: 1.5,
              background: 'var(--bg-1)',
            }}
          >
            {subtitle}
          </div>
        )}
        <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>
      </div>
    </>
  )
}
