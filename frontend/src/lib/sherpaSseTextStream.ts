/**
 * Pace Sherpa SSE text_chunk events into the UI.
 * The fetch reader can deliver many frames in one turn; draining on a timer
 * gives progressive reveal without a separate typewriter hook.
 */
import { useWorkflowStore } from '../store/workflowStore'

const DRAIN_MS = 8
const CHARS_PER_TICK = 8

const pending: string[] = []
let draining = false
const flushWaiters: Array<() => void> = []

function notifyFlush(): void {
  if (draining || pending.length > 0) return
  const waiters = flushWaiters.splice(0)
  for (const resolve of waiters) resolve()
}

function pump(): void {
  if (!pending.length) {
    draining = false
    notifyFlush()
    return
  }
  let piece = ''
  while (piece.length < CHARS_PER_TICK && pending.length > 0) {
    const head = pending[0]
    const need = CHARS_PER_TICK - piece.length
    if (head.length <= need) {
      piece += pending.shift()
    } else {
      piece += head.slice(0, need)
      pending[0] = head.slice(need)
    }
  }
  const store = useWorkflowStore.getState()
  if (!store.copilotPlanPhaseStreaming) {
    const next = `${store.copilotStreamText}${piece}`
    store.patchCopilotStream({ copilotStreamText: next })
  }
  globalThis.setTimeout(pump, DRAIN_MS)
}

function scheduleDrain(): void {
  if (draining) return
  draining = true
  globalThis.setTimeout(pump, 0)
}

/** Mirror of visible stream text for stream-end assembly (service layer). */
export const sherpaStreamTextRef = { current: '' }

export function resetSherpaTextStream(): void {
  pending.length = 0
  draining = false
  sherpaStreamTextRef.current = ''
  useWorkflowStore.getState().patchCopilotStream({ copilotStreamText: '' })
}

export function beginSherpaTextStream(): void {
  resetSherpaTextStream()
}

export function enqueueSherpaTextChunk(chunk: string): void {
  if (!chunk) return
  sherpaStreamTextRef.current += chunk
  pending.push(chunk)
  scheduleDrain()
}

function syncStreamTextRefFromStore(): void {
  const store = useWorkflowStore.getState()
  if (store.copilotPlanPhaseStreaming) return
  sherpaStreamTextRef.current = store.copilotStreamText
}

export function flushSherpaTextStream(): Promise<void> {
  if (!draining && pending.length === 0) {
    syncStreamTextRefFromStore()
    return Promise.resolve()
  }
  return new Promise((resolve) => {
    flushWaiters.push(() => {
      syncStreamTextRefFromStore()
      resolve()
    })
  })
}
