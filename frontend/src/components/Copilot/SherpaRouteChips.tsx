import { useCopilotRoutes, suggestedSlashRoutes, buildSlashMessage } from '../../hooks/useCopilotRoutes'
import type { SherpaSlashRouteDef } from '../../services/api'

type SherpaRouteChipsProps = {
  hasWorkflow: boolean
  hasRunLog: boolean
  hasErrors: boolean
  onSelect: (message: string) => void
  limit?: number
  title?: string
  showMoreHint?: boolean
}

export default function SherpaRouteChips({
  hasWorkflow,
  hasRunLog,
  hasErrors,
  onSelect,
  limit = 6,
  title = 'Routes',
  showMoreHint = false,
}: SherpaRouteChipsProps) {
  const { data, isLoading } = useCopilotRoutes({
    hasWorkflow,
    hasRunLog,
    hasErrors,
  })
  const chips = suggestedSlashRoutes(data?.routes, data?.suggested_ids).slice(0, limit)

  if (!chips.length && !isLoading) return null

  return (
    <div className="routes" role="list" aria-label="Sherpa slash routes">
      <div className="routes__head">
        <span className="routes__label">{title}</span>
        <span className="routes__hint">
          {showMoreHint ? 'Press \\ for more options' : 'Press \\ or tap a route'}
        </span>
      </div>
      <div className="routes__list">
        {isLoading && !chips.length ? (
          <span className="routes__loading" style={{ fontSize: 10, color: 'var(--text-3)' }}>Loading routes…</span>
        ) : (
          chips.map((route) => (
            <RouteChip key={route.id} route={route} onSelect={onSelect} />
          ))
        )}
      </div>
    </div>
  )
}

function RouteChip({
  route,
  onSelect,
}: {
  route: SherpaSlashRouteDef
  onSelect: (message: string) => void
}) {
  return (
    <button
      type="button"
      className="route-chip"
      title={route.description}
      onClick={() => onSelect(buildSlashMessage(route))}
    >
      <span className="route-chip__cmd">{route.command}</span>
      <span className="route-chip__name">{route.label}</span>
    </button>
  )
}
