import { useRef, type CSSProperties, type ReactNode } from 'react'
import { useEscapeKey, useFocusTrap } from '../hooks/useFocusTrap'

interface ModalProps {
  ariaLabel: string
  onClose: () => void
  children: ReactNode
  zIndex?: number
  closeOnBackdrop?: boolean
  overlayStyle?: CSSProperties
  overlayClassName?: string
  backdropClassName?: string
  panelStyle?: CSSProperties
  panelClassName?: string
}

export default function Modal({
  ariaLabel,
  onClose,
  children,
  zIndex = 110,
  closeOnBackdrop = true,
  overlayStyle,
  overlayClassName,
  backdropClassName,
  panelStyle,
  panelClassName = 'panel-glass',
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  useFocusTrap(panelRef, true)
  useEscapeKey(onClose, true)

  return (
    <div
      className={overlayClassName ? `fixed inset-0 flex items-center justify-center ${overlayClassName}` : 'fixed inset-0 flex items-center justify-center'}
      style={overlayClassName ? { zIndex } : { zIndex, ...overlayStyle }}
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
    >
      <button
        type="button"
        aria-label="Close dialog"
        className={backdropClassName ?? 'absolute inset-0'}
        style={
          backdropClassName
            ? {
                border: 'none',
                padding: 0,
                cursor: closeOnBackdrop ? 'pointer' : 'default',
              }
            : {
                background: overlayStyle?.background ?? 'rgba(3, 6, 11, 0.46)',
                backdropFilter: overlayStyle?.backdropFilter ?? 'blur(3px)',
                WebkitBackdropFilter: overlayStyle?.WebkitBackdropFilter ?? 'blur(3px)',
                border: 'none',
                padding: 0,
                cursor: closeOnBackdrop ? 'pointer' : 'default',
              }
        }
        onClick={closeOnBackdrop ? onClose : undefined}
        tabIndex={-1}
      />
      <div
        ref={panelRef}
        className={panelClassName}
        style={{ position: 'relative', zIndex: 1, ...panelStyle }}
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>
  )
}
