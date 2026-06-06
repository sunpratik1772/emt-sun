import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkflowStore } from '../store/workflowStore'
import { openOutputPanelSummary, openRunOutputOnComplete } from './openOutputPanel'

describe('openOutputPanelSummary', () => {
  beforeEach(() => {
    useWorkflowStore.setState({
      rightPanelMode: 'copilot',
      outputOrientation: 'bottom',
      outputSummarySource: null,
      outputSummaryAt: null,
    })
  })

  it('opens side output panel with source and timestamp', () => {
    openOutputPanelSummary('save')
    const s = useWorkflowStore.getState()
    expect(s.rightPanelMode).toBe('output')
    expect(s.outputOrientation).toBe('side')
    expect(s.outputSummarySource).toBe('save')
    expect(s.outputSummaryAt).toBeTypeOf('number')
  })

  it('opens output on run completion without changing dock orientation', () => {
    useWorkflowStore.setState({ outputOrientation: 'bottom' })
    openRunOutputOnComplete()
    const s = useWorkflowStore.getState()
    expect(s.rightPanelMode).toBe('output')
    expect(s.outputOrientation).toBe('bottom')
    expect(s.outputSummarySource).toBe('run')
    expect(s.outputSummaryAt).toBeTypeOf('number')
  })
})
