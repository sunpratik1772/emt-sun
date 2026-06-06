import { useMemo } from 'react'
import { useCopilotRoutes } from '../../hooks/useCopilotRoutes'
import type { SherpaSlashRouteDef } from '../../services/api'

type SherpaSlashMenuProps = {
  filter: string
  hasWorkflow: boolean
  hasRunLog: boolean
  hasErrors: boolean
  onPick: (route: SherpaSlashRouteDef) => void
  onClose: () => void
}

export default function SherpaSlashMenu({
  filter,
  hasWorkflow,
  hasRunLog,
  hasErrors,
  onPick,
  onClose,
}: SherpaSlashMenuProps) {
  const { data } = useCopilotRoutes({ hasWorkflow, hasRunLog, hasErrors })
  const needle = filter.toLowerCase().replace(/^[/\\]/, '')

  const matches = useMemo(() => {
    const routes = data?.routes ?? []
    if (!needle) return routes
    return routes.filter(
      (r) =>
        r.slash.includes(needle) ||
        r.label.toLowerCase().includes(needle) ||
        r.id.includes(needle),
    )
  }, [data?.routes, needle])

  if (!matches.length) return null

  return (
    <div className="sherpa-slash-menu" role="listbox" aria-label="Sherpa routes">
      {matches.map((route) => (
        <button
          key={route.id}
          type="button"
          role="option"
          className="sherpa-slash-menu__row"
          onMouseDown={(e) => {
            e.preventDefault()
            onPick(route)
            onClose()
          }}
        >
          <span className="sherpa-slash-menu__cmd">{route.command}</span>
          <span className="sherpa-slash-menu__label">{route.label}</span>
          <span className="sherpa-slash-menu__desc">{route.description}</span>
        </button>
      ))}
    </div>
  )
}
