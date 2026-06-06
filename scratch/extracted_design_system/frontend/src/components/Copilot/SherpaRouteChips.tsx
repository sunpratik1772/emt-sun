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
    <div className="sherpa-routes" role="list" aria-label="Sherpa slash routes">
      <div className="sherpa-routes__head">
        <span className="sherpa-routes__label">{title}</span>
        <span className="sherpa-routes__hint">
          {showMoreHint ? 'Press \\ for more options' : 'Press \\ or tap a route'}
        </span>
      </div>
      <div className="sherpa-routes__list">
        {isLoading && !chips.length ? (
          <span className="sherpa-routes__loading">Loading routes…</span>
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
      className="sherpa-routes__chip"
      title={route.description}
      onClick={() => onSelect(buildSlashMessage(route))}
    >
      <span className="sherpa-routes__cmd">{route.command}</span>
      <span className="sherpa-routes__name">{route.label}</span>
    </button>
  )
}
