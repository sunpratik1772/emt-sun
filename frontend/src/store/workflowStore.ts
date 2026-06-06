/**
 * Composed Zustand store for the workflow editor.
 *
 * State is split across slice modules under `./workflow/`:
 *   workflowSlice  — DAG editing, history, selection
 *   runStream      — SSE run event queue + run state
 *   copilotSlice   — chat messages + session
 *   uiSlice        — panels, panes, workspace chrome
 */
import { create } from 'zustand'
import { createCopilotSlice } from './workflow/copilotSlice'
import { createCopilotStreamSlice } from './workflow/copilotStreamSlice'
import { createRunSlice, finalizeStuckRunLog, flushRunEventQueue } from './workflow/runStream'
import { PANE_LIMITS } from './workflow/paneUtils'
import { createUiSlice } from './workflow/uiSlice'
import type { WorkflowStore } from './workflow/types'
import { createWorkflowSlice } from './workflow/workflowSlice'

export type { RightPanelMode, WorkspaceView, WorkflowSource, WorkflowStore } from './workflow/types'
export { PANE_LIMITS }
export { finalizeStuckRunLog, flushRunEventQueue }

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  ...createWorkflowSlice(set),
  ...createRunSlice(set),
  ...createCopilotSlice(set),
  ...createCopilotStreamSlice(set),
  ...createUiSlice(set),
}))
