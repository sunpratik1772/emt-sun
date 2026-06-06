/**
 * Thin HTTP client for every backend endpoint the UI calls.
 *
 * Conventions:
 *   • One async function per endpoint; named after the action, not the
 *     URL ("listWorkflows" not "getWorkflows").
 *   • All requests go through `request()` so error parsing,
 *     ValidationError raising, and JSON content-type are centralised.
 *   • Streaming endpoints (/run/stream, /copilot/stream) return an
 *     async iterable of typed SSE events — components consume them
 *     with `for await (const ev of streamRun(...))`.
 *
 * Vite's dev server proxies `/api/*` to the FastAPI backend at
 * localhost:8000 (see vite.config.ts), so BASE stays relative.
 */
import type {
  Workflow,
  RunResult,
  RunLogEntry,
  RunArtifact,
  CopilotStreamEvent,
  CopilotErrorHint,
  RunWorkflowStreamEvent,
  ValidationResult,
} from '../types'

export const BASE = '/api'

export class ValidationError extends Error {
  readonly validation: ValidationResult

  constructor(validation: ValidationResult) {
    super(validation.summary || 'Workflow failed validation')
    this.name = 'ValidationError'
    this.validation = validation
  }
}

const FETCH_INIT: RequestInit = { credentials: 'include' }

function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  return fetch(BASE + path, { ...FETCH_INIT, ...init }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      if (res.status === 422 && err && typeof err.detail === 'object' && err.detail?.errors) {
        throw new ValidationError(err.detail as ValidationResult)
      }
      if (res.status === 409 && err && typeof err.detail === 'object' && err.detail?.code === 'workflow_name_conflict') {
        throw new Error(String(err.detail.message || 'A workflow with this name already exists.'))
      }
      throw new Error(typeof err.detail === 'string' ? err.detail : res.statusText)
    }
    return res.json() as Promise<T>
  })
}

/**
 * Thrown when `/run` (or any other endpoint) rejects a DAG because it
 * failed the deterministic validator. Callers can `instanceof` check it
 * to surface structured per-node errors instead of a generic message.
 */
/** Live NodeSpec bundle for Studio palette + config inspector (`GET /node-manifest`). */
export interface NodeManifestPayload {
  version: number
  palette_sections: Array<{ id: string; label: string; order: number; color: string }>
  nodes: Array<{
    type_id: string
    description: string
    color: string
    icon: string
    config_tags?: string[]
    palette_group: string
    palette_order: number
    display_name?: string
    input_ports: unknown[]
    output_ports: unknown[]
    params: unknown[]
    contract: {
      description: string
      inputs: Record<string, string>
      outputs: Record<string, string>
      config_schema: Record<string, string>
      constraints: string[]
    }
  }>
}

export interface CopilotGuardrailsPayload {
  nodes: Array<{ type_id: string; description: string; section?: string }>
  data_sources: Array<{ id: string; description: string; sources: string[] }>
  skills: Array<{ id: string; name: string; filename: string }>
  capabilities: {
    upload_script_enabled: boolean
    allowed_signal_modes: string[]
    builtin_signal_types: string[]
  }
  rules: string[]
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  return fetchJson<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

export interface StoredWorkflow {
  filename: string
  name: string
  description?: string
  node_count: number
  /** Epoch ms of last file modification. */
  modified_ms?: number
  upvote_count?: number
  downvote_count?: number
}

export interface DataSourceAccessRow {
  source_id: string
  id: string
  description?: string
  has_access: boolean
}

export interface GoodExamplePromotionPrefs {
  promote_to_folder: boolean
  promote_to_table: boolean
}

export interface AdminUserRow {
  user_id: string
  username: string
  email: string
  name: string
  role?: string | null
  created_at?: string | null
  last_login_at?: string | null
}

export interface CreateUserPayload {
  first_name: string
  last_name: string
  username: string
  password: string
  data_source_access: Record<string, boolean>
  skill_access?: Record<string, boolean>
  feature_access?: Record<string, boolean>
  role?: 'admin' | 'user'
}

export interface AdminUserCounts {
  workflows: number
  drafts: number
  runs: number
  automations: number
  chats: number
}

export interface AdminUserRowWithCounts extends AdminUserRow {
  counts: AdminUserCounts
}

export interface AdminWorkflowRow {
  user_id: string
  filename: string
  workflow_id?: string | null
  name?: string | null
  description?: string | null
  updated_at?: string | null
  upvote_count?: number
  downvote_count?: number
}

export interface AdminDraftRow {
  user_id: string
  filename: string
  workflow_id?: string | null
  name?: string | null
  description?: string | null
  updated_at?: string | null
}

export interface AdminRunRow {
  run_id: string
  user_id?: string | null
  workflow?: string | null
  status?: string | null
  started_at?: string | null
  error?: string | null
}

export interface AdminAutomationRow {
  id: string
  user_id?: string | null
  name?: string | null
  workflow_filename?: string | null
  active?: boolean
  schedule_type?: string | null
  created_at?: string | null
}

export interface SkillAccessRow {
  skill_id: string
  id: string
  has_access: boolean
}

export interface FeatureAccessRow {
  feature_key: string
  label: string
  enabled: boolean
}

export interface AdminOverview {
  totals: {
    users: number
    workflows: number
    drafts: number
    runs: number
    automations: number
    chats: number
  }
  users: AdminUserRowWithCounts[]
  workflows: AdminWorkflowRow[]
  drafts: AdminDraftRow[]
  runs: AdminRunRow[]
  automations: AdminAutomationRow[]
  skill_catalog?: string[]
  feature_catalog?: Array<{ feature_key: string; label: string }>
}

export interface LibrarySkill {
  id: string
  title: string
  overview: string
  regulatory: string[]
  sections: string[]
  sources: string[]
  raw_path: string
  bytes: number
}

export interface LibraryDataSource {
  id: string
  description: string
  sources: string[]
  backends: string[]
  backend_labels: string[]
  column_count: number
  source_count: number
  raw_path: string
  columns: { name: string; type: string; description: string; semantic?: string }[]
}

export interface CopilotResolveContextResponse {
  workflow: Workflow
  run_log: RunLogEntry[]
  run_result: RunResult | null
  run_error: string | null
  edit_workflow: Workflow | null
  edit_error: string | null
}

export interface SherpaClarificationOption {
  id: string
  label: string
  description?: string
}

export interface SherpaClarificationQuestionPayload {
  id: string
  kind: 'confirm' | 'choice'
  question: string
  options?: SherpaClarificationOption[]
  default_option_id?: string | null
  allow_multiple?: boolean
}

export interface SherpaClarificationAnswerPayload {
  question_id?: string
  question: string
  kind: 'confirm' | 'choice'
  selection_ids: string[]
  other_text?: string | null
  selection_labels?: string[]
}

export interface SherpaClarificationPayload {
  needed: boolean
  kind?: 'confirm' | 'choice' | null
  question?: string
  options?: SherpaClarificationOption[]
  default_option_id?: string | null
  questions?: SherpaClarificationQuestionPayload[]
  reason?: string
}

export interface CopilotRouteMetadata {
  workflow_name?: string | null
  run_selector?: string | null
  run_id?: string | null
  run_status_filter?: string | null
  error_message?: string | null
  node_id?: string | null
  topics?: string[]
  wants_sql?: boolean
  edit_existing_workflow?: boolean
  wants_sample_run?: boolean
  slash_route?: string | null
  suggested_sql?: string | null
  verification_plan?: string[] | null
  clarification_resolved?: boolean
  propose_build_plan?: boolean
  build_plan_confirmed?: boolean
  original_user_request?: string | null
  awaiting_plan_revision?: boolean
  plan_revision_reason?: string | null
  sherpa_disposition?: 'plan' | 'answer' | 'clarify' | string | null
  disposition_confidence?: number | null
  thinking_preview?: string | null
  propose_fix_plan?: boolean
  clarification_answer?: string | null
}

export interface SherpaDispositionPayload {
  kind: 'plan' | 'answer' | 'clarify' | string
  thinking?: string
  confidence?: number
  reason?: string
}

export type SherpaIntent =
  | 'build'
  | 'ask'
  | 'automate'
  | 'load'
  | 'explain_run'
  | 'explain_error'
  | 'query_run_data'

export interface SherpaSlashRouteDef {
  id: string
  slash: string
  command: string
  label: string
  description: string
  intent: string
  example: string
  contexts: string[]
  default_body: string
}

export interface CopilotRouteResponse {
  intent: SherpaIntent
  reason: string
  source: string
  enhanced_question: string
  keywords: string[]
  metadata: CopilotRouteMetadata
  clarification?: SherpaClarificationPayload | null
  disposition?: SherpaDispositionPayload | null
  thinking_preview?: string | null
}

export interface CopilotClarifyResolveRequest {
  message: string
  selection_id?: string
  other_text?: string | null
  answers?: SherpaClarificationAnswerPayload[]
  clarification_kind?: 'confirm' | 'choice'
  clarification_question?: string | null
  selection_label?: string | null
  selection_description?: string | null
  pending_route: CopilotRouteResponse
  has_workflow?: boolean
  session_id?: string | null
  thread_messages?: Array<{ role: 'user' | 'assistant'; content: string }>
  current_workflow?: Workflow | null
}

export interface RunQueryResult {
  run_id: string
  source: string
  columns: string[]
  rows: Record<string, string>[]
  row_count: number
}

export interface RunLogSummary {
  run_id: string
  workflow?: string
  started_at: string
  finished_at?: string
  duration_ms?: number
  status: 'success' | 'error' | 'warning' | 'running'
  disposition?: string
  flag_count?: number
  node_count?: number
  edge_count?: number
  error?: string
  download_url?: string
  run_log?: RunLogEntry[]
  run_result?: RunResult | null
  run_error?: string | null
  artifacts?: RunArtifact[]
}

export interface Automation {
  id: string
  name: string
  workflow_filename: string
  schedule_type: 'cron' | 'interval'
  cron_expression: string
  interval_mins: number
  duration_mins: number
  active: boolean
  author: string
  output_filename_pattern?: string | null
  created_at: string
  updated_at: string
  last_run_status?: string
  last_run_ago?: string
}

export interface AutomationRun {
  id: string
  automation_id: string
  run_id: string
  status: 'success' | 'error' | 'warning' | 'running'
  triggered_at: string
  duration_ms: number
  error: string | null
  download_url?: string | null
}

export type AutomationPayload = Pick<
  Automation,
  | 'name'
  | 'workflow_filename'
  | 'schedule_type'
  | 'cron_expression'
  | 'interval_mins'
  | 'duration_mins'
  | 'active'
  | 'author'
  | 'output_filename_pattern'
>

export const api = {
  // -- Saved workflows (named, promoted) -----------------------------
  listWorkflows: () => request<{ workflows: StoredWorkflow[] }>('GET', '/workflows'),
  getWorkflow: (filename: string) => request<Workflow>('GET', `/workflows/${filename}`),
  saveWorkflow: (filename: string, dag: Workflow, opts?: { replace?: boolean }) => {
    const q = opts?.replace ? '?replace=true' : ''
    return request<{ saved: string }>('POST', `/workflows/${filename}${q}`, dag)
  },
  deleteWorkflow: (filename: string) => request<{ deleted: string }>('DELETE', `/workflows/${filename}`),
  voteWorkflow: (
    filename: string,
    vote: 'up' | 'down',
    opts?: { promote_to_folder?: boolean; promote_to_table?: boolean },
  ) =>
    request<{
      vote: string
      upvote_count: number
      downvote_count: number
      promoted?: { id: string; folder_path?: string | null } | null
    }>('POST', `/workflows/${filename}/vote`, { vote, ...opts }),

  listDataSourceAccess: () =>
    request<{ sources: DataSourceAccessRow[] }>('GET', '/user/data-source-access'),
  updateDataSourceAccess: (sourceId: string, has_access: boolean) =>
    request<{ source_id: string; has_access: boolean }>(
      'PUT',
      `/user/data-source-access/${encodeURIComponent(sourceId)}`,
      { has_access },
    ),
  getGoodExamplePrefs: () => request<GoodExamplePromotionPrefs>('GET', '/user/preferences/good-examples'),
  updateGoodExamplePrefs: (prefs: Partial<GoodExamplePromotionPrefs>) =>
    request<GoodExamplePromotionPrefs>('PUT', '/user/preferences/good-examples', prefs),
  listUsers: () => request<{ users: AdminUserRow[] }>('GET', '/user/users'),
  getAdminOverview: () => request<AdminOverview>('GET', '/user/admin/overview'),
  createUser: (payload: CreateUserPayload) =>
    request<{ user: AdminUserRow }>('POST', '/user/users', payload),
  setUserRole: (userId: string, role: 'admin' | 'user') =>
    request<{ user: AdminUserRow }>('PUT', `/user/users/${encodeURIComponent(userId)}/role`, { role }),
  deleteUser: (userId: string) =>
    request<{ user_id: string; username?: string; deleted: Record<string, number> }>(
      'DELETE',
      `/user/users/${encodeURIComponent(userId)}`,
    ),
  getAdminUserDataSourceAccess: (userId: string) =>
    request<{ sources: DataSourceAccessRow[] }>(
      'GET',
      `/user/users/${encodeURIComponent(userId)}/data-source-access`,
    ),
  updateAdminUserDataSourceAccess: (userId: string, sourceId: string, has_access: boolean) =>
    request<{ source_id: string; has_access: boolean }>(
      'PUT',
      `/user/users/${encodeURIComponent(userId)}/data-source-access/${encodeURIComponent(sourceId)}`,
      { has_access },
    ),
  getAdminUserSkillAccess: (userId: string) =>
    request<{ skills: SkillAccessRow[] }>('GET', `/user/users/${encodeURIComponent(userId)}/skill-access`),
  updateAdminUserSkillAccess: (userId: string, skillId: string, has_access: boolean) =>
    request<{ skill_id: string; has_access: boolean }>(
      'PUT',
      `/user/users/${encodeURIComponent(userId)}/skill-access/${encodeURIComponent(skillId)}`,
      { has_access },
    ),
  getAdminUserFeatureAccess: (userId: string) =>
    request<{ features: FeatureAccessRow[] }>(
      'GET',
      `/user/users/${encodeURIComponent(userId)}/feature-access`,
    ),
  updateAdminUserFeatureAccess: (userId: string, featureKey: string, enabled: boolean) =>
    request<{ feature_key: string; enabled: boolean }>(
      'PUT',
      `/user/users/${encodeURIComponent(userId)}/feature-access/${encodeURIComponent(featureKey)}`,
      { enabled },
    ),
  workflowFromYaml: (content: string) =>
    request<{ workflow: Workflow }>('POST', '/workflow-format/yaml-to-json', { content }),
  workflowToYaml: (workflow: Workflow) =>
    request<{ content: string }>('POST', '/workflow-format/json-to-yaml', { workflow }),

  // -- Drafts (auto-saved, transient) --------------------------------
  listDrafts: () => request<{ drafts: StoredWorkflow[] }>('GET', '/drafts'),
  getDraft: (filename: string) => request<Workflow>('GET', `/drafts/${filename}`),
  saveDraft: (filename: string, dag: Workflow) => request<{ saved: string }>('POST', `/drafts/${filename}`, dag),
  deleteDraft: (filename: string) => request<{ deleted: string }>('DELETE', `/drafts/${filename}`),
  /** Move a draft to saved/, optionally updating the embedded name. */
  promoteDraft: (
    filename: string,
    target_filename: string,
    name?: string,
    opts?: { replace?: boolean },
  ) =>
    request<{ promoted: string; saved_as: string }>('POST', `/drafts/${filename}/promote`, {
      target_filename,
      name,
      replace: opts?.replace ?? false,
    }),

  // -- Validation ----------------------------------------------------
  /** Deterministic pre-flight check — safe to call continuously. */
  validateWorkflow: (dag: Workflow) => request<ValidationResult>('POST', '/validate', { dag }),

  runWorkflow: (dag: Workflow, alert_payload: Record<string, string>) => request<RunResult>('POST', '/run', { dag, alert_payload }),

  runWorkflowStream: async (
    dag: Workflow,
    alert_payload: Record<string, string>,
    onEvent: (ev: RunWorkflowStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch(BASE + '/run/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ dag, alert_payload }),
      credentials: 'include',
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload) as RunWorkflowStreamEvent) } catch { /* skip malformed */ }
        }
      }
    }
  },

  reportDownloadUrl: (filename: string) => `${BASE}/report/${encodeURIComponent(filename)}`,
  copilotChat: (message: string, session_id: string, reset_history = false) => request<{ reply: string }>('POST', '/copilot/chat', { message, session_id, reset_history }),

  copilotClassify: (
    message: string,
    opts?: {
      has_workflow?: boolean
      has_run_log?: boolean
      workflow_name?: string | null
      run_id?: string | null
      run_workflow_name?: string | null
      recent_errors?: CopilotErrorHint[] | null
      session_id?: string
      thread_messages?: Array<{ role: 'user' | 'assistant'; content: string }>
    },
  ) =>
    request<CopilotRouteResponse>('POST', '/copilot/route', {
      message,
      has_workflow: opts?.has_workflow ?? false,
      has_run_log: opts?.has_run_log ?? false,
      workflow_name: opts?.workflow_name ?? null,
      run_id: opts?.run_id ?? null,
      run_workflow_name: opts?.run_workflow_name ?? null,
      recent_errors: opts?.recent_errors ?? null,
      session_id: opts?.session_id ?? null,
      thread_messages: opts?.thread_messages ?? null,
    }),

  /** Alias for copilotClassify — LLM structured router. */
  copilotRoute: (
    message: string,
    opts?: {
      has_workflow?: boolean
      has_run_log?: boolean
      workflow_name?: string | null
      run_id?: string | null
      run_workflow_name?: string | null
      recent_errors?: CopilotErrorHint[] | null
      session_id?: string
      thread_messages?: Array<{ role: 'user' | 'assistant'; content: string }>
      current_workflow?: Workflow | null
    },
  ) =>
    request<CopilotRouteResponse>('POST', '/copilot/route', {
      message,
      has_workflow: opts?.has_workflow ?? false,
      has_run_log: opts?.has_run_log ?? false,
      workflow_name: opts?.workflow_name ?? null,
      run_id: opts?.run_id ?? null,
      run_workflow_name: opts?.run_workflow_name ?? null,
      recent_errors: opts?.recent_errors ?? null,
      session_id: opts?.session_id ?? null,
      thread_messages: opts?.thread_messages ?? null,
      current_workflow: opts?.current_workflow ?? null,
    }),

  copilotClarifyResolve: (payload: CopilotClarifyResolveRequest) =>
    request<CopilotRouteResponse>('POST', '/copilot/clarify/resolve', payload),

  copilotResolveContext: (payload: {
    route_metadata?: CopilotRouteMetadata | Record<string, unknown>
    current_workflow?: Workflow | null
    run_log?: RunLogEntry[]
    run_result?: RunResult | null
    run_error?: string | null
  }) =>
    request<CopilotResolveContextResponse>('POST', '/copilot/resolve-context', {
      route_metadata: payload.route_metadata ?? {},
      current_workflow: payload.current_workflow ?? null,
      run_log: payload.run_log ?? [],
      run_result: payload.run_result ?? null,
      run_error: payload.run_error ?? null,
    }),

  /**
   * SSE-streamed chat reply. The server returns the model's full
   * answer in word-sized chunks so the UI can render a typewriter
   * effect. Frame shapes:
   *   {type: "chunk",    text: "…"}     ← append to the current bubble
   *   {type: "complete", reply: "…"}    ← optional final canonical text
   *   {type: "error",    error: "…"}    ← bail out
   */
  copilotChatStream: async (
    message: string,
    session_id: string,
    onEvent: (ev: CopilotStreamEvent) => void,
    signal?: AbortSignal,
    reset_history = false,
    context?: {
      current_workflow?: Workflow | null
      recent_errors?: CopilotErrorHint[] | null
      propose_build_plan?: boolean
    },
  ): Promise<void> => {
    const res = await fetch(BASE + '/copilot/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        message,
        session_id,
        reset_history,
        current_workflow: context?.current_workflow ?? null,
        recent_errors: context?.recent_errors ?? null,
        propose_build_plan: context?.propose_build_plan ?? false,
      }),
      credentials: 'include',
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload)) } catch { /* ignore malformed */ }
        }
      }
    }
  },
  copilotGenerate: (
    prompt: string,
    critic_iterations = 3,
    current_workflow?: Workflow | null,
    recent_errors?: CopilotErrorHint[] | null,
    selected_node_id?: string | null,
    session_id?: string | null,
    thread_messages?: Array<{ role: 'user' | 'assistant'; content: string }> | null,
  ) =>
    request<{ success: boolean; workflow?: Workflow; error?: string }>('POST', '/copilot/generate', {
      prompt,
      critic_iterations,
      current_workflow: current_workflow ?? null,
      recent_errors: recent_errors ?? null,
      selected_node_id: selected_node_id ?? null,
      session_id: session_id ?? null,
      thread_messages: thread_messages ?? null,
    }),

  /**
   * SSE stream that accepts the optional edit-mode fields. When
   * `current_workflow` is supplied the backend switches the planner
   * from greenfield generation to a targeted edit of the DAG —
   * preserving node IDs and only changing what the errors / user
   * request require. `selected_node_id` lets deictic phrases
   * ("this", "here") in the request resolve to a concrete node.
   */
  copilotGenerateStream: async (
    prompt: string,
    critic_iterations = 3,
    onEvent: (ev: CopilotStreamEvent) => void,
    signal?: AbortSignal,
    current_workflow?: Workflow | null,
    recent_errors?: CopilotErrorHint[] | null,
    selected_node_id?: string | null,
    session_id?: string | null,
    thread_messages?: Array<{ role: 'user' | 'assistant'; content: string }> | null,
  ): Promise<void> => {
    const res = await fetch(BASE + '/copilot/generate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        prompt,
        critic_iterations,
        current_workflow: current_workflow ?? null,
        recent_errors: recent_errors ?? null,
        selected_node_id: selected_node_id ?? null,
        session_id: session_id ?? null,
        thread_messages: thread_messages ?? null,
      }),
      credentials: 'include',
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload) as CopilotStreamEvent) } catch { /* ignore malformed */ }
        }
      }
    }
  },

  copilotLoadStream: async (
    message: string,
    onEvent: (ev: CopilotStreamEvent) => void,
    signal?: AbortSignal,
    session_id?: string | null,
    thread_messages?: Array<{ role: 'user' | 'assistant'; content: string }> | null,
  ): Promise<void> => {
    const res = await fetch(BASE + '/copilot/load/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        message,
        session_id: session_id ?? null,
        thread_messages: thread_messages ?? null,
      }),
      credentials: 'include',
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload) as CopilotStreamEvent) } catch { /* ignore malformed */ }
        }
      }
    }
  },

  workflowCatalog: () =>
    request<{ entries: Array<{
      canonical_name: string
      filename: string
      kind: 'saved' | 'draft'
      workflow_id: string | null
      updated_ms: number
    }> }>('GET', '/workflows/catalog'),

  resolveWorkflowByName: (name: string) =>
    request<{
      action: 'load' | 'not_found'
      query: string
      canonical_name?: string
      filename?: string
      kind?: 'saved' | 'draft'
      workflow?: Workflow
    }>('GET', `/workflows/resolve?name=${encodeURIComponent(name)}`),

  searchWorkflows: (q: string, limit = 3) =>
    request<{
      action: 'load' | 'disambiguate' | 'not_found'
      query: string
      canonical_name?: string
      match?: { filename: string; name: string; score?: number }
      matches?: Array<{ filename: string; name: string; score?: number }>
      workflow?: Workflow
      message?: string
    }>('GET', `/workflows/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  copilotAutomateStream: async (
    message: string,
    onEvent: (ev: CopilotStreamEvent) => void,
    signal?: AbortSignal,
    current_workflow?: Workflow | null,
    critic_iterations = 2,
    session_id?: string | null,
    thread_messages?: Array<{ role: 'user' | 'assistant'; content: string }> | null,
  ): Promise<void> => {
    const res = await fetch(BASE + '/copilot/automate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        message,
        current_workflow: current_workflow ?? null,
        critic_iterations,
        session_id: session_id ?? null,
        thread_messages: thread_messages ?? null,
      }),
      credentials: 'include',
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload) as CopilotStreamEvent) } catch { /* ignore malformed */ }
        }
      }
    }
  },

  copilotExplainRunStream: async (
    workflow: Workflow,
    run_log: RunLogEntry[],
    run_result: RunResult | null,
    run_error: string | null,
    onEvent: (ev: CopilotStreamEvent) => void,
    signal?: AbortSignal,
    user_message?: string | null,
    suggested_sql?: string | null,
    route_metadata?: CopilotRouteMetadata | null,
  ): Promise<void> => {
    const res = await fetch(BASE + '/copilot/explain-run/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        workflow,
        run_log,
        run_result: run_result ?? null,
        run_error: run_error ?? null,
        user_message: user_message?.trim() || null,
        suggested_sql: suggested_sql?.trim() || null,
        route_metadata: route_metadata ?? null,
      }),
      credentials: 'include',
      signal,
    })
    if (!res.ok || !res.body) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || res.statusText)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try { onEvent(JSON.parse(payload) as CopilotStreamEvent) } catch { /* ignore malformed */ }
        }
      }
    }
  },
  listSkills: () => request<{ skills: Array<{ id: string; name: string; filename: string }> }>('GET', '/copilot/skills'),
  getSkill: (id: string) => request<{ id: string; content: string }>('GET', `/copilot/skills/${id}`),
  getCopilotGuardrails: () => request<CopilotGuardrailsPayload>('GET', '/copilot/guardrails'),
  getCopilotRoutes: (opts?: {
    has_workflow?: boolean
    has_run_log?: boolean
    has_errors?: boolean
  }) => {
    const qs = new URLSearchParams()
    if (opts?.has_workflow) qs.set('has_workflow', 'true')
    if (opts?.has_run_log) qs.set('has_run_log', 'true')
    if (opts?.has_errors) qs.set('has_errors', 'true')
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return request<{
      routes: SherpaSlashRouteDef[]
      suggested_ids: string[]
    }>('GET', `/copilot/routes${suffix}`)
  },
  getExamplePrompts: (params?: { first_name?: string; period?: string; refresh?: number }) => {
    const qs = new URLSearchParams()
    if (params?.first_name) qs.set('first_name', params.first_name)
    if (params?.period) qs.set('period', params.period)
    if (params?.refresh != null) qs.set('_', String(params.refresh))
    const suffix = qs.toString() ? `?${qs.toString()}` : ''
    return request<{
      build_prompts: Array<{ text: string; tag: string }>
      ask_prompts: Array<{ text: string; tag: string }>
      dashboard_subline?: string
      dashboard_subline_from_ai?: boolean
    }>('GET', `/copilot/example-prompts${suffix}`)
  },
  getContracts: () => request<Record<string, unknown>>('GET', '/contracts'),
  listChats: () => request<{ chats: Array<{ session_id: string; title: string; updated_at: string }> }>('GET', '/copilot/chats'),
  getChat: (session_id: string) => request<{
    session_id: string
    title: string
    messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string }>
  }>('GET', `/copilot/chats/${session_id}`),
  saveChat: (session_id: string, messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string }>, title?: string) =>
    request<{ ok: boolean }>('POST', `/copilot/chats/${session_id}`, { title, messages }),
  deleteChat: (session_id: string) => request<{ ok: boolean }>('DELETE', `/copilot/chats/${session_id}`),
  /** Palette + node metadata + contracts from the live backend registry. */
  getNodeManifest: () => request<NodeManifestPayload>('GET', '/node-manifest'),

  // -- Library (skills, data sources, run logs) ----------------------
  listLibrarySkills: () => request<{ skills: LibrarySkill[] }>('GET', '/skills'),
  getLibrarySkill: (id: string) =>
    request<{ id: string; title: string; markdown: string }>('GET', `/skills/${id}`),
  listDataSources: () => request<{ data_sources: LibraryDataSource[] }>('GET', '/data-sources'),
  getIntegrationEnv: () =>
    request<{
      mcp: Record<string, string>
      env_keys: Record<string, string>
      locked_keys: string[]
    }>('GET', '/integration-env'),
  listRunLogs: (opts?: {
    limit?: number
    workflow?: string
    status?: string
  }) => {
    const params = new URLSearchParams()
    if (opts?.limit) params.set('limit', String(opts.limit))
    if (opts?.workflow) params.set('workflow', opts.workflow)
    if (opts?.status) params.set('status', opts.status)
    const qs = params.toString()
    return request<{ logs: RunLogSummary[]; total: number }>(
      'GET',
      `/run-logs${qs ? `?${qs}` : ''}`,
    )
  },
  getRunLog: (runId: string) => request<RunLogSummary>('GET', `/run-logs/${encodeURIComponent(runId)}`),
  queryRunLog: (runId: string, sql: string) =>
    request<RunQueryResult>('POST', `/run-logs/${encodeURIComponent(runId)}/query`, { sql }),
  clearRunLogs: () => request<{ ok: boolean }>('DELETE', '/run-logs'),
  clearWorkspace: () =>
    request<{ ok: boolean; deleted: Record<string, number>; preserved: string[] }>('DELETE', '/workspace'),

  // -- Automations ---------------------------------------------------
  listAutomations: () => request<{ automations: Automation[] }>('GET', '/automations'),
  createAutomation: (payload: Partial<AutomationPayload> & Pick<AutomationPayload, 'name' | 'workflow_filename'>) =>
    request<{ ok: boolean; id: string }>('POST', '/automations', payload),
  updateAutomation: (id: string, payload: Partial<AutomationPayload>) =>
    request<{ ok: boolean }>('PUT', `/automations/${id}`, payload),
  deleteAutomation: (id: string) => request<{ ok: boolean }>('DELETE', `/automations/${id}`),
  triggerAutomation: (id: string) => request<{ ok: boolean }>('POST', `/automations/${id}/run`),
  listAutomationRuns: (id: string) => request<{ runs: AutomationRun[] }>('GET', `/automations/${id}/runs`),
  deleteAutomationRun: (automationId: string, runId: string) =>
    request<{ ok: boolean }>('DELETE', `/automations/${automationId}/runs/${runId}`),
  clearAutomationRuns: (id: string) => request<{ ok: boolean }>('DELETE', `/automations/${id}/runs`),
}
