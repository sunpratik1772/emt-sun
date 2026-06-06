import { useQuery } from '@tanstack/react-query'
import { api, type SherpaSlashRouteDef } from '../services/api'
import { queryKeys } from './queryKeys'

export function useCopilotRoutes(opts: {
  hasWorkflow: boolean
  hasRunLog: boolean
  hasErrors: boolean
  enabled?: boolean
}) {
  const ctx = { wf: opts.hasWorkflow, log: opts.hasRunLog, err: opts.hasErrors }
  return useQuery({
    queryKey: queryKeys.copilotRoutes(ctx),
    queryFn: () =>
      api.getCopilotRoutes({
        has_workflow: opts.hasWorkflow,
        has_run_log: opts.hasRunLog,
        has_errors: opts.hasErrors,
      }),
    enabled: opts.enabled !== false,
    staleTime: 30_000,
  })
}

export function suggestedSlashRoutes(
  routes: SherpaSlashRouteDef[] | undefined,
  suggestedIds: string[] | undefined,
): SherpaSlashRouteDef[] {
  if (!routes?.length || !suggestedIds?.length) return []
  const byId = new Map(routes.map((r) => [r.id, r]))
  return suggestedIds.map((id) => byId.get(id)).filter((r): r is SherpaSlashRouteDef => Boolean(r))
}

export function buildSlashMessage(route: SherpaSlashRouteDef, body?: string): string {
  const tail = (body ?? route.default_body ?? '').trim()
  return tail ? `${route.command} ${tail}` : route.command
}
