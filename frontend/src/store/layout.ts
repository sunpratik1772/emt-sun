import type { Workflow, WorkflowNode } from '../types'

export const NODE_WIDTH = 240
/** Approximate rendered card height (header + status + optional tags). */
export const NODE_BOX_HEIGHT = 108
const DEFAULT_COL_GAP = 56
const DEFAULT_ROW_GAP = 72
const MIN_GAP = 28
/** Minimum clear space between node bounding boxes so edge arrows stay visible. */
export const MIN_NODE_BOX_GAP = MIN_GAP
const MAX_ROW_WIDTH = 1520
const ROW_HEIGHT = 132
const CANVAS_PAD_X = 80
const CANVAS_PAD_Y = 80
const DEFAULT_CENTER_Y = CANVAS_PAD_Y + 200
const COL_STRIDE = NODE_WIDTH + DEFAULT_COL_GAP

type WorkflowShape = Workflow
type WorkflowNodeShape = WorkflowNode

function buildGraph(workflow: WorkflowShape) {
  const nodeIds = workflow.nodes.map((n) => n.id)
  const orderIndex = new Map(nodeIds.map((id, i) => [id, i]))
  const byId = new Map(workflow.nodes.map((n) => [n.id, n]))
  const parents = new Map<string, string[]>(nodeIds.map((id) => [id, []]))
  const children = new Map<string, string[]>(nodeIds.map((id) => [id, []]))
  for (const e of workflow.edges) {
    if (!parents.has(e.to) || !children.has(e.from)) continue
    parents.get(e.to)!.push(e.from)
    children.get(e.from)!.push(e.to)
  }
  return { nodeIds, orderIndex, byId, parents, children }
}

function computeDepths(nodeIds: string[], parents: Map<string, string[]>, children: Map<string, string[]>) {
  const indegree = new Map(nodeIds.map((id) => [id, parents.get(id)!.length]))
  const depth = new Map<string, number>(nodeIds.map((id) => [id, 0]))
  const queue = nodeIds.filter((id) => indegree.get(id) === 0)
  while (queue.length) {
    const u = queue.shift()!
    const du = depth.get(u)!
    for (const v of children.get(u)!) {
      if ((depth.get(v) ?? 0) < du + 1) depth.set(v, du + 1)
      indegree.set(v, indegree.get(v)! - 1)
      if (indegree.get(v) === 0) queue.push(v)
    }
  }
  for (let pass = 0; pass < nodeIds.length; pass++) {
    let changed = false
    for (const id of nodeIds) {
      const ps = parents.get(id)!
      if (!ps.length) continue
      const next = Math.max(...ps.map((p) => depth.get(p) ?? 0)) + 1
      if ((depth.get(id) ?? 0) < next) {
        depth.set(id, next)
        changed = true
      }
    }
    if (!changed) break
  }
  return depth
}

function topoOrder(
  nodeIds: string[],
  parents: Map<string, string[]>,
  children: Map<string, string[]>,
  orderIndex: Map<string, number>,
): string[] {
  const indegree = new Map(nodeIds.map((id) => [id, parents.get(id)!.length]))
  const ready = nodeIds
    .filter((id) => indegree.get(id) === 0)
    .sort((a, b) => (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0))
  const out: string[] = []
  while (ready.length) {
    const u = ready.shift()!
    out.push(u)
    const next = [...(children.get(u) ?? [])].sort(
      (a, b) => (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0),
    )
    for (const v of next) {
      indegree.set(v, indegree.get(v)! - 1)
      if (indegree.get(v) === 0) {
        ready.push(v)
        ready.sort((a, b) => (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0))
      }
    }
  }
  if (out.length < nodeIds.length) return [...nodeIds].sort((a, b) => (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0))
  return out
}

function maxNodesPerDepth(workflow: WorkflowShape): number {
  const { nodeIds, parents, children } = buildGraph(workflow)
  const depth = computeDepths(nodeIds, parents, children)
  const counts = new Map<number, number>()
  for (const id of nodeIds) {
    const d = depth.get(id) ?? 0
    counts.set(d, (counts.get(d) ?? 0) + 1)
  }
  return Math.max(0, ...counts.values())
}

function nodesPerRow(): number {
  return Math.max(1, Math.floor((MAX_ROW_WIDTH + DEFAULT_COL_GAP) / COL_STRIDE))
}

function gapForCount(count: number, axisStride: number, maxSpan: number): number {
  if (count <= 1) return 0
  const ideal = axisStride
  const needed = count * NODE_WIDTH + (count - 1) * ideal
  if (needed <= maxSpan) return ideal
  const tight = (maxSpan - count * NODE_WIDTH) / (count - 1)
  return Math.max(MIN_GAP, tight)
}

function rowCenterY(
  ids: string[],
  parents: Map<string, string[]>,
  positions: Map<string, { x: number; y: number }>,
): number {
  const parentYs: number[] = []
  for (const id of ids) {
    for (const p of parents.get(id) ?? []) {
      const py = positions.get(p)?.y
      if (typeof py === 'number') parentYs.push(py)
    }
  }
  if (parentYs.length) return parentYs.reduce((a, b) => a + b, 0) / parentYs.length
  return DEFAULT_CENTER_Y
}

function sortColumnIds(
  ids: string[],
  orderIndex: Map<string, number>,
  parents: Map<string, string[]>,
  positions: Map<string, { x: number; y: number }>,
): string[] {
  return [...ids].sort((a, b) => {
    const tie = (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0)
    const psA = parents.get(a) ?? []
    const psB = parents.get(b) ?? []
    const baryA = psA.length
      ? psA.map((p) => positions.get(p)?.y ?? DEFAULT_CENTER_Y).reduce((x, y) => x + y, 0) / psA.length
      : DEFAULT_CENTER_Y
    const baryB = psB.length
      ? psB.map((p) => positions.get(p)?.y ?? DEFAULT_CENTER_Y).reduce((x, y) => x + y, 0) / psB.length
      : DEFAULT_CENTER_Y
    return baryA - baryB || tie
  })
}

/** Linear pipeline: horizontal rows, wrapping down when the row is full. */
function layoutLinearChainWrap(orderedIds: string[]): Map<string, { x: number; y: number }> {
  const perRow = nodesPerRow()
  const positions = new Map<string, { x: number; y: number }>()

  orderedIds.forEach((id, i) => {
    const row = Math.floor(i / perRow)
    const col = i % perRow
    positions.set(id, {
      x: CANVAS_PAD_X + col * COL_STRIDE,
      y: CANVAS_PAD_Y + row * ROW_HEIGHT,
    })
  })

  return positions
}

/** Branching DAG: depth moves left→right; siblings stack vertically. */
function layoutHorizontalWithVerticalBranches(workflow: WorkflowShape): Map<string, { x: number; y: number }> {
  const { nodeIds, orderIndex, parents, children } = buildGraph(workflow)
  const depth = computeDepths(nodeIds, parents, children)

  const byDepth = new Map<number, string[]>()
  for (const id of nodeIds) {
    const d = depth.get(id) ?? 0
    if (!byDepth.has(d)) byDepth.set(d, [])
    byDepth.get(d)!.push(id)
  }

  const positions = new Map<string, { x: number; y: number }>()
  const sortedDepths = [...byDepth.keys()].sort((a, b) => a - b)

  for (const d of sortedDepths) {
    const ids = byDepth.get(d)!
    const x = CANVAS_PAD_X + d * COL_STRIDE
    const sorted = sortColumnIds(ids, orderIndex, parents, positions)

    if (sorted.length === 1) {
      const id = sorted[0]!
      const ps = parents.get(id) ?? []
      let y = DEFAULT_CENTER_Y
      if (ps.length === 1 && (children.get(ps[0]!)?.length ?? 0) <= 1) {
        y = positions.get(ps[0]!)?.y ?? DEFAULT_CENTER_Y
      } else if (ps.length >= 1) {
        y = rowCenterY([id], parents, positions)
      }
      positions.set(id, { x, y })
      continue
    }

    const gap = gapForCount(sorted.length, DEFAULT_ROW_GAP, 720)
    const stride = ROW_HEIGHT + Math.max(0, gap - DEFAULT_ROW_GAP)
    const stackHeight = (sorted.length - 1) * stride
    const centerY = rowCenterY(sorted, parents, positions)
    const startY = centerY - stackHeight / 2

    sorted.forEach((id, index) => {
      positions.set(id, { x, y: startY + index * stride })
    })
  }

  return positions
}

/** Horizontal-first layout: pipeline rows with vertical stacks only for branches or wrap. */
export function layoutWorkflowPrimary(workflow: WorkflowShape): Map<string, { x: number; y: number }> {
  const { nodeIds, orderIndex, parents, children } = buildGraph(workflow)
  if (maxNodesPerDepth(workflow) === 1) {
    const ordered = topoOrder(nodeIds, parents, children, orderIndex)
    return layoutLinearChainWrap(ordered)
  }
  return layoutHorizontalWithVerticalBranches(workflow)
}

/** @deprecated alias */
export function layoutHierarchyTopDown(workflow: WorkflowShape): Map<string, { x: number; y: number }> {
  return layoutWorkflowPrimary(workflow)
}

/** True when any two node cards overlap or sit closer than edge arrows need. */
export function hasCrampedOrOverlappingNodes(
  nodes: WorkflowNodeShape[],
  minGap = MIN_NODE_BOX_GAP,
): boolean {
  const positioned = nodes.filter((n) => n.position)
  if (positioned.length < 2) return false

  for (let i = 0; i < positioned.length; i++) {
    for (let j = i + 1; j < positioned.length; j++) {
      const a = positioned[i].position!
      const b = positioned[j].position!
      const gapX =
        Math.max(a.x, b.x) - Math.min(a.x + NODE_WIDTH, b.x + NODE_WIDTH)
      const gapY =
        Math.max(a.y, b.y) - Math.min(a.y + NODE_BOX_HEIGHT, b.y + NODE_BOX_HEIGHT)
      if (gapX < minGap && gapY < minGap) return true
    }
  }
  return false
}

/** Detect layouts that should be re-auto-laid (missing coords, wrong vertical strip, overflow row). */
export function needsAutoRelayout(workflow: WorkflowShape | WorkflowNodeShape[]): boolean {
  const nodes = Array.isArray(workflow) ? workflow : workflow.nodes
  const edges = Array.isArray(workflow) ? [] : workflow.edges

  if (nodes.length === 0) return false
  if (nodes.some((n) => !n.position)) return true
  if (nodes.length < 2) return false
  if (hasCrampedOrOverlappingNodes(nodes)) return true

  const xs = nodes.map((n) => n.position!.x)
  const ys = nodes.map((n) => n.position!.y)
  const xSpan = Math.max(...xs) - Math.min(...xs)
  const ySpan = Math.max(...ys) - Math.min(...ys)

  if (!Array.isArray(workflow) && edges.length > 0) {
    const wf = workflow as WorkflowShape
    const maxPerDepth = maxNodesPerDepth(wf)

    if (maxPerDepth === 1) {
      // Linear chain saved as a vertical column — should be horizontal / wrapped.
      if (ySpan >= ROW_HEIGHT * 1.4 && xSpan < NODE_WIDTH * 0.5) return true
      // Single row spilling past viewport — should wrap vertically.
      const perRow = nodesPerRow()
      if (nodes.length > perRow && ySpan < ROW_HEIGHT * 0.75 && xSpan > MAX_ROW_WIDTH * 0.85) return true
    }
  }

  // AI / import coords often sprawl wider than our wrapped row budget.
  const perRow = nodesPerRow()
  const wrappedBudget = CANVAS_PAD_X + perRow * COL_STRIDE + NODE_WIDTH
  if (xSpan > Math.max(MAX_ROW_WIDTH * 1.08, wrappedBudget * 1.05)) return true

  return false
}

/** @deprecated alias */
export function needsHierarchyRelayout(workflow: WorkflowShape | WorkflowNodeShape[]): boolean {
  return needsAutoRelayout(workflow)
}

export function layoutByTopology(workflow: WorkflowShape): Map<string, { x: number; y: number }> {
  return layoutWorkflowPrimary(workflow)
}

export function compactSparsePositions(
  nodes: WorkflowNodeShape[],
): Map<string, { x: number; y: number }> | null {
  if (nodes.length < 4) return null
  if (!nodes.every((n) => !!n.position)) return null
  const positioned = nodes.map((n) => ({ id: n.id, x: n.position!.x, y: n.position!.y }))
  const minX = Math.min(...positioned.map((p) => p.x))
  const maxX = Math.max(...positioned.map((p) => p.x))
  const minY = Math.min(...positioned.map((p) => p.y))
  const maxY = Math.max(...positioned.map((p) => p.y))
  const spanX = Math.max(1, maxX - minX)
  const spanY = Math.max(1, maxY - minY)

  const targetWidth = Math.max(880, Math.min(MAX_ROW_WIDTH, nodes.length * 248))
  const targetHeight = Math.max(480, Math.min(1200, nodes.length * 110))
  const scaleX = spanX > targetWidth * 1.12 ? targetWidth / spanX : 1
  const scaleY = spanY > targetHeight * 1.35 ? targetHeight / spanY : 1
  if (scaleX === 1 && scaleY === 1) return null

  const compacted = new Map<string, { x: number; y: number }>()
  for (const p of positioned) {
    compacted.set(p.id, {
      x: CANVAS_PAD_X + (p.x - minX) * scaleX,
      y: CANVAS_PAD_Y + (p.y - minY) * scaleY,
    })
  }
  return compacted
}

export function layoutAndCompactWorkflow(workflow: Workflow): Workflow {
  const shouldLayout =
    workflow.nodes.some((n) => !n.position) || needsAutoRelayout(workflow)

  let nodes = workflow.nodes
  if (shouldLayout) {
    const autoPositions = layoutWorkflowPrimary(workflow)
    nodes = workflow.nodes.map((n) => ({
      ...n,
      position: autoPositions.get(n.id) ?? { x: CANVAS_PAD_X, y: DEFAULT_CENTER_Y },
    }))
  }

  const compactedMap = compactSparsePositions(nodes)
  if (compactedMap) {
    const compactedNodes = nodes.map((n) => ({
      ...n,
      position: compactedMap.get(n.id) ?? n.position,
    }))
    if (!hasCrampedOrOverlappingNodes(compactedNodes)) {
      nodes = compactedNodes
    }
  }

  return { ...workflow, nodes }
}
