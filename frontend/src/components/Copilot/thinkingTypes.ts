export interface ThinkingStep {
  id: string
  text: string
  done: boolean
  startedAt: number
  durationSec?: number
  kind?: 'live' | 'parallel' | 'milestone' | 'stage' | 'subagent' | 'summary' | 'thinking'
  subagentName?: string
  subagentType?: string
  outcome?: string
  detail?: string
  status?: 'running' | 'done' | 'error'
  /** When true, only the title row is shown (Cursor-style collapsed step). */
  collapsed?: boolean
  /** Question-aware planning step tied to the user's prompt. */
  contextualPlan?: boolean
  /** Automated steps should never show elapsed time in the UI. */
  hideDuration?: boolean
}

export interface AgentFinalSummary {
  title: string
  bullets: string[]
  spawnedCount: number
  completedCount: number
  failedCount: number
}
