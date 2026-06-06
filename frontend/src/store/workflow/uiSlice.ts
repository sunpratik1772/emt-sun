import { clampPane, PANE_LIMITS, readPaneSizes, writePaneSizes } from './paneUtils'
import type { WorkflowSetState, WorkflowStore } from './types'

export function createUiSlice(
  set: WorkflowSetState,
): Pick<
  WorkflowStore,
  | 'workspaceView'
  | 'setWorkspaceView'
  | 'workspaceEditMode'
  | 'setWorkspaceEditMode'
  | 'workflowDrawerOpen'
  | 'setWorkflowDrawerOpen'
  | 'paletteWidth'
  | 'copilotWidth'
  | 'setPaletteWidth'
  | 'setCopilotWidth'
  | 'rightPanelMode'
  | 'setRightPanelMode'
  | 'toggleRightPanelMode'
  | 'outputOrientation'
  | 'setOutputOrientation'
  | 'toggleOutputOrientation'
  | 'outputSummarySource'
  | 'outputSummaryAt'
  | 'environment'
  | 'setEnvironment'
  | 'mobilePaletteOpen'
  | 'setMobilePaletteOpen'
  | 'toggleMobilePaletteOpen'
  | 'sherpaPanelPopAt'
> {
  const initialPanes = readPaneSizes()
  return {
    workspaceView: 'canvas',
    workspaceEditMode: 'view',
    workflowDrawerOpen: false,
    paletteWidth: initialPanes.paletteWidth,
    copilotWidth: initialPanes.copilotWidth,
    rightPanelMode: 'copilot',
    outputOrientation: 'side',
    outputSummarySource: null,
    outputSummaryAt: null,
    environment: 'dev',
    mobilePaletteOpen: false,
    sherpaPanelPopAt: 0,

    setWorkspaceView: (workspaceView) => set({ workspaceView }),
    setWorkspaceEditMode: (workspaceEditMode) =>
      set({
        workspaceEditMode,
        ...(workspaceEditMode === 'edit' ? { rightPanelMode: 'copilot' as const } : {}),
      }),
    setWorkflowDrawerOpen: (v) => set({ workflowDrawerOpen: v }),

    setPaletteWidth: (px) =>
      set((s) => {
        const next = clampPane(px, PANE_LIMITS.paletteWidth.min, PANE_LIMITS.paletteWidth.max)
        writePaneSizes({ paletteWidth: next, copilotWidth: s.copilotWidth })
        return { paletteWidth: next }
      }),

    setCopilotWidth: (px) =>
      set((s) => {
        const next = clampPane(px, PANE_LIMITS.copilotWidth.min, PANE_LIMITS.copilotWidth.max)
        writePaneSizes({ paletteWidth: s.paletteWidth, copilotWidth: next })
        return { copilotWidth: next }
      }),

    setRightPanelMode: (m) => set({ rightPanelMode: m }),
    toggleRightPanelMode: (m) =>
      set((s) => {
        const next = s.rightPanelMode === m ? null : m
        if (next === 'copilot') {
          return { rightPanelMode: next, sherpaPanelPopAt: Date.now() }
        }
        return { rightPanelMode: next }
      }),

    setOutputOrientation: (outputOrientation) => set({ outputOrientation }),
    toggleOutputOrientation: () =>
      set((s) => ({ outputOrientation: s.outputOrientation === 'bottom' ? 'side' : 'bottom' })),

    setEnvironment: (environment) => set({ environment }),

    setMobilePaletteOpen: (mobilePaletteOpen) => set({ mobilePaletteOpen }),
    toggleMobilePaletteOpen: () => set((s) => ({ mobilePaletteOpen: !s.mobilePaletteOpen })),
  }
}
