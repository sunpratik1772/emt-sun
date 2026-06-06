import { describe, expect, it, beforeEach } from 'vitest'
import { useStudioSectionStore } from './studioSectionStore'

describe('studioSectionStore run history focus', () => {
  beforeEach(() => {
    useStudioSectionStore.setState({
      section: 'dashboard',
      automationId: null,
      runHistoryRunId: null,
      runHistoryAutoOpenModal: false,
      runHistoryPrefill: null,
      runOutputModalRun: null,
    })
  })

  it('opens run history with modal auto-open and prefill', () => {
    const prefill = { run_id: 'run_123', workflow: 'Test', started_at: new Date().toISOString(), status: 'success' as const }
    useStudioSectionStore.getState().openRunHistory('run_123', true, prefill)
    const s = useStudioSectionStore.getState()
    expect(s.section).toBe('run-history')
    expect(s.runHistoryRunId).toBe('run_123')
    expect(s.runHistoryAutoOpenModal).toBe(true)
    expect(s.runHistoryPrefill).toEqual(prefill)
    expect(s.automationId).toBeNull()
  })

  it('clears run history focus when leaving section', () => {
    useStudioSectionStore.getState().openRunHistory('run_123', true)
    useStudioSectionStore.getState().setSection('skills')
    const s = useStudioSectionStore.getState()
    expect(s.section).toBe('skills')
    expect(s.runHistoryRunId).toBeNull()
    expect(s.runHistoryAutoOpenModal).toBe(false)
    expect(s.runHistoryPrefill).toBeNull()
    expect(s.runOutputModalRun).toBeNull()
  })

  it('opens and closes the global run output modal', () => {
    const run = { run_id: 'run_abc', workflow: 'WF', started_at: new Date().toISOString(), status: 'success' as const }
    useStudioSectionStore.getState().openRunOutputModal(run)
    expect(useStudioSectionStore.getState().runOutputModalRun).toEqual(run)
    useStudioSectionStore.getState().closeRunOutputModal()
    expect(useStudioSectionStore.getState().runOutputModalRun).toBeNull()
  })
})
