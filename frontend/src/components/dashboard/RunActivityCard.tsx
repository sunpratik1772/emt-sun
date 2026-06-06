import RunActivityCalendar from './RunActivityCalendar'
import type { RunActivityCalendarData } from './types'

export default function RunActivityCard({
  calendar,
  onViewRuns,
}: {
  calendar: RunActivityCalendarData
  onViewRuns?: () => void
}) {
  return (
    <section className="dash-panel dash-activity-card dash-activity-card--glass">
      <RunActivityCalendar calendar={calendar} onClick={onViewRuns} />
    </section>
  )
}
