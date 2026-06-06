import { describe, expect, it, beforeEach, vi } from 'vitest'
import {
  beginSherpaTextStream,
  enqueueSherpaTextChunk,
  flushSherpaTextStream,
  resetSherpaTextStream,
  sherpaStreamTextRef,
} from './sherpaSseTextStream'
import { useWorkflowStore } from '../store/workflowStore'

describe('sherpaSseTextStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useWorkflowStore.setState({ copilotStreamText: '' })
    resetSherpaTextStream()
  })

  it('drains queued chunks into copilotStreamText', async () => {
    beginSherpaTextStream()
    enqueueSherpaTextChunk('hello world')

    const flushPromise = flushSherpaTextStream()
    await vi.runAllTimersAsync()
    await flushPromise

    expect(useWorkflowStore.getState().copilotStreamText).toBe('hello world')
    vi.useRealTimers()
  })

  it('buffers plan-phase chunks without revealing them in chat', async () => {
    useWorkflowStore.setState({ copilotPlanPhaseStreaming: true })
    beginSherpaTextStream()
    enqueueSherpaTextChunk('1. Load orders.csv\n2. Join products')

    const flushPromise = flushSherpaTextStream()
    await vi.runAllTimersAsync()
    await flushPromise

    expect(useWorkflowStore.getState().copilotStreamText).toBe('')
    expect(sherpaStreamTextRef.current).toContain('Load orders.csv')
    vi.useRealTimers()
  })
})
