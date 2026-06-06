import type { DashboardRunActivity } from './types'

function statusIcon(status: DashboardRunActivity['status']): string {
  if (status === 'success') return '✓'
  if (status === 'error') return '✗'
  if (status === 'running') return '●'
  return '◦'
}

function statusClass(status: DashboardRunActivity['status']): string {
  if (status === 'success') return 'dash-run-item__icon--success'
  if (status === 'error') return 'dash-run-item__icon--error'
  if (status === 'running') return 'dash-run-item__icon--running'
  return 'dash-run-item__icon--muted'
}

export default function RecentRunsRail({
  runs,
  onViewAll,
  onRunClick,
}: {
  runs: DashboardRunActivity[]
  onViewAll?: () => void
  onRunClick?: (run: DashboardRunActivity) => void
}) {
  const visible = runs.slice(0, 4)

  return (
    <section className="dash-panel dash-recent-runs">
      <h2 className="dash-section-title">Recent runs</h2>
      {visible.length === 0 ? (
        <p className="dash-panel__empty">Runs will appear here after you execute a workflow in Studio.</p>
      ) : (
        <ul className="dash-run-list">
          {visible.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                className="dash-run-item"
                onClick={() => onRunClick?.(run)}
                disabled={!onRunClick}
              >
                <span className={`dash-run-item__icon ${statusClass(run.status)}`} aria-hidden>
                  {statusIcon(run.status)}
                </span>
                <div className="dash-run-item__body">
                  <span className="dash-run-item__name">{run.workflowName}</span>
                  <span className="dash-run-item__time">{run.time}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="dash-panel__link" onClick={onViewAll}>
        View all runs
      </button>
    </section>
  )
}
