import { useMemo } from 'react'
import { useAuthStore } from '../store/authStore'
import {
  buildSherpaStarterContext,
  ensureStarterPromptCount,
  personalizeStarterPrompts,
  resolveStarterPrompts,
} from '../lib/sherpaStarterPrompts'
import {
  buildSherpaWelcome,
  DASHBOARD_SUBLINE_FALLBACK,
  firstNameFromDisplayName,
  pickDashboardSublineFallback,
} from '../lib/sherpaGreeting'
import {
  useCopilotExamplePrompts,
  useRunLogs,
  useWorkflowCatalog,
} from './useLibraryQueries'

function shuffle<T>(items: T[]): T[] {
  const out = [...items]
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

/** Single fetch for dashboard welcome subline + three suggestion cards. */
export function useDashboardSherpaContent(
  suggestionLimit = 3,
  enabled = true,
  mountNonce = Date.now(),
) {
  const user = useAuthStore((s) => s.user)
  const { period } = buildSherpaWelcome(user?.name)
  const firstName = firstNameFromDisplayName(user?.name)

  const { data: catalog = [] } = useWorkflowCatalog(true)
  const { data: runLogs = [] } = useRunLogs(true, 8000)

  const { data, isLoading, isFetching, isError, dataUpdatedAt } = useCopilotExamplePrompts(
    enabled,
    { firstName, period },
    {
      staleTime: 0,
      gcTime: 0,
      refetchOnMount: 'always',
      refetchOnWindowFocus: 'always',
      refreshNonce: mountNonce,
    },
  )

  const dashContext = useMemo(
    () => buildSherpaStarterContext(catalog, runLogs, { hasCanvasWorkflow: false }),
    [catalog, runLogs],
  )

  const suggestions = useMemo(() => {
    const base = resolveStarterPrompts(
      data?.build_prompts,
      data?.ask_prompts,
      suggestionLimit * 2,
      { allowRegistryFallbacks: true },
    )
    const personalized = personalizeStarterPrompts(base, dashContext, suggestionLimit * 2)
    return shuffle(ensureStarterPromptCount(personalized, suggestionLimit, dashContext))
  }, [dashContext, data?.ask_prompts, data?.build_prompts, dataUpdatedAt, suggestionLimit])

  const subline = useMemo(() => {
    const fromApi = data?.dashboard_subline?.trim()
    if (fromApi) return fromApi
    if (data && !isLoading) return pickDashboardSublineFallback()
    return DASHBOARD_SUBLINE_FALLBACK
  }, [data, isLoading, dataUpdatedAt])

  const aiReady = Boolean(
    data?.dashboard_subline ||
      data?.build_prompts?.length ||
      data?.ask_prompts?.length,
  )

  const loading = isLoading || (isFetching && !aiReady)

  const status: 'loading' | 'ready' | 'error' = isLoading
    ? 'loading'
    : isError
      ? 'error'
      : aiReady
        ? 'ready'
        : 'error'

  return {
    subline,
    suggestions,
    loading,
    aiReady,
    status,
    sublineFromAi: Boolean(data?.dashboard_subline_from_ai),
    isRefreshing: isFetching && !isLoading,
  }
}
