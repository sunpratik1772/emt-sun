import { useRef, type ReactNode } from 'react'
import { ArcIcon, X as XIcon } from '../icons/arc'
import { useEscapeKey, useFocusTrap } from '../hooks/useFocusTrap'

export interface StudioOverlayProps {
  open: boolean
  onClose: () => void
  eyebrow: string
  title: ReactNode
  subtitle?: string
  bodyClass?: string
  footLeft?: ReactNode
  footRight?: ReactNode
  titleAfter?: ReactNode
  children: ReactNode
  /** Renders above body/footer — e.g. full-height detail drawers over the header */
  overlay?: ReactNode
  /** `workspace` = absolute sheet over studio column; `viewport` = fixed full-screen */
  host?: 'workspace' | 'viewport'
  ariaLabel?: string
}

export default function StudioOverlay({
  open,
  onClose,
  eyebrow,
  title,
  subtitle,
  bodyClass,
  footLeft,
  footRight,
  titleAfter,
  children,
  overlay,
  host = 'workspace',
  ariaLabel,
}: StudioOverlayProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  useFocusTrap(overlayRef, open)
  useEscapeKey(onClose, open)

  if (!open) return null

  const hostClass = host === 'viewport' ? 'ov-host ov-host--viewport' : 'ov-host'

  return (
    <div className={hostClass}>
      <div
        ref={overlayRef}
        className="ov"
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel ?? (typeof title === 'string' ? title : eyebrow)}
        tabIndex={-1}
      >
        <div className="ov__head">
          <div className="ov__heading">
            <div className="ov__eyebrow">{eyebrow}</div>
            <div className="ov__title">{title}</div>
            {subtitle ? <div className="ov__sub">{subtitle}</div> : null}
          </div>
          <div className="ov__tools">
            {titleAfter}
            <button type="button" className="ov__close" aria-label="Close" onClick={onClose}>
              <ArcIcon icon={XIcon} size={17} strokeWidth={2} />
            </button>
          </div>
        </div>

        <div className={`ov__body${bodyClass ? ` ${bodyClass}` : ''}`}>
          {bodyClass?.includes('ov__body--flush') ? children : <div className="ov__bodyinner">{children}</div>}
        </div>

        {(footLeft || footRight) && (
          <div className="ov__foot">
            {footLeft}
            <div className="ov__foot-spacer" />
            {footRight}
          </div>
        )}

        {overlay}
      </div>
    </div>
  )
}
