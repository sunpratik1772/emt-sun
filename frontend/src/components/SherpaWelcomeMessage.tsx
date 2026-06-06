import { useAuthStore } from '../store/authStore'
import { useDashboardSherpaFeed } from './dashboard/DashboardSherpaContext'
import { buildSherpaWelcome, DASHBOARD_SUBLINE_FALLBACK } from '../lib/sherpaGreeting'

export default function SherpaWelcomeMessage({
  variant = 'dashboard',
}: {
  variant?: 'dashboard' | 'copilot'
}) {
  const user = useAuthStore((s) => s.user)
  const { greeting, prompt, dateEyebrow } = buildSherpaWelcome(user?.name)

  if (variant === 'copilot') {
    return (
      <div className="sherpa-welcome sherpa-welcome--copilot sherpa-welcome--reveal">
        <p className="sherpa-welcome__greeting">{greeting}</p>
        <p className="sherpa-welcome__prompt">{prompt}</p>
      </div>
    )
  }

  return <DashboardWelcomeSubline greeting={greeting} dateEyebrow={dateEyebrow} />
}

function DashboardWelcomeSubline({ greeting, dateEyebrow }: { greeting: string; dateEyebrow: string }) {
  const { subline, loading, isRefreshing } = useDashboardSherpaFeed()

  return (
    <div className="dash-welcome sherpa-welcome--reveal">
      <p className="dash-welcome__eyebrow">{dateEyebrow}</p>
      <h1 className="dash-welcome__title">{greeting}</h1>
      <p
        key={subline}
        className={`dash-welcome__sub${loading || isRefreshing ? ' dash-welcome__sub--loading' : ''}`}
        aria-live="polite"
      >
        {subline || DASHBOARD_SUBLINE_FALLBACK}
      </p>
    </div>
  )
}
