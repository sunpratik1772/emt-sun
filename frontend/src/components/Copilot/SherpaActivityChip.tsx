import { Brain } from 'lucide-react'
import { Sparkles } from '../../icons/arc'
import {
  sherpaActivityLabel,
  sherpaActivitySubtext,
  type SherpaActivityMode,
} from '../../lib/sherpaActivity'

type Props = {
  mode: SherpaActivityMode
  /** When true, show animated status icon (active work). */
  live?: boolean
}

export default function SherpaActivityChip({ mode, live = false }: Props) {
  if (!mode) return null
  const label = sherpaActivityLabel(mode)
  const subtext = live ? sherpaActivitySubtext(mode) : ''
  const ariaLabel = subtext ? `${label} ${subtext}` : label

  return (
    <div
      className={`sherpa-activity-chip${live ? ' sherpa-activity-chip--live' : ''}`}
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      <span className="sherpa-activity-chip__icon" aria-hidden>
        {live ? (
          <Brain size={14} strokeWidth={2.2} />
        ) : (
          <Sparkles size={14} strokeWidth={2.2} />
        )}
      </span>
      <span className="sherpa-activity-chip__text">
        <span className="sherpa-activity-chip__label">{label}</span>
        {subtext ? (
          <>
            {' '}
            <span className="sherpa-activity-chip__sub">{subtext}</span>
          </>
        ) : null}
      </span>
    </div>
  )
}
