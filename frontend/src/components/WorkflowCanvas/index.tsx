/**
 * The DAG editing canvas — wraps React Flow.
 *
 * Responsibilities:
 *   • Render every workflow node with `<CustomNode />` (sibling file).
 *   • Translate React Flow events (drag, drop, connect, delete, select)
 *     back into workflowStore actions.
 *   • Accept palette drops via HTML5 DnD — when a NodePanel item is
 *     dropped onto the canvas, we compute the world coordinates and
 *     call `addNode(type, position)`.
 *   • Show validation errors as red badges on the offending node,
 *     pulling from `useWorkflowStore.getState().validationIssues`.
 *
 * Nothing here knows the schema of a specific node type — palette
 * metadata comes from `nodeRegistryStore` (backend node-manifest).
 */
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
  type Node,
  type Edge,
  type NodeDragHandler,
  type OnSelectionChangeParams,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Undo2, Redo2, Grid, Layers, Plus, Minus, Maximize } from 'lucide-react'

// (icons used in empty state are inline below)
import { CustomNode } from './CustomNode'
import { Button } from '../ui/Button'
import { useWorkflowStore } from '../../store/workflowStore'
import { useThemeStore } from '../../store/themeStore'
import { layoutAndCompactWorkflow, needsAutoRelayout } from '../../store/layout'
import { useNodeRegistryStore, type NodeType } from '../../nodes'
import type { RunLogEntry } from '../../types'
import { useCanvasKeyboard } from './useCanvasKeyboard'
import NodeContextMenu, { type ContextMenuState } from './NodeContextMenu'
import { PALETTE_DND_MIME } from './constants'
import { launchSherpaPrompt } from '../../lib/launchSherpaPrompt'
import { useSherpaCanvasGenerating } from '../../hooks/useSherpaCanvasGenerating'
import { SherpaCanvasGeneratingOverlay } from './SherpaCanvasGeneratingOverlay'

const nodeTypes = { custom: CustomNode }

const CANVAS_PAD_X = 60
const CANVAS_PAD_Y = 260

const CANVAS_FIT = { padding: 0.2, includeHiddenNodes: true } as const
const SHERPA_COMPLETE_FIT_MS = 560

function runCanvasFit(
  fitView: ReturnType<typeof useReactFlow>['fitView'],
  duration: number,
  maxZoom = 1.02,
) {
  return fitView({ ...CANVAS_FIT, duration, maxZoom })
}

function flowSignature(workflow: ReturnType<typeof useWorkflowStore.getState>['workflow']): string {
  const { nodes, edges } = workflowToFlow(workflow)
  return JSON.stringify({
    nodes: nodes.map((n) => ({
      id: n.id,
      x: n.position.x,
      y: n.position.y,
      type: n.data.nodeType,
      label: n.data.label,
      disabled: n.data.disabled,
    })),
    edges: edges.map((e) => ({ s: e.source, t: e.target, sh: e.sourceHandle ?? null })),
  })
}

function positionsChanged(
  before: ReturnType<typeof useWorkflowStore.getState>['workflow'],
  after: ReturnType<typeof useWorkflowStore.getState>['workflow'],
): boolean {
  if (!before || !after) return false
  return after.nodes.some((n) => {
    const prev = before.nodes.find((p) => p.id === n.id)
    if (!prev?.position || !n.position) return true
    return prev.position.x !== n.position.x || prev.position.y !== n.position.y
  })
}
function workflowToFlow(workflow: ReturnType<typeof useWorkflowStore.getState>['workflow']) {
  if (!workflow) return { nodes: [], edges: [] }

  const nodes: Node[] = workflow.nodes.map((n) => ({
    id: n.id,
    type: 'custom',
    position: n.position ?? { x: CANVAS_PAD_X, y: CANVAS_PAD_Y },
    data: { label: n.label, nodeType: n.type, config: n.config, disabled: !!n.disabled },
  }))

  const edges: Edge[] = workflow.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.from,
    target: e.to,
    sourceHandle: e.sourceHandle,
    type: 'smoothstep',
    pathOptions: { borderRadius: 16, offset: 32 },
    animated: false,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 18,
      height: 18,
      color: 'var(--canvas-edge-stroke)',
    },
    style: { stroke: 'var(--canvas-edge-stroke)', strokeWidth: 2, opacity: 1 },
  }))

  return { nodes, edges }
}

function styleEdgesByRun(edges: Edge[], log: RunLogEntry[]): Edge[] {
  const byNode = new Map<string, RunLogEntry>()
  for (const e of log) byNode.set(e.node_id, e)
  return edges.map((e) => {
    const target = byNode.get(e.target as string)
    const source = byNode.get(e.source as string)
    if (target?.status === 'running') {
      return {
        ...e,
        className: 'edge--running',
        animated: false,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 18,
          height: 18,
          color: 'var(--running)',
        },
        style: { stroke: 'var(--running)', strokeWidth: 2.25, opacity: 1 },
      }
    }
    if (target?.status === 'ok') {
      return {
        ...e,
        className: 'edge--done',
        animated: false,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 18,
          height: 18,
          color: 'var(--success)',
        },
        style: { stroke: 'var(--success)', strokeWidth: 2.0, opacity: 0.95 },
      }
    }
    if (target?.status === 'error') {
      return {
        ...e,
        className: 'edge--error',
        animated: false,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 18,
          height: 18,
          color: 'var(--danger)',
        },
        style: { stroke: 'var(--danger)', strokeWidth: 2.25, opacity: 1 },
      }
    }
    // Source completed but target not yet started — subtle lead-in
    if (source?.status === 'ok') {
      return {
        ...e,
        className: '',
        animated: true,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 18,
          height: 18,
          color: 'var(--success)',
        },
        style: { stroke: 'var(--success)', strokeWidth: 1.75, opacity: 0.55 },
      }
    }
    return {
      ...e,
      className: '',
      animated: false,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 18,
        height: 18,
        color: 'var(--canvas-edge-stroke)',
      },
      style: { stroke: 'var(--canvas-edge-stroke)', strokeWidth: 2, opacity: 0.85 },
    }
  })
}

function EmptyCanvas({ onDragOver, onDrop }: { onDragOver: (e: DragEvent<HTMLDivElement>) => void; onDrop: (e: DragEvent<HTMLDivElement>) => void }) {
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const sherpaGenerating = useSherpaCanvasGenerating()

  function askSherpa(prompt?: string) {
    if (prompt?.trim()) {
      launchSherpaPrompt(prompt.trim())
      return
    }
    useWorkflowStore.getState().setRightPanelMode('copilot')
  }

  return (
    <div
      className={`flex-1 flex items-center justify-center p-6 min-h-0 relative workflow-canvas workflow-canvas--empty${sherpaGenerating ? ' workflow-canvas--generating' : ''}`}
      style={{ background: 'var(--canvas-bg)' }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="workflow-canvas-dots" aria-hidden />
      {sherpaGenerating ? <SherpaCanvasGeneratingOverlay /> : null}
      <div className="text-center relative z-10 max-w-md px-6" style={{ display: 'grid', gap: 16, justifyItems: 'center' }}>
        {/* Linear-style decorative chip */}
        <span
          className="font-mono"
          style={{
            fontSize: 10,
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
            color: 'var(--text-3)',
            padding: '4px 10px',
            borderRadius: 999,
            border: '1px solid var(--border)',
            background: 'var(--bg-2)',
          }}
        >
          new workflow
        </span>
        <h2
          className="display"
          style={{
            color: 'var(--text-0)',
            fontSize: 32,
            fontWeight: 540,
            letterSpacing: '-0.03em',
            lineHeight: 1.05,
          }}
        >
          Compose a workflow
        </h2>
        <p
          style={{
            color: 'var(--text-2)',
            fontSize: 13.5,
            lineHeight: 1.55,
            maxWidth: 440,
            letterSpacing: '-0.005em',
          }}
        >
          Drag nodes from the left palette, chain typed ports, or ask the{' '}
          <span style={{ color: 'var(--text-0)', fontWeight: 540 }}>sherpa</span> to generate the entire workflow for you.
        </p>
        <div className="flex items-center gap-2 mt-1">
          <Button
            variant="primary"
            size="md"
            onClick={() => setDrawerOpen(true)}
            style={{ height: 36, padding: '0 14px', borderRadius: 7, fontSize: 12.5, fontWeight: 540 }}
          >
            Load a template
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={() => askSherpa()}
            style={{ height: 36, padding: '0 14px', borderRadius: 7, fontSize: 12.5, fontWeight: 540 }}
          >
            Ask sherpa
          </Button>
        </div>
        <div
          className="flex items-center gap-2 mt-3 font-mono"
          style={{ fontSize: 10.5, color: 'var(--text-3)', letterSpacing: '0.02em' }}
        >
          <kbd>⌘</kbd>
          <kbd>K</kbd>
          <span>for commands</span>
        </div>
      </div>
    </div>
  )
}

export default function WorkflowCanvas() {
  // ReactFlowProvider is required so the inner shell can use `useReactFlow()`
  // for screen→flow coord conversion when handling palette drops.
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner />
    </ReactFlowProvider>
  )
}

function WorkflowCanvasInner() {
  const theme = useThemeStore((s) => s.theme)
  const workflow = useWorkflowStore((s) => s.workflow)
  const workflowViewportVersion = useWorkflowStore((s) => s.workflowViewportVersion)
  const runLog = useWorkflowStore((s) => s.runLog)
  const addNode = useWorkflowStore((s) => s.addNode)
  const updateNodePosition = useWorkflowStore((s) => s.updateNodePosition)
  const deleteNodes = useWorkflowStore((s) => s.deleteNodes)
  const deleteEdge = useWorkflowStore((s) => s.deleteEdge)
  const { screenToFlowPosition, fitView } = useReactFlow()
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [canvasFitPop, setCanvasFitPop] = useState(false)
  const prevSherpaGeneratingRef = useRef(false)
  const { copySelection } = useCanvasKeyboard(wrapperRef)

  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => workflowToFlow(workflow),
    [workflow]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const flowSyncRef = useRef('')
  const layoutAttemptRef = useRef<string | null>(null)

  // Re-sync React Flow when the workflow changes outside canvas gestures.
  useEffect(() => {
    const sig = flowSignature(workflow)
    if (flowSyncRef.current === sig) return
    flowSyncRef.current = sig
    const { nodes: n, edges: e } = workflowToFlow(workflow)
    setNodes(n)
    setEdges(e)
  }, [workflow, setNodes, setEdges])

  // Auto-layout once when imported/generated nodes need repositioning.
  useEffect(() => {
    const state = useWorkflowStore.getState()
    const wf = state.workflow
    if (!wf || !needsAutoRelayout(wf)) {
      layoutAttemptRef.current = null
      return
    }

    const attemptKey = wf.nodes
      .map((n) => `${n.id}:${n.position?.x ?? 'x'},${n.position?.y ?? 'y'}`)
      .join('|')
    if (layoutAttemptRef.current === attemptKey) return
    layoutAttemptRef.current = attemptKey

    const fixed = layoutAndCompactWorkflow(wf)
    if (needsAutoRelayout(fixed)) return
    if (!positionsChanged(wf, fixed)) return

    useWorkflowStore.setState({
      workflow: fixed,
      workflowViewportVersion: state.workflowViewportVersion + 1,
    })
  }, [workflow])

  // Derive edge styling from run state without mutating layout
  const displayEdges = useMemo(() => styleEdgesByRun(edges, runLog), [edges, runLog])

  const sherpaGenerating = useSherpaCanvasGenerating()

  // Re-fit when a workflow is externally loaded/replaced. Skip while Sherpa is
  // still streaming so we do not frame a half-open output panel or sprawl layout.
  useEffect(() => {
    const wf = useWorkflowStore.getState().workflow
    if (!wf || wf.nodes.length === 0 || sherpaGenerating) return
    let timeoutId: number | null = null
    const rafId = requestAnimationFrame(() => {
      void runCanvasFit(fitView, 240)
      timeoutId = window.setTimeout(() => {
        void runCanvasFit(fitView, 180)
      }, 90)
    })
    return () => {
      cancelAnimationFrame(rafId)
      if (timeoutId != null) window.clearTimeout(timeoutId)
    }
  }, [workflowViewportVersion, fitView, sherpaGenerating])

  // After Sherpa build/load finishes: compact layout is applied in
  // focusStudioOnCopilotComplete; animate the viewport back into frame.
  useEffect(() => {
    const wasGenerating = prevSherpaGeneratingRef.current
    prevSherpaGeneratingRef.current = sherpaGenerating
    if (!wasGenerating || sherpaGenerating) return

    const wf = useWorkflowStore.getState().workflow
    if (!wf || wf.nodes.length === 0) return

    let cancelled = false
    let prepId: number | null = null
    let popId: number | null = null
    let clearPopId: number | null = null

    const playPopFit = () => {
      if (cancelled) return
      setCanvasFitPop(true)
      runCanvasFit(fitView, SHERPA_COMPLETE_FIT_MS, 1.02)
      clearPopId = window.setTimeout(() => setCanvasFitPop(false), SHERPA_COMPLETE_FIT_MS + 80)
    }

    const rafId = requestAnimationFrame(() => {
      prepId = window.setTimeout(() => {
        if (cancelled) return
        void runCanvasFit(fitView, 0, 1.02)
        popId = window.setTimeout(playPopFit, 48)
      }, 140)
    })

    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      if (prepId != null) window.clearTimeout(prepId)
      if (popId != null) window.clearTimeout(popId)
      if (clearPopId != null) window.clearTimeout(clearPopId)
      setCanvasFitPop(false)
    }
  }, [sherpaGenerating, fitView])

  // Keep graph comfortably framed when panes/window are resized.
  useEffect(() => {
    const wf = useWorkflowStore.getState().workflow
    if (!wf || wf.nodes.length === 0 || sherpaGenerating) return
    const host = wrapperRef.current
    if (!host || typeof ResizeObserver === 'undefined') return
    let timeoutId: number | null = null
    const observer = new ResizeObserver(() => {
      if (timeoutId != null) window.clearTimeout(timeoutId)
      timeoutId = window.setTimeout(() => {
        void runCanvasFit(fitView, 140)
      }, 160)
    })
    observer.observe(host)
    return () => {
      observer.disconnect()
      if (timeoutId != null) window.clearTimeout(timeoutId)
    }
  }, [workflowViewportVersion, fitView, sherpaGenerating])

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) =>
        addEdge({ ...params, type: 'smoothstep', style: { stroke: 'var(--accent)', strokeWidth: 1.75 } }, eds)
      ),
    [setEdges]
  )

  const onDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      const raw =
        e.dataTransfer.getData(PALETTE_DND_MIME) ||
        e.dataTransfer.getData('text/plain')
      if (!raw) return
      if (!useNodeRegistryStore.getState().nodeUI[raw]) return
      const type = raw as NodeType
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      addNode(type, position)
    },
    [addNode, screenToFlowPosition]
  )

  // Persist manual drags back to the workflow so position survives re-sync.
  const onNodeDragStop: NodeDragHandler = useCallback(
    (_ev, node) => updateNodePosition(node.id, node.position),
    [updateNodePosition]
  )

  // ReactFlow fires these when the user presses Delete on the canvas with
  // its built-in shortcut set. We forward to the store so edges referencing
  // removed nodes are cleaned up too.
  const onNodesDelete = useCallback(
    (deleted: Node[]) => deleteNodes(deleted.map((n) => n.id)),
    [deleteNodes],
  )
  const onEdgesDelete = useCallback(
    (deleted: Edge[]) =>
      deleted.forEach((e) => deleteEdge(e.source as string, e.target as string)),
    [deleteEdge],
  )

  // Right-click on a node → open context menu anchored at the cursor.
  const onNodeContextMenu = useCallback(
    (event: React.MouseEvent, node: Node) => {
      event.preventDefault()
      setContextMenu({ x: event.clientX, y: event.clientY, nodeId: node.id })
    },
    [],
  )

  // Right-click on empty canvas / node deselection → dismiss any open menu.
  const onPaneClick = useCallback(() => setContextMenu(null), [])
  const onPaneContextMenu = useCallback((e: React.MouseEvent | MouseEvent) => {
    // Prevent browser menu on the canvas backdrop. We'll add a pane-level
    // menu later if needed (paste clipboard here, etc.).
    e.preventDefault()
    setContextMenu(null)
  }, [])

  // When the selection changes, also close the menu so it doesn't drift.
  const onSelectionChange = useCallback((_p: OnSelectionChangeParams) => {
    setContextMenu(null)
  }, [])

  const [showGrid, setShowGrid] = useState(true)
  const [showMinimap, setShowMinimap] = useState(true)

  return (
    <div
      ref={wrapperRef}
      className={`absolute inset-0 workflow-canvas flex flex-col min-h-0${sherpaGenerating ? ' workflow-canvas--generating' : ''}${canvasFitPop ? ' workflow-canvas--fit-pop' : ''}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {workflow ? (
        <div className="flex-1 relative min-h-0" style={{ background: 'var(--canvas-bg)' }}>
          {sherpaGenerating ? <SherpaCanvasGeneratingOverlay /> : null}
          <ReactFlow
            nodes={nodes}
            edges={displayEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeDragStop={onNodeDragStop}
            onNodesDelete={onNodesDelete}
            onEdgesDelete={onEdgesDelete}
            onNodeContextMenu={onNodeContextMenu}
            onPaneClick={onPaneClick}
            onPaneContextMenu={onPaneContextMenu}
            onSelectionChange={onSelectionChange}
            nodeTypes={nodeTypes}
            deleteKeyCode={['Delete', 'Backspace']}
            multiSelectionKeyCode={['Meta', 'Shift', 'Control']}
            selectionKeyCode={['Shift']}
            fitView={!workflow.nodes.some((n) => n.position)}
            fitViewOptions={{ padding: CANVAS_FIT.padding, maxZoom: 1.02 }}
            minZoom={0.25}
            maxZoom={1.5}
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{
              type: 'smoothstep',
              pathOptions: { borderRadius: 16, offset: 24 },
            } as any}
          >
            {showGrid && (
              <Background
                id="workflow-dot-grid"
                variant={BackgroundVariant.Dots}
                gap={20}
                size={theme === 'altermind' ? 3.2 : 2.6}
                color="var(--canvas-dots-color)"
              />
            )}
            {showMinimap && (
              <MiniMap
                className="panel-glass !bg-[var(--panel-glass-bg)]"
                style={{
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                }}
                nodeColor={(n) => {
                  const nodeType = (n.data as { nodeType: string })?.nodeType
                  return useNodeRegistryStore.getState().nodeUI[nodeType]?.color ?? 'var(--text-3)'
                }}
                maskColor="var(--minimap-mask)"
                pannable
                zoomable
              />
            )}
          </ReactFlow>

          <CustomCanvasControls
            showGrid={showGrid}
            setShowGrid={setShowGrid}
            showMinimap={showMinimap}
            setShowMinimap={setShowMinimap}
          />
        </div>
      ) : (
        <EmptyCanvas onDragOver={onDragOver} onDrop={onDrop} />
      )}

      {contextMenu && (
        <NodeContextMenu
          menu={contextMenu}
          onClose={() => setContextMenu(null)}
          onCopy={() => copySelection()}
        />
      )}
    </div>
  )
}

function CustomCanvasControls({
  showGrid,
  setShowGrid,
  showMinimap,
  setShowMinimap,
}: {
  showGrid: boolean
  setShowGrid: (v: boolean) => void
  showMinimap: boolean
  setShowMinimap: (v: boolean) => void
}) {
  const { zoomIn, zoomOut, fitView } = useReactFlow()
  const undo = useWorkflowStore((s) => s.undo)
  const redo = useWorkflowStore((s) => s.redo)
  const historyIndex = useWorkflowStore((s) => s.historyIndex)
  const history = useWorkflowStore((s) => s.history)

  const canUndo = historyIndex > 0
  const canRedo = historyIndex < history.length - 1

  const btnStyle: React.CSSProperties = {
    width: 30,
    height: 30,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'transparent',
    border: 'none',
    color: 'var(--text-2)',
    cursor: 'pointer',
    borderRadius: 4,
    transition: 'background 120ms, color 120ms',
  }

  const activeBtnStyle: React.CSSProperties = {
    ...btnStyle,
    color: 'var(--accent)',
    background: 'color-mix(in srgb, var(--accent) 10%, transparent)',
  }

  const disabledBtnStyle: React.CSSProperties = {
    ...btnStyle,
    color: 'var(--text-3)',
    cursor: 'not-allowed',
    opacity: 0.4,
  }

  const handleMouseEnter = (e: React.MouseEvent<HTMLButtonElement>) => {
    const btn = e.currentTarget
    if (btn.disabled) return
    btn.style.background = 'var(--bg-3)'
    btn.style.color = 'var(--text-0)'
  }

  const handleMouseLeave = (e: React.MouseEvent<HTMLButtonElement>, active = false) => {
    const btn = e.currentTarget
    if (btn.disabled) return
    btn.style.background = active ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'transparent'
    btn.style.color = active ? 'var(--accent)' : 'var(--text-2)'
  }

  return (
    <div
      className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1 panel-glass"
      style={{
        border: '1px solid var(--border)',
        borderRadius: 20,
        padding: '4px 8px',
        boxShadow: 'var(--linear-elev-raised, none)',
      }}
    >
      <button
        type="button"
        title="Toggle Grid"
        style={showGrid ? activeBtnStyle : btnStyle}
        onClick={() => setShowGrid(!showGrid)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => handleMouseLeave(e, showGrid)}
      >
        <Grid size={14} strokeWidth={1.8} />
      </button>
      <button
        type="button"
        title="Zoom In"
        style={btnStyle}
        onClick={() => zoomIn({ duration: 150 })}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => handleMouseLeave(e)}
      >
        <Plus size={14} strokeWidth={1.8} />
      </button>
      <button
        type="button"
        title="Zoom Out"
        style={btnStyle}
        onClick={() => zoomOut({ duration: 150 })}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => handleMouseLeave(e)}
      >
        <Minus size={14} strokeWidth={1.8} />
      </button>
      <button
        type="button"
        title="Fit View"
        style={btnStyle}
        onClick={() => runCanvasFit(fitView, 280)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => handleMouseLeave(e)}
      >
        <Maximize size={14} strokeWidth={1.8} />
      </button>
      <button
        type="button"
        title="Undo"
        disabled={!canUndo}
        style={canUndo ? btnStyle : disabledBtnStyle}
        onClick={undo}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => handleMouseLeave(e)}
      >
        <Undo2 size={14} strokeWidth={1.8} />
      </button>
      <button
        type="button"
        title="Redo"
        disabled={!canRedo}
        style={canRedo ? btnStyle : disabledBtnStyle}
        onClick={redo}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => handleMouseLeave(e)}
      >
        <Redo2 size={14} strokeWidth={1.8} />
      </button>
      <button
        type="button"
        title="Toggle MiniMap"
        style={showMinimap ? activeBtnStyle : btnStyle}
        onClick={() => setShowMinimap(!showMinimap)}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={(e) => handleMouseLeave(e, showMinimap)}
      >
        <Layers size={14} strokeWidth={1.8} />
      </button>
    </div>
  )
}
