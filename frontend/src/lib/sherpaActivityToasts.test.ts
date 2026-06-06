import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  notifyCopilotStreamActivity,
  notifyRunStreamActivity,
  resetSherpaActivityToastDedupe,
} from './sherpaActivityToasts'

const push = vi.fn()

vi.mock('../store/toastStore', () => ({
  toast: {
    success: (message: string) => push({ variant: 'success', message }),
    error: (message: string) => push({ variant: 'error', message }),
    info: (message: string) => push({ variant: 'info', message }),
    warning: (message: string) => push({ variant: 'warning', message }),
  },
}))

describe('sherpaActivityToasts', () => {
  beforeEach(() => {
    push.mockClear()
    resetSherpaActivityToastDedupe()
  })

  it('toasts workflow_created once', () => {
    notifyCopilotStreamActivity({
      type: 'workflow_created',
      workflowId: 'wf-1',
      name: 'FX Briefing',
      nodeCount: 5,
    })
    notifyCopilotStreamActivity({
      type: 'workflow_created',
      workflowId: 'wf-1',
      name: 'FX Briefing',
      nodeCount: 5,
    })
    expect(push).toHaveBeenCalledTimes(1)
    expect(push.mock.calls[0][0].message).toContain('Workflow generated')
  })

  it('toasts automation_created', () => {
    notifyCopilotStreamActivity({
      type: 'automation_created',
      automation_id: 'a1',
      name: 'Nightly digest',
      workflow_filename: 'nightly.yaml',
      cron_expression: '0 9 * * *',
      schedule_summary: 'Daily at 9:00',
    })
    expect(push.mock.calls[0][0].message).toContain('Automation created')
  })

  it('does not toast agent_stage substages', () => {
    notifyCopilotStreamActivity({
      type: 'agent_stage',
      stage_id: 's1',
      stage: 'Validating workflow',
      status: 'done',
      detail: 'Workflow validated',
    })
    expect(push).not.toHaveBeenCalled()
  })

  it('toasts only run complete not per-node lifecycle', () => {
    notifyRunStreamActivity({ type: 'workflow_start' })
    notifyRunStreamActivity({
      type: 'node_start',
      node_id: 'n01',
      label: 'Load CSV',
      index: 1,
      total: 3,
    })
    notifyRunStreamActivity({
      type: 'node_complete',
      node_id: 'n01',
      label: 'Load CSV',
      index: 1,
      total: 3,
    })
    notifyRunStreamActivity({ type: 'workflow_complete' })
    expect(push).toHaveBeenCalledTimes(1)
    expect(push.mock.calls[0][0].message).toContain('run complete')
  })
})
