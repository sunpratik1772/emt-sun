// NodeType is any backend type_id; UI metadata is hydrated from
// `GET /node-manifest` (see `nodeRegistryStore`). This file re-exports
// the *types* only so consumers avoid pulling in lucide or the store.
export type { NodeType, NodeUIMeta, NodeMeta } from '../nodes'
import type { NodeType } from '../nodes'
import type { ThinkingStep, AgentFinalSummary } from '../components/Copilot/thinkingTypes'

export interface WorkflowNode {
  id: string
  type: NodeType
  label: string
  config: Record<string, unknown>
  /** Persisted canvas position (flow coords). Optional — missing nodes fall back to auto-layout. */
  position?: { x: number; y: number }
  /** When true the engine should skip this node. Purely a UI concern today — backend honours it if the runner filters disabled nodes before topo sort. */
  disabled?: boolean
}

export interface WorkflowEdge {
  from: string
  to: string
  /** Required for condition/router branches — "true" | "false" or route label. */
  sourceHandle?: string
}

export interface Workflow {
  workflow_id: string
  name: string
  version?: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

export interface RunResult {
  disposition: 'ESCALATE' | 'REVIEW' | 'DISMISS' | ''
  flag_count: number
  output_branch: string
  report_path: string
  download_url?: string
  datasets: string[]
  sections: Record<string, { stats: Record<string, unknown>; narrative: string }>
  executive_summary: string
  workflow?: string
  run_id?: string
  row_count?: number
  rows?: number
  /** Non-blocking warnings emitted by the pre-flight validator. */
  warnings?: ValidationIssue[]
}

export interface RunArtifact {
  run_id?: string
  source_node_id?: string | null
  file_name?: string | null
  artifact_type?: string | null
  file_path?: string | null
  download_url?: string | null
  generated_at?: string | null
}

/** Matches the shape emitted by `engine.validator.ValidationIssue.to_json()` on the backend. */
export interface ValidationIssue {
  code: string
  message: string
  severity: 'error' | 'warning'
  node_id?: string | null
  field?: string | null
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  summary: string
}

export interface RunLogEntry {
  node_id: string
  node_type: NodeType | string
  label: string
  index: number
  total: number
  status: 'running' | 'ok' | 'error'
  started_at?: string
  duration_ms?: number
  output?: {
    datasets?: Record<string, { rows: number; columns: string[]; sample: Record<string, unknown>[] }>
    context?: Record<string, unknown>
    disposition?: string
    flag_count?: number
    output_branch?: string
    section?: { name: string; stats: Record<string, unknown>; narrative_preview: string }
    executive_summary_preview?: string
    executive_summary_chars?: number
    report_path?: string
    agent_response?: string
    /** Full orchestrator-style node output (rows, rowCount, …) when available. */
    node_output?: Record<string, unknown>
  }
  error?: string
  trace?: string
}

export interface RunWorkflowStreamEvent {
  type:
    | 'workflow_start'
    | 'node_start'
    | 'node_complete'
    | 'node_error'
    | 'workflow_complete'
    | 'workflow_error'
  name?: string
  total_nodes?: number
  order?: string[]
  node_id?: string
  node_type?: string
  label?: string
  index?: number
  total?: number
  started_at?: string
  duration_ms?: number
  status?: string
  output?: RunLogEntry['output']
  error?: string
  trace?: string
  total_duration_ms?: number
  result?: RunResult
  /** Present on `workflow_error` frames emitted when the pre-flight validator rejects the DAG. */
  validation?: ValidationResult
  /** Present on `workflow_complete` frames when the run had non-blocking warnings. */
  warnings?: ValidationIssue[]
}

export interface CopilotMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  steps?: ThinkingStep[]
  summary?: AgentFinalSummary | null
  previousWorkflow?: Workflow | null
  newWorkflow?: Workflow | null
  reverted?: boolean
  automationLink?: {
    id: string
    name: string
    schedule_summary?: string
  }
}


export type CopilotPhase =
  | 'understanding'
  | 'planning'
  | 'generating'
  | 'auto_fixing'
  | 'critiquing'
  | 'finalizing'
  | 'complete'
  | 'error'

/**
 * Normalised error hint the Copilot's edit-mode receives. The
 * backend prompt builder accepts a loose shape: anything with a
 * `message` is enough, and optional `code` / `node_id` / `kind` /
 * `severity` tighten the hint. Shaped here so every call site
 * (validation, runtime, save errors) has one target type.
 */
export interface CopilotErrorHint {
  /** Validator error code (e.g. `UNKNOWN_NODE_TYPE`) when known. */
  code?: string
  /** ID of the offending node when known. */
  node_id?: string
  /** "validation" | "runtime" | "save" — helps the LLM pick a repair strategy. */
  kind?: 'validation' | 'runtime' | 'save' | string
  /** "error" | "warning" | "info". Defaults to "error" in the backend. */
  severity?: 'error' | 'warning' | 'info' | string
  /** Free-form human-readable description. */
  message: string
}

/** Orchestrator-style Copilot generate/stream SSE events. */
export type CopilotStreamEvent =
  | { type: 'thinking'; step: string; status?: 'running' | 'done' }
  | {
      type: 'agent_stage'
      stage_id: string
      stage: string
      status: 'running' | 'done' | 'error'
      detail?: string
      subagent_name?: string
      subagent_type?: string
      outcome?: string
      contextual_plan?: boolean
      thinking_monologue?: boolean
      prompt_anchor?: string
    }
  | {
      type: 'agent_final_summary'
      title: string
      bullets: string[]
      spawned_count: number
      completed_count: number
      failed_count: number
    }
  | { type: 'text_start' }
  | { type: 'text_chunk'; chunk: string }
  | { type: 'text_end' }
  | {
      type: 'workflow_disambiguation'
      query: string
      matches: Array<{ filename: string; name: string; score?: number; reasons?: string[] }>
    }
  | {
      type: 'workflow_created'
      workflowId: string
      name: string
      nodeCount: number
      workflow?: Workflow
      draft_filename?: string
    }
  | {
      type: 'automation_created'
      automation_id: string
      name: string
      workflow_filename: string
      schedule_type?: 'cron' | 'interval'
      cron_expression: string
      interval_mins?: number
      duration_mins?: number
      schedule_summary: string
      timezone_note?: string
    }
  | { type: 'test_run_started'; automation_id: string }
  | { type: 'done'; success?: boolean; compiler_mode?: string; automation_id?: string }
  | { type: 'error'; message: string }

/** @deprecated Legacy phase timeline — kept for type compatibility only. */
export interface CopilotPhaseStreamEvent {
  phase: CopilotPhase
  label: string
  status: 'running' | 'done' | 'error'
  detail?: string
  workflow?: Workflow
  validation?: ValidationResult
}

