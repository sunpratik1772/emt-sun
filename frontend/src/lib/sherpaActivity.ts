import type { CopilotActiveRoute } from '../store/workflow/copilotStreamSlice'
import type { CopilotRouteResponse, SherpaDispositionPayload } from '../services/api'

export type SherpaActivityMode =
  | 'thinking'
  | 'planning'
  | 'clarifying'
  | 'reviewing'
  | 'answering'
  | 'generating'
  | 'loading'
  | null

const MODE_LABELS: Record<Exclude<SherpaActivityMode, null>, string> = {
  thinking: 'Processing',
  planning: 'Planning',
  clarifying: 'Clarifying',
  reviewing: 'Analyzing',
  answering: 'Working on it',
  generating: 'Generating',
  loading: 'Loading',
}

/** Short reassurance shown beside the label while Sherpa is busy. */
const MODE_SUBTEXT: Record<Exclude<SherpaActivityMode, null>, string> = {
  thinking: 'Be with you shortly',
  planning: 'Drafting your plan',
  clarifying: 'One quick question',
  reviewing: 'Reviewing run output',
  answering: "We'll be with you shortly",
  generating: 'Building on the canvas',
  loading: 'Opening workflow',
}

export function sherpaActivityLabel(mode: SherpaActivityMode): string {
  if (!mode) return ''
  return MODE_LABELS[mode]
}

export function sherpaActivitySubtext(mode: SherpaActivityMode): string {
  if (!mode) return ''
  return MODE_SUBTEXT[mode]
}

export function resolveSherpaActivityMode(input: {
  isLoading: boolean
  activeRoute: CopilotActiveRoute
  disposition?: SherpaDispositionPayload | null
  routeIntent?: string | null
  pendingClarification?: boolean
  planPhaseStreaming?: boolean
  /** True only while the workflow harness is streaming onto the canvas. */
  harnessGenerating?: boolean
}): SherpaActivityMode {
  const {
    isLoading,
    activeRoute,
    disposition,
    routeIntent,
    pendingClarification,
    planPhaseStreaming,
    harnessGenerating = false,
  } = input

  if (pendingClarification) return 'clarifying'
  if (!isLoading) return null

  if (harnessGenerating) return 'generating'
  if (activeRoute === 'load') return 'loading'

  const kind = disposition?.kind || null
  const intent = routeIntent || ''

  if (planPhaseStreaming || kind === 'plan') return 'planning'
  if (kind === 'clarify') return 'clarifying'
  if (intent === 'explain_run' || intent === 'explain_error' || activeRoute === 'explain_run') {
    return 'reviewing'
  }
  if (kind === 'answer' || activeRoute === 'ask') return 'answering'
  return 'thinking'
}

export function activityModeFromRoute(route: CopilotRouteResponse, isLoading: boolean): SherpaActivityMode {
  return resolveSherpaActivityMode({
    isLoading,
    activeRoute: route.intent === 'build' ? 'build' : (route.intent as CopilotActiveRoute),
    disposition: route.disposition ?? null,
    routeIntent: route.intent,
    planPhaseStreaming: Boolean(route.metadata?.propose_build_plan || route.metadata?.propose_fix_plan),
  })
}
