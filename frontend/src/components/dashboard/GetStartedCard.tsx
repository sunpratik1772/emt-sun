import { ArcIcon, ChevronRight } from '../../icons/arc'
import type { DashboardGetStartedStep } from './types'

export default function GetStartedCard({
  steps,
  onOpenSettings,
}: {
  steps: DashboardGetStartedStep[]
  onOpenSettings?: () => void
}) {
  const completed = steps.filter((s) => s.done).length
  const total = steps.length
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0

  return (
    <section className="dash-panel dash-get-started">
      <div className="dash-get-started__head">
        <h2 className="dash-section-title">Get started with dbSherpa Studio</h2>
        <span className="dash-get-started__count">
          {completed}/{total} steps
        </span>
      </div>

      <div className="dash-get-started__progress" aria-hidden>
        <div className="dash-get-started__progress-fill" style={{ width: `${pct}%` }} />
      </div>

      <ul className="dash-get-started__list">
        {steps.map((step) => (
          <li key={step.id}>
            <button
              type="button"
              className={`dash-get-started__item${step.done ? ' dash-get-started__item--done' : ''}`}
              onClick={step.onClick}
              disabled={!step.onClick}
            >
              <span className="dash-get-started__check" aria-hidden>
                {step.done ? '✓' : ''}
              </span>
              <span className="dash-get-started__label">{step.label}</span>
              {!step.done && step.onClick ? (
                <ArcIcon icon={ChevronRight} size={14} className="dash-get-started__chevron" />
              ) : null}
            </button>
          </li>
        ))}
      </ul>

      {completed === total ? (
        <p className="dash-get-started__done-msg">You&apos;re all set — keep building in Studio.</p>
      ) : (
        <button type="button" className="dash-link-btn dash-link-btn--sm" onClick={onOpenSettings}>
          Configure integrations in Settings →
        </button>
      )}
    </section>
  )
}
