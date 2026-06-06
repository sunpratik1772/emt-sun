import type { DashboardRunHealth } from './types'

function rateDisplay(health: DashboardRunHealth): {
  value: string
  tone: 'neutral' | 'success' | 'warn' | 'danger'
  summary: string
} {
  const { runsThisMonth, failedThisMonth, successRate } = health

  if (runsThisMonth === 0) {
    return {
      value: '—',
      tone: 'neutral',
      summary: 'No runs yet this month',
    }
  }

  const success = runsThisMonth - failedThisMonth
  const pct = successRate != null ? Math.round(successRate * 100) : 0

  if (failedThisMonth === runsThisMonth) {
    return {
      value: '0%',
      tone: 'danger',
      summary: `${runsThisMonth} run${runsThisMonth === 1 ? '' : 's'} — all failed`,
    }
  }

  if (success === runsThisMonth) {
    return {
      value: `${pct}%`,
      tone: 'success',
      summary: `${runsThisMonth} run${runsThisMonth === 1 ? '' : 's'} — all succeeded`,
    }
  }

  const tone = pct >= 80 ? 'success' : pct >= 50 ? 'warn' : 'danger'
  return {
    value: `${pct}%`,
    tone,
    summary: `${runsThisMonth} run${runsThisMonth === 1 ? '' : 's'} · ${failedThisMonth} failed`,
  }
}

export default function RunHealthCard({ health }: { health: DashboardRunHealth }) {
  const { value, tone, summary } = rateDisplay(health)

  return (
    <section className={`dash-health-card dash-health-card--glass dash-health-card--${tone}`}>
      <div className="dash-health-card__blobs" aria-hidden>
        <span className="dash-health-card__blob dash-health-card__blob--1" />
        <span className="dash-health-card__blob dash-health-card__blob--2" />
        <span className="dash-health-card__blob dash-health-card__blob--3" />
      </div>

      <div className="dash-health-card__content">
        <div className="dash-health-card__metric">
          <span className={`dash-health-card__value dash-health-card__value--${tone}`}>{value}</span>
          <span className="dash-health-card__label">Success rate this month</span>
        </div>
        <p className="dash-health-card__copy">{summary}</p>
        <div className="dash-health-card__footer">
          <span
            className={`dash-pill dash-pill--status${
              health.engineOnline ? ' dash-pill--status-online' : ''
            }`}
          >
            <span className="dash-pill__dot" />
            {health.engineOnline ? 'Engine online' : 'Engine offline'}
          </span>
        </div>
      </div>
    </section>
  )
}
