import type { AgentFinalSummary, ThinkingStep } from '../../components/Copilot/thinkingTypes'
import type { CopilotDraftRequest } from '../../lib/sherpaStarterPrompts'
import type {
  Workflow,
  RunResult,
  CopilotMessage,
  RunLogEntry,
  RunWorkflowStreamEvent,
  ValidationIssue,
  NodeType,
} from '../../types'
import type { CopilotActiveRoute } from './copilotStreamSlice'
import type { SherpaPendingClarification } from '../../components/Copilot/sherpaClarificationTypes'

export type RightPanelMode = 'config' | 'runlog' | 'output' | 'copilot' | null
export type WorkspaceView = 'canvas' | 'code'
export type WorkspaceEditMode = 'view' | 'edit'

/** Where the on-disk version of the current workflow lives. */
export type WorkflowSource = 'saved' | 'draft' | null

export interface WorkflowStore {
  workflow: Workflow | null
  workflowViewportVersion: number
  sourceFilename: string | null
  sourceKind: WorkflowSource
  lastSavedSignature: string | null
  setWorkflow: (w: Workflow) => void
  loadWorkflowFromFile: (filename: string, w: Workflow) => void
  loadDraftFromFile: (filename: string, w: Workflow) => void
  history: (Workflow | null)[]
  historyIndex: number
  undo: () => void
  redo: () => void
  copilotSessionId: string
  resetCopilotSession: () => void
  setCopilotSessionMessages: (msgs: CopilotMessage[]) => void
  setDraftFilename: (filename: string) => void
  markSaved: (filename: string) => void
  newBlankWorkflow: () => void
  clearWorkflow: () => void
  addNode: (type: NodeType, position: { x: number; y: number }) => string
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void
  updateNodeConfig: (nodeId: string, patch: Record<string, unknown>) => void
  renameNode: (nodeId: string, label: string) => void
  deleteNodes: (nodeIds: string[]) => void
  deleteEdge: (fromId: string, toId: string) => void
  duplicateNodes: (nodeIds: string[], offset?: { x: number; y: number }) => string[]
  toggleNodeDisabled: (nodeId: string) => void
  workspaceView: WorkspaceView
  setWorkspaceView: (view: WorkspaceView) => void
  workspaceEditMode: WorkspaceEditMode
  setWorkspaceEditMode: (mode: WorkspaceEditMode) => void
  workflowDrawerOpen: boolean
  setWorkflowDrawerOpen: (v: boolean) => void
  paletteWidth: number
  copilotWidth: number
  setPaletteWidth: (px: number) => void
  setCopilotWidth: (px: number) => void
  isRunning: boolean
  runResult: RunResult | null
  runError: string | null
  validationIssues: ValidationIssue[] | null
  runWarnings: ValidationIssue[] | null
  runLog: RunLogEntry[]
  runTotalMs: number | null
  setRunning: (v: boolean) => void
  setRunResult: (r: RunResult | null) => void
  setRunError: (e: string | null) => void
  setValidationIssues: (issues: ValidationIssue[] | null) => void
  resetRun: () => void
  applyRunEvent: (ev: RunWorkflowStreamEvent) => void
  selectedNodeId: string | null
  selectNode: (id: string | null) => void
  copilotMessages: CopilotMessage[]
  addCopilotMessage: (msg: CopilotMessage) => void
  appendToLastAssistantMessage: (chunk: string) => void
  clearCopilotMessages: () => void
  revertWorkflow: (index: number) => void
  redoWorkflow: (index: number) => void
  rightPanelMode: RightPanelMode
  setRightPanelMode: (m: RightPanelMode) => void
  toggleRightPanelMode: (m: RightPanelMode) => void
  copilotDraft: CopilotDraftRequest | null
  setCopilotDraft: (v: string | CopilotDraftRequest | null) => void
  requestCopilotPrompt: (text: string, autoSend?: boolean) => void
  copilotStreamActive: boolean
  copilotActiveRoute: CopilotActiveRoute
  /** True only while copilotGenerateStream is actively building on canvas. */
  copilotHarnessGenerating: boolean
  copilotActivityMode: import('../../lib/sherpaActivity').SherpaActivityMode
  copilotThinkingSteps: ThinkingStep[]
  copilotThinkingOpen: boolean
  copilotStreamText: string
  /** When true, SSE text is buffered for plan extraction but not shown in chat until commit. */
  copilotPlanPhaseStreaming: boolean
  copilotWorkflowCreated: { name: string; nodeCount: number } | null
  copilotStreamError: string | null
  copilotFinalSummary: AgentFinalSummary | null
  copilotPendingAutomationLink: CopilotMessage['automationLink']
  copilotPendingClarification: SherpaPendingClarification | null
  setCopilotPendingClarification: (pending: SherpaPendingClarification | null) => void
  resetCopilotStreamUi: () => void
  resetCopilotStreamSurface: () => void
  patchCopilotStream: (
    patch: Partial<
      Pick<
        WorkflowStore,
        | 'copilotStreamActive'
        | 'copilotActiveRoute'
        | 'copilotHarnessGenerating'
        | 'copilotActivityMode'
        | 'copilotThinkingSteps'
        | 'copilotThinkingOpen'
        | 'copilotStreamText'
        | 'copilotPlanPhaseStreaming'
        | 'copilotWorkflowCreated'
        | 'copilotStreamError'
        | 'copilotFinalSummary'
        | 'copilotPendingAutomationLink'
      >
    >,
  ) => void
  setCopilotThinkingSteps: (
    updater: ThinkingStep[] | ((prev: ThinkingStep[]) => ThinkingStep[]),
  ) => void
  outputOrientation: 'bottom' | 'side'
  setOutputOrientation: (orientation: 'bottom' | 'side') => void
  toggleOutputOrientation: () => void
  outputSummarySource: 'save' | 'copilot' | 'run' | null
  outputSummaryAt: number | null
  environment: 'dev' | 'uat' | 'prod'
  setEnvironment: (env: 'dev' | 'uat' | 'prod') => void
  mobilePaletteOpen: boolean
  setMobilePaletteOpen: (open: boolean) => void
  toggleMobilePaletteOpen: () => void
  sherpaPanelPopAt: number
}

export type WorkflowSetState = (
  partial:
    | Partial<WorkflowStore>
    | ((state: WorkflowStore) => Partial<WorkflowStore>),
) => void
