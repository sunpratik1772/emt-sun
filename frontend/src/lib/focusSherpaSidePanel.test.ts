import { describe, expect, it, beforeEach } from 'vitest'
import { focusSherpaSidePanel } from './focusSherpaSidePanel'
import { useWorkflowStore } from '../store/workflowStore'

describe('focusSherpaSidePanel', () => {
  beforeEach(() => {
    useWorkflowStore.setState({
      rightPanelMode: null,
      sherpaPanelPopAt: 0,
    })
  })

  it('opens copilot side panel and bumps pop timestamp', () => {
    const before = useWorkflowStore.getState().sherpaPanelPopAt
    focusSherpaSidePanel()
    const s = useWorkflowStore.getState()
    expect(s.rightPanelMode).toBe('copilot')
    expect(s.sherpaPanelPopAt).toBeGreaterThan(before)
  })
})
