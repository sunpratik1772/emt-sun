import type { RunActivityCalendarData, RunCalendarCell } from './types'

function parseDateKey(key: string): Date {
  const [y, m, d] = key.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function groupIntoWeeks(cells: RunCalendarCell[]): RunCalendarCell[][] {
  const weeks: RunCalendarCell[][] = []
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7))
  }
  return weeks
}

function monthLabelForWeek(week: RunCalendarCell[], prevWeek?: RunCalendarCell[]): string {
  if (week.length === 0) return ''
  const first = parseDateKey(week[0].date)
  if (!prevWeek?.length) {
    return first.toLocaleDateString('en-US', { month: 'short' })
  }
  const prevFirst = parseDateKey(prevWeek[0].date)
  if (first.getMonth() !== prevFirst.getMonth()) {
    return first.toLocaleDateString('en-US', { month: 'short' })
  }
  return ''
}

function cellTitle(cell: RunCalendarCell): string {
  const d = parseDateKey(cell.date)
  const label = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  if (cell.count === 0) return `${label} · no runs`
  return `${label} · ${cell.count} run${cell.count === 1 ? '' : 's'}`
}

export default function RunActivityCalendar({
  calendar,
  onClick,
}: {
  calendar: RunActivityCalendarData
  onClick?: () => void
}) {
  const weeks = groupIntoWeeks(calendar.cells)
  const streakWeeks = Math.floor(calendar.streakDays / 7)
  const streakLabel =
    calendar.streakDays === 0
      ? null
      : streakWeeks >= 1
        ? `${streakWeeks}-week streak`
        : `${calendar.streakDays}-day streak`

  return (
    <div className="dash-run-calendar">
      <div className="dash-run-calendar__head">
        <span className="dash-run-calendar__title">Run activity</span>
        {streakLabel ? (
          <span className="dash-run-calendar__streak">{streakLabel}</span>
        ) : null}
      </div>

      <button
        type="button"
        className="dash-run-calendar__grid-wrap"
        onClick={onClick}
        disabled={!onClick}
        aria-label="View run history"
      >
        <div className="dash-run-calendar__months" aria-hidden>
          {weeks.map((week, i) => (
            <span key={week[0]?.date ?? i} className="dash-run-calendar__month">
              {monthLabelForWeek(week, weeks[i - 1])}
            </span>
          ))}
        </div>
        <div className="dash-run-calendar__grid" aria-hidden>
          {weeks.map((week) => (
            <div key={week[0]?.date} className="dash-run-calendar__week">
              {week.map((cell) => (
                <span
                  key={cell.date}
                  className={`dash-run-calendar__cell${
                    cell.level > 0 ? ` dash-run-calendar__cell--l${cell.level}` : ''
                  }`}
                  title={cellTitle(cell)}
                />
              ))}
            </div>
          ))}
        </div>
      </button>

      <div className="dash-run-calendar__legend" aria-hidden>
        <span>Less</span>
        {[0, 1, 2, 3, 4].map((level) => (
          <span
            key={level}
            className={`dash-run-calendar__cell${
              level > 0 ? ` dash-run-calendar__cell--l${level}` : ''
            }`}
          />
        ))}
        <span>More</span>
      </div>
    </div>
  )
}
