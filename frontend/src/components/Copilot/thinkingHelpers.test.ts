import { describe, expect, it } from 'vitest'
import {
  LIVE_ACTIVITY_ID,
  applyAgentStage,
  applyThinkingPulse,
  closeAllThinkingSteps,
  displayLabel,
  humanizeStepLabel,
} from './thinkingHelpers'
import type { ThinkingStep } from './thinkingTypes'

describe('humanizeStepLabel', () => {
  it('maps internal harness labels to readable copy', () => {
    expect(humanizeStepLabel('dispatch_parallel_tasks')).toBe('Planning service topology')
    expect(humanizeStepLabel('collect_parallel_results')).toBe('Linking services')
  })
})

describe('displayLabel', () => {
  it('prefers parallel agent names', () => {
    expect(
      displayLabel({
        stage_id: 'a',
        stage: 'parallel_subagent',
        status: 'running',
        subagent_name: 'Resolving postgres schema',
        subagent_type: 'explore',
      }),
    ).toBe('Resolving postgres schema')
  })

  it('uses detail for what is being checked', () => {
    expect(
      displayLabel({
        stage_id: 'b',
        stage: 'Checking node schema',
        status: 'running',
        detail: 'csv_reader output columns',
      }),
    ).toBe('csv_reader output columns')
  })
})

describe('applyAgentStage', () => {
  it('keeps the thinking monologue through output collapse', () => {
    let steps: ThinkingStep[] = []
    const monologue = 'User wants load orders.csv → sort rows → Excel export.\nDrafting now.'

    steps = applyAgentStage(steps, {
      stage_id: 'thinking-1',
      stage: 'Thinking',
      status: 'running',
      subagent_name: 'Thinking',
      subagent_type: 'thinking',
      thinking_monologue: true,
      detail: monologue,
      outcome: monologue,
    })
    steps = applyAgentStage(steps, {
      stage_id: 'thinking-1',
      stage: 'Thinking',
      status: 'done',
      subagent_name: 'Thinking',
      subagent_type: 'thinking',
      thinking_monologue: true,
      detail: monologue,
      outcome: monologue,
    })
    steps = closeAllThinkingSteps(steps)

    expect(steps).toHaveLength(1)
    expect(steps[0].kind).toBe('thinking')
    expect(steps[0].done).toBe(true)
    expect(steps[0].detail).toContain('orders.csv')
  })

  it('keeps automated phases in one live row that updates in place', () => {
    let steps: ThinkingStep[] = []

    steps = applyAgentStage(steps, {
      stage_id: 's1',
      stage: 'Reading request',
      status: 'running',
    })
    expect(steps).toHaveLength(1)
    expect(steps[0].id).toBe(LIVE_ACTIVITY_ID)
    expect(steps[0].done).toBe(false)

    steps = applyAgentStage(steps, {
      stage_id: 's1',
      stage: 'Analyzing request: hono api',
      status: 'running',
    })
    expect(steps).toHaveLength(1)
    expect(steps[0].text).toContain('Analyzing request')

    steps = applyAgentStage(steps, {
      stage_id: 's1',
      stage: 'Reading request',
      status: 'done',
    })
    expect(steps).toHaveLength(0)
  })

  it('shows parallel agents while running and removes them when done', () => {
    let steps: ThinkingStep[] = []

    steps = applyAgentStage(steps, {
      stage_id: 'p1',
      stage: 'parallel_subagent',
      status: 'running',
      subagent_name: 'Resolving postgres schema',
      subagent_type: 'explore',
    })
    steps = applyAgentStage(steps, {
      stage_id: 'p2',
      stage: 'parallel_subagent',
      status: 'running',
      subagent_name: 'Defining hono api topology',
      subagent_type: 'general',
    })

    expect(steps.filter((s) => !s.done)).toHaveLength(2)

    steps = applyAgentStage(steps, {
      stage_id: 'p1',
      stage: 'parallel_subagent',
      status: 'done',
      subagent_name: 'Resolving postgres schema',
      subagent_type: 'explore',
    })

    expect(steps.find((s) => s.id === 'p1')).toBeUndefined()
    expect(steps.filter((s) => !s.done)).toHaveLength(1)
  })

  it('converts live milestone rows in place instead of appending duplicates', () => {
    let steps: ThinkingStep[] = []

    steps = applyAgentStage(steps, {
      stage_id: 'm1',
      stage: 'Drafting workflow',
      status: 'running',
    })
    steps = applyAgentStage(steps, {
      stage_id: 'm1',
      stage: 'Drafting workflow',
      status: 'done',
    })

    expect(steps).toHaveLength(1)
    expect(steps[0].done).toBe(true)
    expect(steps[0].text).toBe('Drafted workflow')
    expect(steps[0].hideDuration).toBe(true)
    expect(steps[0].durationSec).toBeUndefined()
  })
})

describe('applyThinkingPulse', () => {
  it('never builds a pre-planned step list', () => {
    let steps: ThinkingStep[] = []
    const planned = ['Load data', 'Filter rows', 'Write output']

    for (const step of planned) {
      steps = applyThinkingPulse(steps, step, 'running')
    }

    expect(steps).toHaveLength(1)
    expect(steps[0].text).toBe('Write output')
    expect(steps[0].kind).toBe('live')
  })
})

describe('closeAllThinkingSteps', () => {
  it('drops ephemeral live rows and freezes durationSec on durable steps', () => {
    const steps: ThinkingStep[] = [
      {
        id: 'p1',
        text: 'Resolved postgres schema',
        done: false,
        startedAt: Date.now(),
        kind: 'parallel',
        status: 'running',
      },
      {
        id: LIVE_ACTIVITY_ID,
        text: 'Linking services',
        done: false,
        startedAt: Date.now(),
        kind: 'live',
        status: 'running',
      },
    ]

    const closed = closeAllThinkingSteps(steps)
    expect(closed).toHaveLength(1)
    expect(closed[0].done).toBe(true)
    expect(closed[0].durationSec).toBeGreaterThanOrEqual(1)
  })
})
