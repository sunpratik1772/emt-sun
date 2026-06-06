import { useMemo } from 'react'
import { useCopilotExamplePrompts } from './useLibraryQueries'
import {
  ensureStarterPromptCount,
  personalizeStarterPrompts,
  resolveStarterPrompts,
  type SherpaStarterContext,
} from '../lib/sherpaStarterPrompts'

export function useSherpaStarterPrompts(
  limit = 5,
  context?: SherpaStarterContext,
  queryContext?: { firstName?: string; period?: string },
) {
  const { data, isLoading, isFetching, isError } = useCopilotExamplePrompts(
    limit > 0,
    queryContext,
  )

  const prompts = useMemo(() => {
    const base = resolveStarterPrompts(data?.build_prompts, data?.ask_prompts, limit * 2, {
      allowRegistryFallbacks: true,
    })
    const merged = personalizeStarterPrompts(base, context, limit * 2)
    return ensureStarterPromptCount(merged, limit, context)
  }, [context, data?.ask_prompts, data?.build_prompts, limit])

  const aiReady = Boolean(data?.build_prompts?.length || data?.ask_prompts?.length)
  const status: 'loading' | 'ready' | 'error' = isLoading
    ? 'loading'
    : isError
      ? 'error'
      : aiReady
        ? 'ready'
        : 'error'

  return {
    prompts,
    loading: isLoading || (isFetching && !aiReady),
    aiReady,
    status,
  }
}
