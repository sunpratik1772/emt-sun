import { describe, expect, it, beforeEach } from 'vitest'
import { focusStudioOnCopilotComplete } from './copilotStreamService'
import { useWorkflowStore } from '../store/workflowStore'
import { useStudioSectionStore } from '../store/studioSectionStore'

describe('focusStudioOnCopilotComplete', () => {
  beforeEach(() => {
    useWorkflowStore.setState({
      workspaceView: 'code',
      workflowDrawerOpen: true,
      rightPanelMode: null,
    })
    useStudioSectionStore.setState({ section: 'automations', automationId: 'a1' })
  })

  it('closes overlays, shows canvas, and keeps Sherpa chat when a workflow landed', () => {
    const sprawled: import('../types').Workflow = {
      workflow_id: 'wf',
      name: 'Test',
      version: '1',
      description: '',
      nodes: [
        { id: 'n01', type: 'passthrough', label: 'A', config: {}, position: { x: 120, y: 90 } },
        { id: 'n02', type: 'passthrough', label: 'B', config: {}, position: { x: 2200, y: 90 } },
        { id: 'n03', type: 'passthrough', label: 'C', config: {}, position: { x: 4300, y: 90 } },
        { id: 'n04', type: 'passthrough', label: 'D', config: {}, position: { x: 6400, y: 90 } },
      ],
      edges: [
        { from: 'n01', to: 'n02' },
        { from: 'n02', to: 'n03' },
        { from: 'n03', to: 'n04' },
      ],
    }
    useWorkflowStore.setState({ workflow: sprawled })
    focusStudioOnCopilotComplete({ gotWorkflow: true })
    const wf = useWorkflowStore.getState()
    const studio = useStudioSectionStore.getState()
    expect(wf.workspaceView).toBe('canvas')
    expect(wf.workflowDrawerOpen).toBe(false)
    expect(wf.rightPanelMode).toBe('copilot')
    const xs = (wf.workflow?.nodes ?? []).map((n) => n.position?.x ?? 0)
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThan(1700)
    expect(studio.section).toBe(null)
    expect(studio.automationId).toBe(null)
  })
})
