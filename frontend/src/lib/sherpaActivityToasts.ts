import { toast } from '../store/toastStore'
import type { CopilotStreamEvent, RunWorkflowStreamEvent } from '../types'

const DEDUPE_MS = 1400
const recent = new Map<string, number>()

function pushOnce(key: string, fn: () => void, windowMs = DEDUPE_MS): void {
  const now = Date.now()
  if (now - (recent.get(key) ?? 0) < windowMs) return
  recent.set(key, now)
  fn()
}

function clip(text: string, max = 160): string {
  const t = text.trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}

/** Global bottom-right toasts — high-level milestones only (not substages). */
export function notifyCopilotStreamActivity(ev: CopilotStreamEvent): void {
  switch (ev.type) {
    case 'workflow_created':
      pushOnce(
        `workflow:${ev.workflowId || ev.name}`,
        () =>
          toast.success(
            `Workflow generated · ${ev.name} (${ev.nodeCount} node${ev.nodeCount === 1 ? '' : 's'} on canvas)`,
          ),
        4000,
      )
      break
    case 'automation_created':
      pushOnce(
        `automation:${ev.automation_id}`,
        () => {
          const sched = ev.schedule_summary?.trim()
          toast.success(
            sched
              ? `Automation created · ${ev.name} · ${sched}`
              : `Automation created · ${ev.name}`,
          )
        },
        4000,
      )
      break
    case 'error':
      pushOnce(`copilot-err:${ev.message.slice(0, 48)}`, () =>
        toast.error(clip(ev.message, 200)),
      )
      break
    default:
      break
  }
}

/** Toasts for workflow execution — run finished / failed only (node progress stays in chat). */
export function notifyRunStreamActivity(ev: RunWorkflowStreamEvent): void {
  switch (ev.type) {
    case 'workflow_complete':
      pushOnce('run:complete', () => toast.success('Workflow run complete'))
      break
    case 'workflow_error':
      pushOnce('run:error', () => toast.error('Workflow run failed'))
      break
    case 'node_error': {
      const name = ev.label?.trim() || ev.node_id || 'Step'
      toast.error(clip(`Node failed · ${name}: ${ev.error || 'Unknown error'}`, 200))
      break
    }
    default:
      break
  }
}

/** @internal test helper */
export function resetSherpaActivityToastDedupe(): void {
  recent.clear()
}
