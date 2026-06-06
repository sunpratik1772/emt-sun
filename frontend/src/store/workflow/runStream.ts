import { openRunOutputOnComplete } from '../../lib/openOutputPanel'
import { notifyRunStreamActivity } from '../../lib/sherpaActivityToasts'
import type { RunLogEntry, RunWorkflowStreamEvent } from '../../types'
import type { WorkflowSetState, WorkflowStore } from './types'

const MIN_NODE_DWELL_MS = 450

type QueuedEvent = { gen: number; ev: RunWorkflowStreamEvent }
const queue: QueuedEvent[] = []
let draining = false
let runGen = 0
const flushWaiters: Array<() => void> = []

function notifyFlushWaiters(): void {
  if (queue.length > 0 || draining) return
  const waiters = flushWaiters.splice(0)
  for (const resolve of waiters) resolve()
}
const uiStartedAt = new Map<string, number>()

let setState: WorkflowSetState | null = null

export function bindRunStream(set: WorkflowSetState): void {
  setState = set
}

function durationFromStarted(started_at?: string): number | undefined {
  if (!started_at) return undefined
  const startedMs = Date.parse(started_at)
  if (Number.isNaN(startedMs)) return undefined
  return Math.max(0, Date.now() - startedMs)
}

function finalizeRunningLog(log: RunLogEntry[]): RunLogEntry[] {
  let changed = false
  const next = log.map((e) => {
    if (e.status !== 'running') return e
    changed = true
    return {
      ...e,
      status: 'ok' as const,
      duration_ms: e.duration_ms ?? durationFromStarted(e.started_at),
    }
  })
  return changed ? next : log
}

function upsertRunLogEntry(log: RunLogEntry[], entry: RunLogEntry): RunLogEntry[] {
  const idx = log.findIndex((e) => e.node_id === entry.node_id)
  if (idx < 0) return [...log, entry]
  const copy = [...log]
  copy[idx] = entry
  return copy
}

function completeRunLogEntry(
  log: RunLogEntry[],
  nodeId: string,
  patch: Partial<RunLogEntry> & { status: 'ok' | 'error' },
): RunLogEntry[] | null {
  let idx = -1
  for (let i = log.length - 1; i >= 0; i--) {
    if (log[i].node_id === nodeId && log[i].status === 'running') {
      idx = i
      break
    }
  }
  if (idx < 0) {
    for (let i = log.length - 1; i >= 0; i--) {
      if (log[i].node_id === nodeId) {
        idx = i
        break
      }
    }
  }
  if (idx < 0) return null
  const copy = [...log]
  copy[idx] = { ...copy[idx], ...patch }
  return copy
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function applyNow(ev: RunWorkflowStreamEvent): void {
  notifyRunStreamActivity(ev)
  if (!setState) return
  setState((s) => {
    switch (ev.type) {
      case 'workflow_start':
        uiStartedAt.clear()
        return {
          runLog: [],
          runResult: null,
          runError: null,
          runTotalMs: null,
          validationIssues: null,
          runWarnings: null,
        }
      case 'node_start': {
        if (!ev.node_id) return {}
        const nowIso = new Date().toISOString()
        uiStartedAt.set(ev.node_id, Date.now())
        const entry: RunLogEntry = {
          node_id: ev.node_id,
          node_type: ev.node_type || '',
          label: ev.label || ev.node_id,
          index: ev.index ?? s.runLog.length + 1,
          total: ev.total ?? 0,
          status: 'running',
          started_at: nowIso,
        }
        return { runLog: upsertRunLogEntry(s.runLog, entry) }
      }
      case 'node_complete':
      case 'node_error': {
        if (!ev.node_id) return {}
        uiStartedAt.delete(ev.node_id)
        const log = completeRunLogEntry(s.runLog, ev.node_id, {
          status: ev.type === 'node_complete' ? 'ok' : 'error',
          duration_ms: ev.duration_ms,
          output: ev.output,
          error: ev.error,
          trace: ev.trace,
        })
        if (!log) return {}
        return { runLog: log }
      }
      case 'workflow_complete':
        uiStartedAt.clear()
        return {
          runLog: finalizeRunningLog(s.runLog),
          runResult: ev.result ?? null,
          runTotalMs: ev.total_duration_ms ?? null,
          runWarnings: ev.warnings ?? ev.result?.warnings ?? null,
        }
      case 'workflow_error': {
        uiStartedAt.clear()
        const validation = ev.validation
        const message = validation
          ? validation.errors.map((e) => e.message).join(' · ') ||
            `${validation.errors.length} validation error(s): ${validation.errors.map((e) => e.code).join(', ')}`
          : ev.error ?? 'Workflow error'
        return {
          runLog: finalizeRunningLog(s.runLog),
          runError: message,
          validationIssues: validation?.errors ?? null,
          runWarnings: validation?.warnings ?? null,
        }
      }
      default:
        return {}
    }
  })
  if (ev.type === 'workflow_complete' || ev.type === 'workflow_error') {
    openRunOutputOnComplete()
  }
}

async function drain(): Promise<void> {
  if (draining) return
  draining = true
  try {
    while (queue.length > 0) {
      const item = queue[0]
      if (item.gen !== runGen) {
        queue.shift()
        continue
      }
      const ev = item.ev

      if (ev.type === 'node_complete' || ev.type === 'node_error') {
        const uiStart = ev.node_id ? uiStartedAt.get(ev.node_id) : undefined
        if (uiStart != null) {
          const elapsed = Date.now() - uiStart
          const remaining = MIN_NODE_DWELL_MS - elapsed
          if (remaining > 0) await sleep(remaining)
        }
      }

      queue.shift()
      applyNow(ev)
    }
  } finally {
    draining = false
    if (queue.length > 0) {
      void drain()
    } else {
      notifyFlushWaiters()
    }
  }
}

/** Wait until all queued run SSE events have been applied to the store. */
export function flushRunEventQueue(): Promise<void> {
  if (queue.length === 0 && !draining) return Promise.resolve()
  return new Promise((resolve) => {
    flushWaiters.push(resolve)
    if (!draining) void drain()
  })
}

export function enqueueRunEvent(ev: RunWorkflowStreamEvent): void {
  if (ev.type === 'workflow_start') {
    runGen += 1
    queue.length = 0
    uiStartedAt.clear()
  }
  queue.push({ gen: runGen, ev })
  void drain()
}

export function resetRunStream(): void {
  runGen += 1
  queue.length = 0
  uiStartedAt.clear()
}

export function finalizeStuckRunLog(): void {
  uiStartedAt.clear()
  if (!setState) return
  setState((s) => {
    const runLog = finalizeRunningLog(s.runLog)
    return runLog === s.runLog ? {} : { runLog }
  })
}

export function createRunSlice(
  set: WorkflowSetState,
): Pick<
  WorkflowStore,
  | 'isRunning'
  | 'runResult'
  | 'runError'
  | 'validationIssues'
  | 'runWarnings'
  | 'runLog'
  | 'runTotalMs'
  | 'setRunning'
  | 'setRunResult'
  | 'setRunError'
  | 'setValidationIssues'
  | 'resetRun'
  | 'applyRunEvent'
> {
  bindRunStream(set)
  return {
    isRunning: false,
    runResult: null,
    runError: null,
    validationIssues: null,
    runWarnings: null,
    runLog: [],
    runTotalMs: null,
    setRunning: (v) => set({ isRunning: v }),
    setRunResult: (r) => set({ runResult: r }),
    setRunError: (e) => set({ runError: e }),
    setValidationIssues: (issues) => set({ validationIssues: issues }),
    resetRun: () => {
      resetRunStream()
      set({
        runResult: null,
        runError: null,
        runLog: [],
        runTotalMs: null,
        validationIssues: null,
        runWarnings: null,
      })
    },
    applyRunEvent: (ev) => enqueueRunEvent(ev),
  }
}
