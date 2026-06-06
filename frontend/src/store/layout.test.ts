import { describe, expect, it } from 'vitest'
import {
  layoutAndCompactWorkflow,
  layoutWorkflowPrimary,
  needsAutoRelayout,
} from '../store/layout'
import type { Workflow } from '../types'

function chainWorkflow(count: number): Workflow {
  const nodes = Array.from({ length: count }, (_, i) => ({
    id: `n0${i + 1}`,
    type: 'passthrough',
    label: `Step ${i + 1}`,
    config: {},
  }))
  const edges = Array.from({ length: count - 1 }, (_, i) => ({
    from: `n0${i + 1}`,
    to: `n0${i + 2}`,
  }))
  return { workflow_id: 'wf', name: 'Chain', nodes, edges }
}

describe('layoutWorkflowPrimary', () => {
  it('lays linear pipelines out horizontally on one row', () => {
    const positions = layoutWorkflowPrimary(chainWorkflow(5))
    const ys = [...positions.values()].map((p) => p.y)
    const xs = [...positions.values()].map((p) => p.x)
    expect(new Set(xs).size).toBe(5)
    expect(Math.max(...ys) - Math.min(...ys)).toBe(0)
  })

  it('wraps long linear pipelines to fill vertical space when cramped', () => {
    const positions = layoutWorkflowPrimary(chainWorkflow(8))
    const ys = [...positions.values()].map((p) => p.y)
    expect(Math.max(...ys) - Math.min(...ys)).toBeGreaterThan(0)
  })

  it('stacks parallel branches vertically at the next column', () => {
    const wf: Workflow = {
      workflow_id: 'fork',
      name: 'Fork',
      nodes: [
        { id: 'n01', type: 'passthrough', label: 'Start', config: {} },
        { id: 'n02', type: 'passthrough', label: 'Left', config: {} },
        { id: 'n03', type: 'passthrough', label: 'Right', config: {} },
      ],
      edges: [
        { from: 'n01', to: 'n02' },
        { from: 'n01', to: 'n03' },
      ],
    }
    const positions = layoutWorkflowPrimary(wf)
    const start = positions.get('n01')!
    const left = positions.get('n02')!
    const right = positions.get('n03')!
    expect(left.y).not.toBe(right.y)
    expect(left.x).toBe(right.x)
    expect(left.x).toBeGreaterThan(start.x)
    expect(start.y).toBeCloseTo((left.y + right.y) / 2, 0)
  })

  it('relayouts cramped horizontal pipelines so edges stay visible', () => {
    const wf = chainWorkflow(4)
    wf.nodes = wf.nodes.map((n, i) => ({
      ...n,
      position: { x: 40 + i * 180, y: 300 },
    }))
    expect(needsAutoRelayout(wf)).toBe(true)
    const laid = layoutAndCompactWorkflow(wf)
    const xs = laid.nodes.map((n) => n.position!.x).sort((a, b) => a - b)
    for (let i = 1; i < xs.length; i++) {
      expect(xs[i] - xs[i - 1]).toBeGreaterThanOrEqual(268)
    }
  })

  it('relayouts vertical strips into horizontal flow', () => {
    const wf = chainWorkflow(5)
    wf.nodes = wf.nodes.map((n, i) => ({
      ...n,
      position: { x: 480, y: 80 + i * 132 },
    }))
    expect(needsAutoRelayout(wf)).toBe(true)
    const laid = layoutAndCompactWorkflow(wf)
    const ys = laid.nodes.map((n) => n.position!.y)
    const xs = laid.nodes.map((n) => n.position!.x)
    expect(Math.max(...xs) - Math.min(...xs)).toBeGreaterThan(200)
    expect(Math.max(...ys) - Math.min(...ys)).toBe(0)
  })

  it('relayouts AI-sprawled horizontal pipelines into wrapped rows', () => {
    const wf = chainWorkflow(6)
    wf.nodes = wf.nodes.map((n, i) => ({
      ...n,
      position: { x: 80 + i * 920, y: 120 },
    }))
    expect(needsAutoRelayout(wf)).toBe(true)
    const laid = layoutAndCompactWorkflow(wf)
    const xs = laid.nodes.map((n) => n.position!.x)
    expect(Math.max(...xs) - Math.min(...xs)).toBeLessThan(1700)
  })
})
