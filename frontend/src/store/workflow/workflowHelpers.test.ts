import { describe, expect, it } from 'vitest'
import type { WorkflowNode } from '../../types'
import { nextNodeId } from './workflowHelpers'

describe('nextNodeId', () => {
  it('returns n01 when no nodes exist', () => {
    expect(nextNodeId([])).toBe('n01')
  })

  it('skips occupied ids', () => {
    const existing: WorkflowNode[] = [
      { id: 'n01', type: 'input', label: 'Input', config: {} },
      { id: 'n02', type: 'output', label: 'Output', config: {} },
    ]
    expect(nextNodeId(existing)).toBe('n03')
  })

  it('fills gaps in the sequence', () => {
    const existing: WorkflowNode[] = [
      { id: 'n01', type: 'input', label: 'Input', config: {} },
      { id: 'n03', type: 'output', label: 'Output', config: {} },
    ]
    expect(nextNodeId(existing)).toBe('n02')
  })
})
