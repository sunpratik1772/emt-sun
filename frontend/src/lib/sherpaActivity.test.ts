import { describe, expect, it } from 'vitest'
import {
  resolveSherpaActivityMode,
  sherpaActivityLabel,
  sherpaActivitySubtext,
} from './sherpaActivity'

describe('resolveSherpaActivityMode', () => {
  it('shows Generating only when harness is actively building', () => {
    expect(
      resolveSherpaActivityMode({
        isLoading: true,
        activeRoute: 'build',
        disposition: { kind: 'answer' },
        harnessGenerating: true,
      }),
    ).toBe('generating')
    expect(
      resolveSherpaActivityMode({
        isLoading: true,
        activeRoute: 'build',
        disposition: { kind: 'answer' },
        harnessGenerating: false,
      }),
    ).toBe('answering')
  })

  it('shows Planning during plan phase', () => {
    expect(
      resolveSherpaActivityMode({
        isLoading: true,
        activeRoute: 'ask',
        disposition: { kind: 'plan' },
        planPhaseStreaming: true,
      }),
    ).toBe('planning')
  })

  it('shows Analyzing for explain_run', () => {
    expect(
      resolveSherpaActivityMode({
        isLoading: true,
        activeRoute: 'explain_run',
        disposition: { kind: 'answer' },
        routeIntent: 'explain_run',
      }),
    ).toBe('reviewing')
  })

  it('shows Clarifying when questions panel is open', () => {
    expect(
      resolveSherpaActivityMode({
        isLoading: false,
        activeRoute: null,
        pendingClarification: true,
      }),
    ).toBe('clarifying')
  })

  it('shows Working on it for answer disposition', () => {
    expect(
      resolveSherpaActivityMode({
        isLoading: true,
        activeRoute: 'ask',
        disposition: { kind: 'answer' },
        routeIntent: 'ask',
      }),
    ).toBe('answering')
  })

  it('returns null when idle', () => {
    expect(resolveSherpaActivityMode({ isLoading: false, activeRoute: null })).toBeNull()
  })
})

describe('sherpaActivityLabel', () => {
  it('maps modes to user-facing labels', () => {
    expect(sherpaActivityLabel('generating')).toBe('Generating')
    expect(sherpaActivityLabel('planning')).toBe('Planning')
    expect(sherpaActivityLabel('reviewing')).toBe('Analyzing')
    expect(sherpaActivityLabel('thinking')).toBe('Processing')
  })
})

describe('sherpaActivitySubtext', () => {
  it('provides reassurance copy while live', () => {
    expect(sherpaActivitySubtext('thinking')).toBe('Be with you shortly')
    expect(sherpaActivitySubtext('answering')).toBe("We'll be with you shortly")
    expect(sherpaActivitySubtext('reviewing')).toContain('Reviewing')
    expect(sherpaActivitySubtext('generating')).toContain('canvas')
  })
})
