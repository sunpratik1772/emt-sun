import type { Workflow, WorkflowNode } from '../../types'
import { filterLockedPatch, stripLockedMcpConfig } from '../../lib/integrationLocked'
import { layoutAndCompactWorkflow } from '../layout'
import { defaultNodeLabel, nextNodeId } from './workflowHelpers'
import type { WorkflowSetState, WorkflowStore } from './types'
import { resetRunStream } from './runStream'

export function createWorkflowSlice(
  set: WorkflowSetState,
): Pick<
  WorkflowStore,
  | 'workflow'
  | 'workflowViewportVersion'
  | 'sourceFilename'
  | 'sourceKind'
  | 'lastSavedSignature'
  | 'history'
  | 'historyIndex'
  | 'setWorkflow'
  | 'loadWorkflowFromFile'
  | 'loadDraftFromFile'
  | 'setDraftFilename'
  | 'markSaved'
  | 'newBlankWorkflow'
  | 'clearWorkflow'
  | 'undo'
  | 'redo'
  | 'addNode'
  | 'updateNodePosition'
  | 'updateNodeConfig'
  | 'renameNode'
  | 'deleteNodes'
  | 'deleteEdge'
  | 'duplicateNodes'
  | 'toggleNodeDisabled'
  | 'selectedNodeId'
  | 'selectNode'
> {
  return {
    workflow: null,
    workflowViewportVersion: 0,
    sourceFilename: null,
    sourceKind: null,
    lastSavedSignature: null,
    history: [],
    historyIndex: -1,
    selectedNodeId: null,

    undo: () =>
      set((s) => {
        if (s.historyIndex <= 0) return {}
        const idx = s.historyIndex - 1
        return {
          workflow: s.history[idx],
          historyIndex: idx,
          workflowViewportVersion: s.workflowViewportVersion + 1,
        }
      }),

    redo: () =>
      set((s) => {
        if (s.historyIndex >= s.history.length - 1) return {}
        const idx = s.historyIndex + 1
        return {
          workflow: s.history[idx],
          historyIndex: idx,
          workflowViewportVersion: s.workflowViewportVersion + 1,
        }
      }),

    setWorkflow: (w) =>
      set((s) => {
        const processed = layoutAndCompactWorkflow(stripLockedMcpConfig(w))
        return {
          workflow: processed,
          sourceFilename: null,
          sourceKind: null,
          lastSavedSignature: null,
          history: [processed],
          historyIndex: 0,
          workflowViewportVersion: s.workflowViewportVersion + 1,
        }
      }),

    loadWorkflowFromFile: (filename, w) =>
      set((s) => {
        const processed = layoutAndCompactWorkflow(stripLockedMcpConfig(w))
        return {
          workflow: processed,
          sourceFilename: filename,
          sourceKind: 'saved',
          lastSavedSignature: JSON.stringify(processed),
          history: [processed],
          historyIndex: 0,
          workflowViewportVersion: s.workflowViewportVersion + 1,
        }
      }),

    loadDraftFromFile: (filename, w) =>
      set((s) => {
        const processed = layoutAndCompactWorkflow(stripLockedMcpConfig(w))
        return {
          workflow: processed,
          sourceFilename: filename,
          sourceKind: 'draft',
          lastSavedSignature: JSON.stringify(processed),
          history: [processed],
          historyIndex: 0,
          workflowViewportVersion: s.workflowViewportVersion + 1,
        }
      }),

    setDraftFilename: (filename) =>
      set((s) => ({
        sourceFilename: filename,
        sourceKind: 'draft',
        lastSavedSignature: s.workflow ? JSON.stringify(s.workflow) : s.lastSavedSignature,
      })),

    markSaved: (filename) =>
      set((s) => ({
        sourceFilename: filename,
        sourceKind: 'saved',
        lastSavedSignature: s.workflow ? JSON.stringify(s.workflow) : null,
      })),

    newBlankWorkflow: () =>
      set({
        workflow: null,
        history: [],
        historyIndex: -1,
        sourceFilename: null,
        sourceKind: null,
        lastSavedSignature: null,
        runResult: null,
        runError: null,
        runLog: [],
        runTotalMs: null,
        selectedNodeId: null,
      }),

    clearWorkflow: () => {
      resetRunStream()
      set({
        workflow: null,
        history: [],
        historyIndex: -1,
        sourceFilename: null,
        sourceKind: null,
        lastSavedSignature: null,
        selectedNodeId: null,
        runResult: null,
        runError: null,
        runLog: [],
        runTotalMs: null,
        validationIssues: null,
        runWarnings: null,
        isRunning: false,
      })
    },

    addNode: (type, position) => {
      let newId = ''
      set((s) => {
        const existingNodes = s.workflow?.nodes ?? []
        newId = nextNodeId(existingNodes)
        const newNode: WorkflowNode = {
          id: newId,
          type,
          label: defaultNodeLabel(type, existingNodes),
          config: {},
          position,
        }
        const base: Workflow = s.workflow ?? {
          workflow_id: 'untitled',
          name: 'Untitled workflow',
          version: '0.1.0',
          description: '',
          nodes: [],
          edges: [],
        }
        const nextWorkflow = { ...base, nodes: [...base.nodes, newNode] }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
        }
      })
      return newId
    },

    updateNodePosition: (nodeId, position) =>
      set((s) => {
        if (!s.workflow) return {}
        const nodes = s.workflow.nodes.map((n) => (n.id === nodeId ? { ...n, position } : n))
        const nextWorkflow = { ...s.workflow, nodes }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
        }
      }),

    updateNodeConfig: (nodeId, patch) =>
      set((s) => {
        if (!s.workflow) return {}
        const nodes = s.workflow.nodes.map((n) => {
          if (n.id !== nodeId) return n
          const safePatch = filterLockedPatch(n.type, patch)
          const merged: Record<string, unknown> = { ...(n.config ?? {}), ...safePatch }
          for (const [k, v] of Object.entries(safePatch)) {
            if (v === null || v === undefined) delete merged[k]
          }
          return { ...n, config: merged }
        })
        const nextWorkflow = { ...s.workflow, nodes }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
        }
      }),

    renameNode: (nodeId, label) =>
      set((s) => {
        if (!s.workflow) return {}
        const nodes = s.workflow.nodes.map((n) => (n.id === nodeId ? { ...n, label } : n))
        const nextWorkflow = { ...s.workflow, nodes }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
        }
      }),

    deleteNodes: (nodeIds) =>
      set((s) => {
        if (!s.workflow || nodeIds.length === 0) return {}
        const drop = new Set(nodeIds)
        const nodes = s.workflow.nodes.filter((n) => !drop.has(n.id))
        const edges = s.workflow.edges.filter((e) => !drop.has(e.from) && !drop.has(e.to))
        const selectedNodeId = s.selectedNodeId && drop.has(s.selectedNodeId) ? null : s.selectedNodeId
        const nextWorkflow = { ...s.workflow, nodes, edges }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
          selectedNodeId,
        }
      }),

    deleteEdge: (fromId, toId) =>
      set((s) => {
        if (!s.workflow) return {}
        const edges = s.workflow.edges.filter((e) => !(e.from === fromId && e.to === toId))
        const nextWorkflow = { ...s.workflow, edges }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
        }
      }),

    duplicateNodes: (nodeIds, offset = { x: 40, y: 40 }) => {
      const newIds: string[] = []
      set((s) => {
        if (!s.workflow || nodeIds.length === 0) return {}
        const keep = new Set(nodeIds)
        const sourceNodes = s.workflow.nodes.filter((n) => keep.has(n.id))
        if (sourceNodes.length === 0) return {}

        const working: WorkflowNode[] = [...s.workflow.nodes]
        const idMap = new Map<string, string>()
        for (const src of sourceNodes) {
          const newId = nextNodeId(working)
          idMap.set(src.id, newId)
          const clone: WorkflowNode = {
            ...src,
            id: newId,
            label: `${src.label} (copy)`,
            config: JSON.parse(JSON.stringify(src.config ?? {})),
            position: src.position
              ? { x: src.position.x + offset.x, y: src.position.y + offset.y }
              : undefined,
          }
          working.push(clone)
          newIds.push(newId)
        }

        const clonedEdges = s.workflow.edges
          .filter((e) => idMap.has(e.from) && idMap.has(e.to))
          .map((e) => ({ from: idMap.get(e.from)!, to: idMap.get(e.to)! }))

        const nextWorkflow = {
          ...s.workflow,
          nodes: working,
          edges: [...s.workflow.edges, ...clonedEdges],
        }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
        }
      })
      return newIds
    },

    toggleNodeDisabled: (nodeId) =>
      set((s) => {
        if (!s.workflow) return {}
        const nodes = s.workflow.nodes.map((n) =>
          n.id === nodeId ? { ...n, disabled: !n.disabled } : n,
        )
        const nextWorkflow = { ...s.workflow, nodes }
        const nextHistory = s.history.slice(0, s.historyIndex + 1)
        return {
          workflow: nextWorkflow,
          history: [...nextHistory, nextWorkflow],
          historyIndex: nextHistory.length,
        }
      }),

    selectNode: (id) => set({ selectedNodeId: id }),
  }
}
