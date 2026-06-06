import type { ThinkingStep } from './thinkingTypes'

export const LIVE_ACTIVITY_ID = '__live__'
export const RUN_LIVE_ID = '__run_live__'
export const THINKING_STEP_ID = '__thinking__'

/** Seed the thinking block from the intent-layer preview returned by /copilot/route. */
export function thinkingStepFromPreview(text: string, done = false): ThinkingStep {
  const detail = (text || '').trim()
  return {
    id: THINKING_STEP_ID,
    text: 'Thinking',
    kind: 'thinking',
    detail,
    outcome: detail,
    done,
    subagentType: 'thinking',
    startedAt: Date.now(),
  }
}

export type AgentStageInput = {
  stage_id: string
  stage: string
  status: 'running' | 'done' | 'error'
  detail?: string
  subagent_name?: string
  subagent_type?: string
  outcome?: string
  contextual_plan?: boolean
  thinking_monologue?: boolean
}

const RAW_LABELS: Record<string, string> = {
  dispatch_parallel_tasks: 'Planning service topology',
  collect_parallel_results: 'Linking services',
  matched_blueprint: 'Matching blueprints',
  parallel_subagent: 'Running parallel agent',
}

function pastTense(text: string): string {
  const replacements: Array<[RegExp, string]> = [
    [/^Reading\b/i, 'Read'],
    [/^Checking\b/i, 'Checked'],
    [/^Gathering\b/i, 'Gathered'],
    [/^Analyzing\b/i, 'Analyzed'],
    [/^Planning\b/i, 'Planned'],
    [/^Drafting\b/i, 'Drafted'],
    [/^Applying\b/i, 'Applied'],
    [/^Repairing\b/i, 'Repaired'],
    [/^Validating\b/i, 'Validated'],
    [/^Running\b/i, 'Ran'],
    [/^Executing\b/i, 'Executed'],
    [/^Matching\b/i, 'Matched'],
    [/^Linking\b/i, 'Linked'],
    [/^Staging\b/i, 'Staged'],
    [/^Configuring\b/i, 'Configured'],
    [/^Defining\b/i, 'Defined'],
    [/^Resolving\b/i, 'Resolved'],
    [/^Verifying\b/i, 'Verified'],
    [/^Self-healing\b/i, 'Self-healed'],
  ]
  for (const [regex, replacement] of replacements) {
    if (regex.test(text)) {
      const match = text.match(regex)
      if (match) {
        const original = match[0]
        const isLowercase = original[0] === original[0].toLowerCase()
        return text.replace(regex, isLowercase ? replacement.toLowerCase() : replacement)
      }
    }
  }
  return text
}

const PARALLEL_TITLE_MAP: Record<string, string> = {
  'dataset and schema plan': 'Checking data sources',
  'topology and action plan': 'Designing workflow steps',
  'output artifact plan': 'Planning export',
  'data access plan': 'Checking data sources',
  'topology plan': 'Designing workflow steps',
}

export function humanizeParallelTitle(raw: string): string {
  const text = (raw || '').trim()
  if (!text) return 'Planning'
  return PARALLEL_TITLE_MAP[text.toLowerCase()] || text
}

/** Turn backend/internal labels into short user-facing activity copy. */
export function humanizeStepLabel(raw: string): string {
  const text = (raw || '').trim()
  if (!text) return 'Working…'
  const mapped = RAW_LABELS[text]
  if (mapped) return mapped
  const parallel = PARALLEL_TITLE_MAP[text.toLowerCase()]
  if (parallel) return parallel
  if (text.includes('_')) {
    return text.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  }
  return text
}

export function displayLabel(ev: AgentStageInput): string {
  const name = humanizeParallelTitle(ev.subagent_name || '')
  if (name && name !== 'Planning') return name

  const detail = (ev.detail || '').trim()
  const stage = humanizeStepLabel(ev.stage)

  if (detail && detail.length <= 160) {
    if (detail !== stage && !stage.toLowerCase().includes(detail.toLowerCase().slice(0, 24))) {
      return detail
    }
  }

  return stage || 'Working…'
}

function isThinkingMonologue(ev: AgentStageInput): boolean {
  return (
    ev.subagent_type === 'thinking' ||
    ev.thinking_monologue === true ||
    (ev.stage || '').trim().toLowerCase() === 'thinking'
  )
}

function isParallelAgent(ev: AgentStageInput): boolean {
  if (isThinkingMonologue(ev)) return true
  return !!(ev.subagent_name || ev.subagent_type)
}

function isContextualPlan(ev: AgentStageInput): boolean {
  return ev.subagent_type === 'context' || Boolean((ev as AgentStageInput & { contextual_plan?: boolean }).contextual_plan)
}

function isMicroPhase(stage: string): boolean {
  const s = stage.toLowerCase()
  return (
    s.includes('reading request') ||
    s.includes('reading context') ||
    s.includes('analyzing request') ||
    s.includes('resolving template') ||
    s.includes('matching blueprint') ||
    s.includes('matched blueprint') ||
    s.includes('planning service') ||
    s.includes('planning in parallel') ||
    s.includes('planning parallel') ||
    s.includes('linking service') ||
    s.includes('dispatch_parallel') ||
    s.includes('collect_parallel') ||
    s.includes('mechanical fix') ||
    s.includes('auto-fix') ||
    s.includes('auto_fix') ||
    s.includes('self-healing') ||
    s.includes('repair pass') ||
    s.includes('verifying build') ||
    s.includes('repairing workflow') ||
    s.includes('applying fix') ||
    s.includes('asking gemini') ||
    s.includes('parsing response')
  )
}

function shouldKeepWhenDone(ev: AgentStageInput): boolean {
  if (ev.status === 'error') return true
  if (isParallelAgent(ev)) return true
  const s = ev.stage.toLowerCase()
  return (
    s.includes('workflow generated') ||
    s.includes('creating nodes') ||
    s.includes('drafting workflow') ||
    s.includes('staging service') ||
    s.includes('generation error') ||
    s.includes('generation failed') ||
    s.includes('workflow validated') ||
    s.includes('workflow finished')
  )
}

function upsertLive(
  prev: ThinkingStep[],
  text: string,
  now: number,
  liveId = LIVE_ACTIVITY_ID,
  detail?: string,
): ThinkingStep[] {
  const kept = prev.filter((s) => s.id !== liveId)
  const existing = prev.find((s) => s.id === liveId)
  return [
    ...kept,
    {
      id: liveId,
      text,
      done: false,
      startedAt: existing?.startedAt ?? now,
      kind: 'live',
      status: 'running',
      detail: detail || existing?.detail,
      outcome: detail || existing?.outcome,
      collapsed: false,
      hideDuration: true,
    },
  ]
}

function removeLive(prev: ThinkingStep[], liveId = LIVE_ACTIVITY_ID): ThinkingStep[] {
  return prev.filter((s) => s.id !== liveId)
}

function errorStepTitle(ev: AgentStageInput, label: string): string {
  const agent = (ev.subagent_name || '').trim()
  if (agent) return agent
  return humanizeStepLabel(ev.stage) || label
}

function completedStepText(ev: AgentStageInput, label: string): string {
  if (ev.status === 'error') return errorStepTitle(ev, label)
  const named = humanizeParallelTitle(ev.subagent_name || '')
  if (named && named !== 'Planning') return pastTense(named)
  return pastTense(label)
}

function stepDetail(ev: AgentStageInput): string | undefined {
  const raw = (ev.outcome || ev.detail || '').trim()
  return raw || undefined
}

function markStepDone(
  prev: ThinkingStep[],
  idx: number,
  ev: AgentStageInput,
  label: string,
): ThinkingStep[] {
  const copy = [...prev]
  const detail = stepDetail(ev)
  const startedAt = copy[idx].startedAt
  const durationSec = startedAt
    ? Math.max(1, Math.round((Date.now() - startedAt) / 1000))
    : undefined
  copy[idx] = {
    ...copy[idx],
    text: completedStepText(ev, label),
    done: true,
    collapsed: true,
    status: ev.status,
    detail,
    outcome: detail || (ev.status === 'error' ? label : undefined),
    contextualPlan: isContextualPlan(ev) || copy[idx].contextualPlan,
    hideDuration: true,
    durationSec,
  }
  return copy
}

/** Convert the single live spinner row into a completed milestone in place. */
function finalizeLiveInPlace(
  prev: ThinkingStep[],
  liveId: string,
  patch: Omit<ThinkingStep, 'startedAt'> & { startedAt?: number },
): ThinkingStep[] {
  const liveIdx = prev.findIndex((s) => s.id === liveId)
  if (liveIdx < 0) {
    const now = Date.now()
    return [
      ...removeLive(prev, liveId),
      {
        startedAt: now,
        hideDuration: true,
        durationSec: undefined,
        ...patch,
      } as ThinkingStep,
    ]
  }

  const copy = [...prev]
  copy[liveIdx] = {
    ...copy[liveIdx],
    ...patch,
    startedAt: copy[liveIdx].startedAt,
    hideDuration: true,
    durationSec: undefined,
  }
  return copy
}

export function applyAgentStage(prev: ThinkingStep[], ev: AgentStageInput): ThinkingStep[] {
  const now = Date.now()
  const label = displayLabel(ev)
  const thinking = isThinkingMonologue(ev)
  const stageId = thinking ? THINKING_STEP_ID : ev.stage_id
  const idx = prev.findIndex((s) => s.id === stageId)
  const liveId = ev.stage_id.startsWith('run-') ? RUN_LIVE_ID : LIVE_ACTIVITY_ID

  if (isParallelAgent(ev)) {
    const detail = stepDetail(ev)
    const contextual = isContextualPlan(ev)
    if (ev.status === 'running') {
      const progress = detail
      const step: ThinkingStep = {
        id: thinking ? THINKING_STEP_ID : ev.stage_id,
        text: thinking ? 'Thinking…' : label,
        done: false,
        startedAt: idx >= 0 ? prev[idx].startedAt : now,
        kind: thinking ? 'thinking' : contextual ? 'milestone' : 'parallel',
        subagentName: ev.subagent_name,
        subagentType: ev.subagent_type,
        status: 'running',
        detail: progress,
        outcome: progress,
        collapsed: false,
        contextualPlan: contextual,
        hideDuration: true,
      }
      if (idx >= 0) {
        const copy = [...prev]
        copy[idx] = { ...copy[idx], ...step }
        return removeLive(copy)
      }
      return [...removeLive(prev), step]
    }

    if (ev.status === 'done') {
      if (thinking) {
        if (idx >= 0) {
          return markStepDone(prev, idx, ev, 'Thought')
        }
        return [
          ...removeLive(prev),
          {
            id: THINKING_STEP_ID,
            text: 'Thought',
            done: true,
            collapsed: true,
            startedAt: now,
            kind: 'thinking',
            subagentName: ev.subagent_name,
            subagentType: ev.subagent_type,
            status: ev.status,
            detail,
            outcome: detail,
            hideDuration: true,
          },
        ]
      }

      // Claude-style: completed parallel subagents are not shown in the timeline.
      if (idx >= 0) {
        const copy = [...prev]
        copy.splice(idx, 1)
        return copy
      }
      return prev
    }
  }

  if (ev.status === 'running') {
    return upsertLive(prev, label, now, liveId, stepDetail(ev))
  }

  if (ev.status === 'done' || ev.status === 'error') {
    if (shouldKeepWhenDone(ev)) {
      const doneText = completedStepText(ev, label)
      if (idx >= 0) {
        return markStepDone(prev, idx, ev, label)
      }
      return finalizeLiveInPlace(prev, liveId, {
        id: ev.stage_id,
        text: doneText,
        done: true,
        collapsed: true,
        kind: 'milestone',
        status: ev.status,
        detail: stepDetail(ev),
        outcome: stepDetail(ev) || (ev.status === 'error' ? label : undefined),
      })
    }

    if (isMicroPhase(ev.stage)) {
      return removeLive(prev, liveId)
    }

    return removeLive(prev, liveId)
  }

  return prev
}

/** Legacy/orchestrator `thinking` pulses — always one live row, never a pre-planned list. */
export function applyThinkingPulse(
  prev: ThinkingStep[],
  rawText: string,
  status: 'running' | 'done' = 'running',
): ThinkingStep[] {
  const label = humanizeStepLabel(rawText)
  if (status === 'done') {
    return removeLive(prev)
  }
  return upsertLive(prev, label, Date.now())
}

export function applyRunActivity(
  prev: ThinkingStep[],
  phase: 'workflow_start' | 'node_start' | 'node_complete' | 'node_error' | 'workflow_complete' | 'workflow_error',
  label?: string,
): ThinkingStep[] {
  const now = Date.now()
  switch (phase) {
    case 'workflow_start':
      return upsertLive(prev, 'Running workflow…', now, RUN_LIVE_ID)
    case 'node_start':
      return upsertLive(prev, label ? `Running ${label}…` : 'Running next step…', now, RUN_LIVE_ID)
    case 'node_complete':
      return prev
    case 'node_error':
      return upsertLive(prev, label ? `Issue in ${label}` : 'Run issue', now, RUN_LIVE_ID)
    case 'workflow_complete': {
      return finalizeLiveInPlace(prev, RUN_LIVE_ID, {
        id: `run-done-${now}`,
        text: 'Workflow finished',
        done: true,
        kind: 'milestone',
        status: 'done',
      })
    }
    case 'workflow_error': {
      return finalizeLiveInPlace(prev, RUN_LIVE_ID, {
        id: `run-error-${now}`,
        text: label ? `Run stopped — ${label}` : 'Run stopped',
        done: true,
        kind: 'milestone',
        status: 'error',
        outcome: label,
      })
    }
    default:
      return prev
  }
}

export function upsertThinkingStep(
  prev: ThinkingStep[],
  text: string,
  status: 'running' | 'done' = 'running',
  meta?: Partial<ThinkingStep>,
): ThinkingStep[] {
  if (meta?.id) {
    return applyAgentStage(prev, {
      stage_id: meta.id,
      stage: text,
      status: status === 'done' ? 'done' : 'running',
      detail: meta.outcome,
      subagent_name: meta.subagentName,
      subagent_type: meta.subagentType,
      outcome: meta.outcome,
    })
  }
  return applyThinkingPulse(prev, text, status)
}

function freezeStepDurationSec(step: ThinkingStep, now = Date.now()): number | undefined {
  if (step.durationSec != null) return Math.max(1, step.durationSec)
  if (step.startedAt) return Math.max(1, Math.round((now - step.startedAt) / 1000))
  return undefined
}

export function collapseAllThinkingSteps(prev: ThinkingStep[]): ThinkingStep[] {
  const now = Date.now()
  return prev
    .filter((s) => s.kind !== 'live')
    .map((s) => ({
      ...s,
      done: true,
      collapsed: true,
      status: s.status === 'error' ? 'error' : 'done',
      hideDuration: true,
      durationSec: freezeStepDurationSec(s, now),
    }))
}

export function closeAllThinkingSteps(prev: ThinkingStep[]): ThinkingStep[] {
  return collapseAllThinkingSteps(prev)
}

export function finalizeThinkingStep(prev: ThinkingStep[], _now = Date.now()): ThinkingStep[] {
  return removeLive(prev)
}

export function appendThinkingStep(prev: ThinkingStep[], text: string, meta?: Partial<ThinkingStep>): ThinkingStep[] {
  return upsertThinkingStep(prev, text, 'running', meta)
}
