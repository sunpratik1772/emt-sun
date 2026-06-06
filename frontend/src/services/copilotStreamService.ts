/**
 * Background copilot stream runner — survives sherpa panel unmount.
 * UI subscribes via workflow store; completion focuses canvas + sherpa.
 */
import {
  applyAgentStage,
  applyRunActivity,
  applyThinkingPulse,
  closeAllThinkingSteps,
  collapseAllThinkingSteps,
  thinkingStepFromPreview,
} from '../components/Copilot/thinkingHelpers'
import type { AgentFinalSummary, ThinkingStep } from '../components/Copilot/thinkingTypes'
import {
  buildThreadMessages,
  collectErrorHints,
  isRunOutputQuestion,
  lastAssistantOfferedSampleRun,
  buildPromptFromThread,
  extractPlanSteps,
  formatPlanPhaseChatMessage,
  hasBuildPlanContent,
  looksLikeActionAcceptance,
  SAMPLE_RUN_PAYLOAD,
  shouldEditExistingWorkflow,
  stripNextActionFooter,
} from '../components/Copilot/copilotUtils'
import { useStudioSectionStore } from '../store/studioSectionStore'
import { focusSherpaSidePanel } from '../lib/focusSherpaSidePanel'
import { openRunOutputOnComplete } from '../lib/openOutputPanel'
import { resolveSherpaActivityMode, type SherpaActivityMode } from '../lib/sherpaActivity'
import {
  beginSherpaTextStream,
  enqueueSherpaTextChunk,
  flushSherpaTextStream,
  resetSherpaTextStream,
  sherpaStreamTextRef,
} from '../lib/sherpaSseTextStream'
import { notifyCopilotStreamActivity } from '../lib/sherpaActivityToasts'
import { layoutAndCompactWorkflow } from '../store/layout'
import { flushSync } from 'react-dom'
import { finalizeStuckRunLog, flushRunEventQueue, useWorkflowStore } from '../store/workflowStore'
import { toast } from '../store/toastStore'
import { loadWorkflowFromCatalog, resolveFirstQuotedWorkflowInMessage } from '../lib/workflowLibrary'
import { api } from './api'
import type { CopilotRouteMetadata, CopilotRouteResponse, SherpaClarificationAnswerPayload } from './api'
import {
  buildRouteFromPlanApproval,
  clarificationFromRoute,
  formatAnswersForChat,
  planApprovalFromRoute,
  PLAN_APPROVAL_QUESTION_ID,
  type SherpaClarificationAnswer,
} from '../components/Copilot/sherpaClarificationTypes'
import type {
  CopilotMessage,
  CopilotStreamEvent,
  RunLogEntry,
  RunResult,
  RunWorkflowStreamEvent,
  Workflow,
} from '../types'

let activeAbortController: AbortController | null = null

/** Let React paint the user's clarification answer before the thinking stream starts. */
async function awaitChatAnswerVisible(): Promise<void> {
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  })
}

function commitClarificationUserAnswer(content: string): void {
  flushSync(() => {
    const store = useWorkflowStore.getState()
    store.setCopilotPendingClarification(null)
    store.addCopilotMessage({
      role: 'user',
      content,
      timestamp: new Date(),
    })
  })
}

function snapshotThinkingSteps(): ThinkingStep[] {
  return closeAllThinkingSteps([...useWorkflowStore.getState().copilotThinkingSteps])
}

/** Wait for paced SSE drain, then persist the live stream as a chat message. */
async function commitStreamedAssistantReply(
  fallbackText: string,
  extra?: Partial<Omit<CopilotMessage, 'role' | 'content' | 'timestamp'>>,
): Promise<void> {
  await flushSherpaTextStream()
  const text = useWorkflowStore.getState().copilotStreamText.trim() || fallbackText.trim()
  if (!text) return
  useWorkflowStore.getState().addCopilotMessage({
    role: 'assistant',
    content: text,
    timestamp: new Date(),
    ...extra,
  })
}

/** Refs mirrored in store for stream-end message assembly (not in React state). */
const streamTextRef = sherpaStreamTextRef
const streamErrorRef = { current: null as string | null }
const finalSummaryRef = { current: null as AgentFinalSummary | null }
const automationLinkRef = { current: undefined as CopilotMessage['automationLink'] }

export function isCopilotStreamRunning(): boolean {
  return useWorkflowStore.getState().copilotStreamActive
}

export function stopCopilotStream(): void {
  activeAbortController?.abort()
}

export function focusStudioOnCopilotComplete(opts?: { gotWorkflow?: boolean }): void {
  const wf = useWorkflowStore.getState()
  const studio = useStudioSectionStore.getState()
  wf.setWorkflowDrawerOpen(false)
  studio.setSection(null)
  studio.clearAutomationFocus()
  wf.setWorkspaceView('canvas')
  if (opts?.gotWorkflow && wf.workflow) {
    const fixed = layoutAndCompactWorkflow(wf.workflow)
    useWorkflowStore.setState({
      workflow: fixed,
      workflowViewportVersion: wf.workflowViewportVersion + 1,
    })
  }
  focusSherpaSidePanel()
}

function syncThinking(updater: ThinkingStep[] | ((prev: ThinkingStep[]) => ThinkingStep[])) {
  useWorkflowStore.getState().setCopilotThinkingSteps(updater)
}

function handleStreamEvent(ev: CopilotStreamEvent) {
  notifyCopilotStreamActivity(ev)
  const patch = useWorkflowStore.getState().patchCopilotStream
  switch (ev.type) {
    case 'agent_stage':
      syncThinking((prev) =>
        applyAgentStage(prev, {
          stage_id: ev.stage_id,
          stage: ev.stage,
          status: ev.status,
          detail: ev.detail,
          subagent_name: ev.subagent_name,
          subagent_type: ev.subagent_type,
          outcome: ev.outcome,
          contextual_plan: ev.contextual_plan,
          thinking_monologue: ev.thinking_monologue,
        }),
      )
      break
    case 'agent_final_summary':
      finalSummaryRef.current = {
        title: ev.title,
        bullets: ev.bullets,
        spawnedCount: ev.spawned_count,
        completedCount: ev.completed_count,
        failedCount: ev.failed_count,
      }
      patch({ copilotFinalSummary: finalSummaryRef.current })
      break
    case 'thinking':
      syncThinking((prev) => applyThinkingPulse(prev, ev.step, ev.status ?? 'running'))
      break
    case 'text_start':
      syncThinking((prev) => collapseAllThinkingSteps(prev))
      beginSherpaTextStream()
      break
    case 'text_chunk': {
      enqueueSherpaTextChunk(ev.chunk)
      break
    }
    case 'text_end':
      break
    case 'workflow_created':
      syncThinking((prev) => collapseAllThinkingSteps(prev))
      patch({
        copilotWorkflowCreated: { name: ev.name, nodeCount: ev.nodeCount },
      })
      if (ev.workflow) {
        const { resetRun, setWorkflow } = useWorkflowStore.getState()
        resetRun()
        setWorkflow(ev.workflow)
      }
      break
    case 'automation_created':
      automationLinkRef.current = {
        id: ev.automation_id,
        name: ev.name,
        schedule_summary: ev.schedule_summary,
      }
      patch({ copilotPendingAutomationLink: automationLinkRef.current })
      break
    case 'test_run_started':
      break
    case 'done':
      syncThinking((prev) => collapseAllThinkingSteps(prev))
      break
    case 'error':
      if (!streamTextRef.current.trim()) {
        streamErrorRef.current = ev.message
        patch({ copilotStreamError: ev.message })
      }
      patch({ copilotThinkingOpen: false })
      break
    default:
      break
  }
}

function patchActivityMode(patch: {
  activeRoute?: import('../store/workflow/copilotStreamSlice').CopilotActiveRoute
  disposition?: CopilotRouteResponse['disposition']
  routeIntent?: string | null
  planPhaseStreaming?: boolean
  pendingClarification?: boolean
}) {
  const store = useWorkflowStore.getState()
  const mode: SherpaActivityMode = resolveSherpaActivityMode({
    isLoading: store.copilotStreamActive,
    activeRoute: patch.activeRoute ?? store.copilotActiveRoute,
    disposition: patch.disposition ?? null,
    routeIntent: patch.routeIntent ?? null,
    planPhaseStreaming: patch.planPhaseStreaming ?? store.copilotPlanPhaseStreaming,
    pendingClarification: patch.pendingClarification ?? Boolean(store.copilotPendingClarification),
    harnessGenerating: store.copilotHarnessGenerating,
  })
  store.patchCopilotStream({ copilotActivityMode: mode })
}

function beginStreamUi(opts?: { focusSherpa?: boolean }) {
  resetSherpaTextStream()
  streamErrorRef.current = null
  finalSummaryRef.current = null
  automationLinkRef.current = undefined
  if (opts?.focusSherpa !== false) {
    focusSherpaSidePanel()
  }
  const store = useWorkflowStore.getState()
  store.setCopilotPendingClarification(null)
  store.resetCopilotStreamSurface()
  store.patchCopilotStream({
    copilotStreamActive: true,
    copilotThinkingOpen: true,
    copilotHarnessGenerating: false,
    copilotActivityMode: 'thinking',
  })
}

function endStreamUi() {
  useWorkflowStore.getState().patchCopilotStream({
    copilotStreamActive: false,
    copilotActiveRoute: null,
    copilotHarnessGenerating: false,
    copilotActivityMode: null,
  })
  activeAbortController = null
}

function clearStreamUiAfterMessage() {
  useWorkflowStore.getState().resetCopilotStreamSurface()
  resetSherpaTextStream()
  streamErrorRef.current = null
  finalSummaryRef.current = null
  automationLinkRef.current = undefined
}

async function streamExplainRunReply(
  msg: string,
  workflow: Workflow,
  runLog: RunLogEntry[],
  runResult: RunResult | null,
  runError: string | null,
  signal: AbortSignal,
  suggestedSql?: string | null,
  routeMetadata?: CopilotRouteMetadata | null,
): Promise<string> {
  beginSherpaTextStream()
  const { patchCopilotStream } = useWorkflowStore.getState()
  patchCopilotStream({ copilotThinkingOpen: true })
  await api.copilotExplainRunStream(
    workflow,
    runLog,
    runResult,
    runError,
    (ev) => {
      if (ev.type === 'agent_stage') {
        syncThinking((prev) =>
          applyAgentStage(prev, {
            stage_id: ev.stage_id,
            stage: ev.stage,
            status: ev.status,
            detail: ev.detail,
            subagent_name: ev.subagent_name,
            subagent_type: ev.subagent_type,
            outcome: ev.outcome,
            contextual_plan: ev.contextual_plan,
            thinking_monologue: ev.thinking_monologue,
          }),
        )
      } else if (ev.type === 'text_start') {
        syncThinking((prev) => collapseAllThinkingSteps(prev))
        beginSherpaTextStream()
      } else if (ev.type === 'text_chunk') {
        enqueueSherpaTextChunk(ev.chunk)
      } else if (ev.type === 'done') {
        syncThinking((prev) => collapseAllThinkingSteps(prev))
      } else if (ev.type === 'error') {
        streamErrorRef.current = ev.message
        patchCopilotStream({ copilotStreamError: ev.message })
      }
    },
    signal,
    msg,
    suggestedSql,
    routeMetadata,
  )
  await flushSherpaTextStream()
  return useWorkflowStore.getState().copilotStreamText.trim()
}

/** Canonical catalog resolve — same endpoint as suggestion name validation. */
async function resolveLibraryWorkflowByName(name: string): Promise<Workflow | null> {
  const loaded = await loadWorkflowFromCatalog(name)
  return loaded?.workflow ?? null
}

async function resolveRunContextFromRoute(
  route: CopilotRouteResponse,
  canvasWorkflow: Workflow | null,
  canvasRunLog: RunLogEntry[],
  canvasRunResult: RunResult | null,
  canvasRunError: string | null,
): Promise<{
  workflow: Workflow
  runLog: RunLogEntry[]
  runResult: RunResult | null
  runError: string | null
  editWorkflow: Workflow | null
  editError: string | null
}> {
  const ctx = await api.copilotResolveContext({
    route_metadata: route.metadata ?? {},
    current_workflow: canvasWorkflow,
    run_log: canvasRunLog,
    run_result: canvasRunResult,
    run_error: canvasRunError,
  })
  return {
    workflow: ctx.workflow,
    runLog: ctx.run_log ?? [],
    runResult: ctx.run_result ?? null,
    runError: ctx.run_error ?? null,
    editWorkflow: ctx.edit_workflow ?? null,
    editError: ctx.edit_error ?? null,
  }
}

/** Execute the canvas workflow with sample payload, then stream a run summary. */
async function executeSampleRunAndExplain(
  workflow: Workflow,
  signal: AbortSignal,
): Promise<void> {
  focusSherpaSidePanel()
  const store = useWorkflowStore.getState()
  store.addCopilotMessage({
    role: 'assistant',
    content:
      'Run started. I will analyze full output logs and return one final data-focused explanation when execution finishes.',
    timestamp: new Date(),
  })

  store.resetCopilotStreamSurface()
  store.patchCopilotStream({ copilotThinkingOpen: true })
  store.setRunning(true)
  store.resetRun()

  let runResult: RunResult | null = null
  try {
    await api.runWorkflowStream(workflow, SAMPLE_RUN_PAYLOAD, (ev: RunWorkflowStreamEvent) => {
      if (signal.aborted) return
      store.applyRunEvent(ev)
      if (ev.type === 'workflow_start') {
        syncThinking((prev) => applyRunActivity(prev, 'workflow_start'))
      } else if (ev.type === 'node_start') {
        syncThinking((prev) => applyRunActivity(prev, 'node_start', ev.label))
      } else if (ev.type === 'node_complete') {
        syncThinking((prev) => applyRunActivity(prev, 'node_complete', ev.label))
      } else if (ev.type === 'node_error') {
        syncThinking((prev) => applyRunActivity(prev, 'node_error', ev.label))
      } else if (ev.type === 'workflow_complete') {
        runResult = ev.result ?? null
        syncThinking((prev) => applyRunActivity(prev, 'workflow_complete'))
      } else if (ev.type === 'workflow_error') {
        syncThinking((prev) => applyRunActivity(prev, 'workflow_error', ev.error))
      }
    })
  } catch (e) {
    if ((e as Error).name !== 'AbortError') {
      store.addCopilotMessage({
        role: 'assistant',
        content: `Run failed: ${(e as Error).message}`,
        timestamp: new Date(),
      })
    }
    return
  } finally {
    finalizeStuckRunLog()
    store.setRunning(false)
    await flushRunEventQueue()
  }

  if (signal.aborted) return

  await flushRunEventQueue()
  const afterRun = useWorkflowStore.getState()
  const freshLog = afterRun.runLog
  if (!freshLog.length) {
    openRunOutputOnComplete()
    store.addCopilotMessage({
      role: 'assistant',
      content: 'Run finished but no node logs were captured.',
      timestamp: new Date(),
    })
    return
  }

  openRunOutputOnComplete()
  beginStreamUi({ focusSherpa: false })
  store.patchCopilotStream({ copilotStreamText: '', copilotActiveRoute: 'explain_run' })
  try {
    const summary = await streamExplainRunReply(
      'Summarize this sample run — row counts, key columns, and whether the export looks correct.',
      workflow,
      freshLog,
      afterRun.runResult ?? runResult,
      afterRun.runError,
      signal,
    )
    const assistantText = summary || 'Run finished but no summary was produced.'
    await commitStreamedAssistantReply(assistantText, { steps: snapshotThinkingSteps() })
  } catch (e) {
    if ((e as Error).name !== 'AbortError') {
      store.addCopilotMessage({
        role: 'assistant',
        content: `Run analysis failed: ${(e as Error).message}`,
        timestamp: new Date(),
      })
    }
  } finally {
    endStreamUi()
    clearStreamUiAfterMessage()
  }
}

/** Post-run Sherpa summary in the copilot panel (uses captured runLog). */
export async function explainLastRunInCopilot(
  userMessage = 'Summarize this workflow run.',
): Promise<void> {
  if (isCopilotStreamRunning()) return

  await flushRunEventQueue()
  const store = useWorkflowStore.getState()
  const workflow = store.workflow
  const runLog = store.runLog
  const runResult = store.runResult
  const runError = store.runError
  if (!workflow || !runLog.length) return

  openRunOutputOnComplete()
  beginStreamUi({ focusSherpa: false })
  store.patchCopilotStream({ copilotActiveRoute: 'explain_run' })

  try {
    const summary = await streamExplainRunReply(
      userMessage,
      workflow,
      runLog,
      runResult,
      runError,
      new AbortController().signal,
    )
    const currentThinkingSteps = snapshotThinkingSteps()
    const assistantText = summary || 'Run finished but no summary was produced.'
    await commitStreamedAssistantReply(assistantText, { steps: currentThinkingSteps })
  } catch (e) {
    if ((e as Error).name !== 'AbortError') {
      store.addCopilotMessage({
        role: 'assistant',
        content: `Run analysis failed: ${(e as Error).message}`,
        timestamp: new Date(),
      })
    }
  } finally {
    endStreamUi()
    clearStreamUiAfterMessage()
  }
}

/** Same outcome as Sherpa /run when the user accepts a sample-run offer in chat. */
function clientSampleRunAcceptRoute(): CopilotRouteResponse {
  return {
    intent: 'ask',
    reason: 'Accepted sample-run offer (same as /run)',
    source: 'client_sample_run',
    enhanced_question: 'Run workflow with sample data',
    keywords: [],
    metadata: {
      wants_sample_run: true,
      edit_existing_workflow: false,
      clarification_resolved: true,
    },
  }
}

export { clarificationFromRoute }

type ContinueRouteCtx = {
  route: CopilotRouteResponse
  msg: string
  criticIter: number
  controller: AbortController
  workflowBeforeEdit: Workflow | null
  threadMessages: ReturnType<typeof buildThreadMessages>
  askContext: { current_workflow: Workflow | null; recent_errors: ReturnType<typeof collectErrorHints> | null }
  allErrorHints: ReturnType<typeof collectErrorHints>
  gotWorkflowFlag: { value: boolean }
  shouldFocusFlag: { value: boolean }
}

async function continueAfterRoute(ctx: ContinueRouteCtx): Promise<void> {
  const {
    route,
    msg,
    criticIter,
    controller,
    workflowBeforeEdit,
    threadMessages,
    askContext,
    allErrorHints,
    gotWorkflowFlag,
    shouldFocusFlag,
  } = ctx
  const store = useWorkflowStore.getState()
  const {
    addCopilotMessage,
    copilotSessionId,
    currentWorkflow,
    validationIssues,
    runLog,
    runError,
    runResult,
    selectedNodeId,
  } = {
    addCopilotMessage: store.addCopilotMessage,
    copilotSessionId: store.copilotSessionId,
    currentWorkflow: store.workflow,
    validationIssues: store.validationIssues,
    runLog: store.runLog,
    runError: store.runError,
    runResult: store.runResult,
    selectedNodeId: store.selectedNodeId,
  }

  if (route.metadata?.wants_sample_run) {
    let wf = currentWorkflow
    if (!wf?.nodes?.length) {
      const named = route.metadata?.workflow_name?.trim() || ''
      if (named) {
        const fromLibrary = await resolveLibraryWorkflowByName(named)
        if (fromLibrary) {
          wf = fromLibrary
          store.resetRun()
          store.setWorkflow(fromLibrary)
        }
      }
    }
    if (!wf?.nodes?.length) {
      const named = route.metadata?.workflow_name?.trim()
      addCopilotMessage({
        role: 'assistant',
        content: named
          ? `I could not find **${named}** on the canvas or in saved/draft workflows. Build it first, or use **/load** with the exact name from Templates.`
          : 'There is no workflow on the canvas yet. Build or load a pipeline first, then say **yes** to run it with sample data.',
        timestamp: new Date(),
      })
      return
    }
    store.patchCopilotStream({ copilotActiveRoute: 'explain_run' })
    await executeSampleRunAndExplain(wf, controller.signal)
    return
  }

  const routeAsk = route.intent === 'ask'
  const routeAutomate = route.intent === 'automate'
  const routeLoad = route.intent === 'load'
  const routeExplainRun = route.intent === 'explain_run' || route.intent === 'explain_error'
  const routeQueryRun = route.intent === 'query_run_data'
  const runReviewFallback =
    routeAsk &&
    isRunOutputQuestion(msg) &&
    (runLog.length > 0 || Boolean(route.metadata?.workflow_name || route.metadata?.run_id))
  const disposition = route.disposition?.kind || route.metadata?.sherpa_disposition
  const activeRoute =
    route.intent === 'build' && disposition !== 'plan' && !route.metadata?.propose_build_plan
      ? 'build'
      : (route.intent as 'build' | 'ask' | 'automate' | 'load' | 'explain_run')
  store.patchCopilotStream({ copilotActiveRoute: activeRoute })
  patchActivityMode({
    activeRoute,
    disposition: route.disposition,
    routeIntent: route.intent,
    planPhaseStreaming: Boolean(route.metadata?.propose_build_plan || route.metadata?.propose_fix_plan),
  })

  const editExisting = Boolean(
    route.metadata?.edit_existing_workflow ||
      (currentWorkflow &&
        shouldEditExistingWorkflow(msg, {
          threadMessages: buildThreadMessages(useWorkflowStore.getState().copilotMessages, {
            excludeLast: true,
          }),
        })),
  )
  const canvasHasNodes = Boolean(currentWorkflow?.nodes?.length)
  const namedWorkflow = route.metadata?.workflow_name?.trim() || ''
  let workflowForContext = currentWorkflow
  if (!canvasHasNodes && namedWorkflow) {
    const fromLibrary = await resolveLibraryWorkflowByName(namedWorkflow)
    if (fromLibrary) {
      workflowForContext = fromLibrary
    }
  }

  let ctxWorkflow: Workflow | null = editExisting ? workflowForContext : null
  if (route.intent === 'build' && route.metadata?.edit_existing_workflow && !canvasHasNodes) {
    try {
      const resolvedEdit = await api.copilotResolveContext({
        route_metadata: route.metadata ?? {},
        current_workflow: currentWorkflow,
        run_log: runLog,
        run_result: runResult,
        run_error: runError,
      })
      if (resolvedEdit.edit_workflow) {
        ctxWorkflow = resolvedEdit.edit_workflow
      } else if (resolvedEdit.edit_error && !ctxWorkflow) {
        toast.warning(resolvedEdit.edit_error)
      }
    } catch {
      /* fall through */
    }
  }
  if (
    route.intent === 'build' &&
    !ctxWorkflow &&
    !canvasHasNodes &&
    route.metadata?.edit_existing_workflow &&
    namedWorkflow &&
    workflowForContext
  ) {
    ctxWorkflow = workflowForContext
  }
  const buildPrompt = route.enhanced_question?.trim() || msg
  const errorHints = ctxWorkflow ? allErrorHints : null

  if (
    (routeExplainRun || routeQueryRun || runReviewFallback) &&
    (route.metadata?.workflow_name || runLog.length > 0 || route.metadata?.run_id)
  ) {
    await flushRunEventQueue()
    const freshLog = useWorkflowStore.getState().runLog
    const freshResult = useWorkflowStore.getState().runResult
    const freshError = useWorkflowStore.getState().runError
    const resolved = await resolveRunContextFromRoute(
      route,
      workflowForContext ?? currentWorkflow,
      freshLog.length ? freshLog : runLog,
      freshResult ?? runResult,
      freshError ?? runError,
    )
    store.patchCopilotStream({ copilotActiveRoute: 'explain_run' })

    let question = route.enhanced_question || msg
    if (routeQueryRun && route.metadata?.wants_sql) {
      const runId =
        route.metadata.run_id ||
        (await api.listRunLogs({ workflow: route.metadata.workflow_name ?? undefined, limit: 1 }))
          .logs[0]?.run_id
      if (runId) {
        try {
          const sqlMatch = msg.match(/select[\s\S]+/i)
          const sql = sqlMatch ? sqlMatch[0] : 'SELECT * FROM run_output LIMIT 10'
          const qr = await api.queryRunLog(runId, sql)
          question = `${question}\n\nSQL query results (${qr.row_count} rows):\n${JSON.stringify(qr.rows.slice(0, 10))}`
        } catch (e) {
          question = `${question}\n\n(Query failed: ${(e as Error).message})`
        }
      }
    }

    try {
      const summary = await streamExplainRunReply(
        question,
        resolved.workflow,
        resolved.runLog,
        resolved.runResult,
        resolved.runError,
        controller.signal,
        route.metadata?.suggested_sql ?? null,
        route.metadata ?? null,
      )
      const currentThinkingSteps = snapshotThinkingSteps()
      const assistantText = summary || 'Run finished but no summary was produced.'
      const assistantError = streamErrorRef.current
      focusSherpaSidePanel()
      if (assistantText) {
        await commitStreamedAssistantReply(assistantText, { steps: currentThinkingSteps })
      } else if (assistantError) {
        await commitStreamedAssistantReply(assistantError, { steps: currentThinkingSteps })
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        addCopilotMessage({
          role: 'assistant',
          content: `Run analysis failed: ${(e as Error).message}`,
          timestamp: new Date(),
        })
      }
    }
    return
  }

  if (routeAsk) {
    const askPrompt = route.enhanced_question?.trim() || msg
    const proposeBuildPlan = Boolean(route.metadata?.propose_build_plan)
    store.patchCopilotStream({
      copilotThinkingOpen: true,
      copilotPlanPhaseStreaming: proposeBuildPlan,
    })
    await api.copilotChatStream(
      askPrompt,
      copilotSessionId,
      (ev) => handleStreamEvent(ev),
      controller.signal,
      false,
      {
        ...askContext,
        current_workflow: workflowForContext ?? askContext.current_workflow,
        propose_build_plan: proposeBuildPlan,
      },
    )

    const currentThinkingSteps = snapshotThinkingSteps()
    const assistantText = streamTextRef.current.trim()
    const assistantError = streamErrorRef.current

    focusSherpaSidePanel()
    const planBody = assistantText ? stripNextActionFooter(assistantText) : ''
    const planSteps =
      proposeBuildPlan && planBody ? extractPlanSteps(planBody) : []
    const showPlanModal =
      proposeBuildPlan &&
      !route.metadata?.build_plan_confirmed &&
      (planSteps.length >= 2 || hasBuildPlanContent(planBody || assistantText))

    store.patchCopilotStream({ copilotPlanPhaseStreaming: false })

    if (showPlanModal) {
      const steps =
        planSteps.length >= 2
          ? planSteps
          : extractPlanSteps(planBody || assistantText)
      await commitStreamedAssistantReply(formatPlanPhaseChatMessage(steps), {
        steps: currentThinkingSteps,
      })
      const originalMsg = route.metadata?.original_user_request?.trim() || msg
      store.setCopilotPendingClarification(
        planApprovalFromRoute(route, originalMsg, planBody || assistantText, steps),
      )
      shouldFocusFlag.value = false
      endStreamUi()
      clearStreamUiAfterMessage()
    } else if (assistantText) {
      await commitStreamedAssistantReply(planBody || assistantText, { steps: currentThinkingSteps })
    } else if (assistantError) {
      await commitStreamedAssistantReply(assistantError, { steps: currentThinkingSteps })
    } else {
      addCopilotMessage({
        role: 'assistant',
        content:
          'I could not produce a reply for that question. Check that the backend is running and retry, or rephrase with more detail.',
        timestamp: new Date(),
        steps: currentThinkingSteps,
      })
    }

    if (
      proposeBuildPlan &&
      !showPlanModal &&
      !route.metadata?.awaiting_plan_revision &&
      !route.metadata?.build_plan_confirmed &&
      route.source !== 'clarification_plan_rejected' &&
      route.source !== 'clarification_confirmed_build'
    ) {
      addCopilotMessage({
        role: 'assistant',
        content:
          'I could not draft a clear numbered plan from that request. Add more detail (data sources, filters, outputs) and try again.',
        timestamp: new Date(),
      })
    }
    return
  }

  if (routeLoad) {
    let gotWorkflow = false
    let loadedWorkflow: Workflow | null = null
    let loadedName = ''

    await api.copilotLoadStream(
      msg,
      (ev) => {
        handleStreamEvent(ev)
        if (ev.type === 'workflow_created' && ev.workflow) {
          gotWorkflow = true
          gotWorkflowFlag.value = true
          loadedWorkflow = ev.workflow
          loadedName = ev.name
        }
      },
      controller.signal,
      copilotSessionId,
      threadMessages,
    )

    const currentThinkingSteps = snapshotThinkingSteps()
    const assistantText = streamTextRef.current.trim()
    const assistantError = streamErrorRef.current

    focusSherpaSidePanel()
    if (assistantText) {
      await commitStreamedAssistantReply(assistantText, {
        steps: currentThinkingSteps,
        newWorkflow: gotWorkflow
          ? (loadedWorkflow || useWorkflowStore.getState().workflow)
          : undefined,
      })
    } else if (gotWorkflow) {
      addCopilotMessage({
        role: 'assistant',
        content: `Loaded **${loadedName}** onto the canvas.`,
        timestamp: new Date(),
        steps: currentThinkingSteps,
        newWorkflow: loadedWorkflow || useWorkflowStore.getState().workflow,
      })
    } else if (assistantError) {
      await commitStreamedAssistantReply(assistantError, { steps: currentThinkingSteps })
    }
    return
  }

  if (routeAutomate) {
    let gotWorkflow = false
    let createdWorkflow: Workflow | null = null
    let createdName = ''

    await api.copilotAutomateStream(
      msg,
      (ev) => {
        handleStreamEvent(ev)
        if (ev.type === 'workflow_created' && ev.workflow) {
          gotWorkflow = true
          gotWorkflowFlag.value = true
          createdWorkflow = ev.workflow
          createdName = ev.name
        }
      },
      controller.signal,
      currentWorkflow,
      criticIter,
      copilotSessionId,
      threadMessages,
    )

    const currentThinkingSteps = snapshotThinkingSteps()
    const currentFinalSummary = finalSummaryRef.current
    const assistantText = streamTextRef.current.trim()
    const assistantError = streamErrorRef.current
    const automationLink = automationLinkRef.current

    focusSherpaSidePanel()
    if (assistantText) {
      await commitStreamedAssistantReply(assistantText, {
        steps: currentThinkingSteps,
        summary: currentFinalSummary ?? undefined,
        previousWorkflow: gotWorkflow ? workflowBeforeEdit : undefined,
        newWorkflow: gotWorkflow
          ? (createdWorkflow || useWorkflowStore.getState().workflow)
          : undefined,
        automationLink: automationLink ?? undefined,
      })
    } else if (assistantError) {
      await commitStreamedAssistantReply(assistantError, {
        steps: currentThinkingSteps,
        summary: currentFinalSummary ?? undefined,
        automationLink: automationLink ?? undefined,
      })
    } else {
      addCopilotMessage({
        role: 'assistant',
        content: automationLink
          ? 'Your automation is ready.'
          : 'Automation setup finished. Open **Automations** in the left nav to review the schedule and runs.',
        timestamp: new Date(),
        steps: currentThinkingSteps,
        summary: currentFinalSummary ?? undefined,
        automationLink: automationLink ?? undefined,
      })
    }
    return
  }

  {
    store.patchCopilotStream({ copilotActiveRoute: 'build', copilotHarnessGenerating: true })
    patchActivityMode({ activeRoute: 'build', routeIntent: 'build' })
    let gotWorkflow = false
    let createdWorkflow: Workflow | null = null
    let createdName = ''
    let createdNodes = 0

    await api.copilotGenerateStream(
      buildPrompt,
      criticIter,
      (ev) => {
        handleStreamEvent(ev)
        if (ev.type === 'workflow_created' && ev.workflow) {
          gotWorkflow = true
          gotWorkflowFlag.value = true
          createdWorkflow = ev.workflow
          createdName = ev.name
          createdNodes = ev.nodeCount
        }
      },
      controller.signal,
      ctxWorkflow,
      errorHints,
      ctxWorkflow ? selectedNodeId : null,
      copilotSessionId,
      threadMessages,
    )

    store.patchCopilotStream({ copilotHarnessGenerating: false })
    patchActivityMode({ activeRoute: 'build', routeIntent: 'build' })

    const currentThinkingSteps = snapshotThinkingSteps()
    const currentFinalSummary = finalSummaryRef.current
    const assistantText = streamTextRef.current.trim()
    const assistantError = streamErrorRef.current

    focusSherpaSidePanel()
    if (assistantText) {
      await commitStreamedAssistantReply(assistantText, {
        steps: currentThinkingSteps,
        summary: currentFinalSummary ?? undefined,
        previousWorkflow: gotWorkflow ? workflowBeforeEdit : undefined,
        newWorkflow: gotWorkflow
          ? (createdWorkflow || useWorkflowStore.getState().workflow)
          : undefined,
      })
    } else if (gotWorkflow) {
      addCopilotMessage({
        role: 'assistant',
        content: `Built **${createdName}** (${createdNodes} nodes). Loaded on the canvas.`,
        timestamp: new Date(),
        steps: currentThinkingSteps,
        summary: currentFinalSummary ?? undefined,
        previousWorkflow: workflowBeforeEdit,
        newWorkflow: createdWorkflow || useWorkflowStore.getState().workflow,
      })
    } else if (assistantError) {
      await commitStreamedAssistantReply(assistantError, {
        steps: currentThinkingSteps,
        summary: currentFinalSummary ?? undefined,
      })
    } else {
      addCopilotMessage({
        role: 'assistant',
        content:
          'I could not produce a workflow from that request, and no diagnostic details came back from the server. Confirm the backend is running and `GEMINI_API_KEY` is set, then retry — if it fails again you should see a full diagnosis with errors and fix steps.',
        timestamp: new Date(),
        steps: currentThinkingSteps,
        summary: currentFinalSummary ?? undefined,
      })
    }
  }
}

export async function resolveSherpaClarification(
  answers: SherpaClarificationAnswer[],
  criticIter = 3,
): Promise<void> {
  const store = useWorkflowStore.getState()
  const pending = store.copilotPendingClarification
  if (!pending || answers.length === 0) return

  const answerLine = formatAnswersForChat(answers)
  commitClarificationUserAnswer(answerLine)
  await awaitChatAnswerVisible()

  const planApproved =
    (pending.planApproval &&
      answers.some((a) => a.selectionIds.includes('a') || a.selectionIds.includes('yes'))) ||
    (Boolean(pending.pendingRoute.metadata?.propose_build_plan) &&
      !pending.pendingRoute.metadata?.awaiting_plan_revision &&
      answers.some(
        (a) =>
          a.selectionIds.includes('yes') ||
          a.selectionIds.includes('a') ||
          a.selectionIds.includes('approve'),
      ))

  const declined =
    !pending.planApproval &&
    answers.some((a) => a.selectionIds.length === 1 && a.selectionIds[0] === 'no')
  if (declined) {
    store.addCopilotMessage({
      role: 'assistant',
      content: 'Understood — I will not run or change anything until you say what you want next.',
      timestamp: new Date(),
    })
    return
  }

  if (isCopilotStreamRunning()) {
    endStreamUi()
    activeAbortController?.abort()
    activeAbortController = null
  }

  let threadMessages = buildThreadMessages(useWorkflowStore.getState().copilotMessages, {
    excludeLast: false,
  })
  const currentWorkflow = useWorkflowStore.getState().workflow
  const workflowBeforeEdit = currentWorkflow
    ? (JSON.parse(JSON.stringify(currentWorkflow)) as Workflow)
    : null
  const allErrorHints = collectErrorHints(
    store.validationIssues,
    store.runLog,
    store.runError,
  )
  const askContext = {
    current_workflow: currentWorkflow ?? null,
    recent_errors: allErrorHints.length ? allErrorHints : null,
  }

  if (planApproved) {
    threadMessages = buildThreadMessages(useWorkflowStore.getState().copilotMessages, {
      excludeLast: false,
    })
  }

  beginStreamUi()
  const controller = new AbortController()
  activeAbortController = controller
  const gotWorkflowFlag = { value: false }
  const shouldFocusFlag = { value: true }

  const apiAnswers: SherpaClarificationAnswerPayload[] = answers.map((a) => ({
    question_id: a.questionId || PLAN_APPROVAL_QUESTION_ID,
    question: a.question,
    kind: a.kind === 'plan_approval' ? 'confirm' : a.kind,
    selection_ids: a.selectionIds,
    other_text: a.otherText || null,
    selection_labels: a.labels,
  }))

  try {
    const route = planApproved
      ? buildRouteFromPlanApproval(pending, threadMessages)
      : await api.copilotClarifyResolve({
          message: pending.pendingMessage,
          answers: apiAnswers,
          pending_route: pending.pendingRoute,
          has_workflow: Boolean(currentWorkflow),
          session_id: store.copilotSessionId,
          thread_messages: threadMessages,
          current_workflow: currentWorkflow ?? null,
        })

    if (!planApproved) {
      const again = clarificationFromRoute(route, pending.pendingMessage)
      if (again) {
        store.setCopilotPendingClarification(again)
        endStreamUi()
        return
      }
    }

    const routeMsg = planApproved
      ? route.enhanced_question?.trim() || buildPromptFromThread(threadMessages, pending.pendingMessage)
      : buildPromptFromThread(threadMessages, pending.pendingMessage)
    await continueAfterRoute({
      route,
      msg: routeMsg,
      criticIter,
      controller,
      workflowBeforeEdit,
      threadMessages,
      askContext,
      allErrorHints,
      gotWorkflowFlag,
      shouldFocusFlag,
    })
  } catch (e) {
    shouldFocusFlag.value = false
    if ((e as Error).name !== 'AbortError') {
      store.addCopilotMessage({
        role: 'assistant',
        content: `Error: ${(e as Error).message}`,
        timestamp: new Date(),
      })
    }
  } finally {
    endStreamUi()
    clearStreamUiAfterMessage()
    if (shouldFocusFlag.value) {
      focusStudioOnCopilotComplete({ gotWorkflow: gotWorkflowFlag.value })
    }
  }
}

export async function runCopilotSend(msg: string, criticIter = 3): Promise<void> {
  if (isCopilotStreamRunning()) {
    if (!activeAbortController) {
      endStreamUi()
    } else {
      toast.warning('Sherpa is still working on your last message.')
      return
    }
  }

  const store = useWorkflowStore.getState()
  const {
    addCopilotMessage,
    copilotSessionId,
    currentWorkflow,
    validationIssues,
    runLog,
    runError,
    runResult,
    selectedNodeId,
  } = {
    addCopilotMessage: store.addCopilotMessage,
    copilotSessionId: store.copilotSessionId,
    currentWorkflow: store.workflow,
    validationIssues: store.validationIssues,
    runLog: store.runLog,
    runError: store.runError,
    runResult: store.runResult,
    selectedNodeId: store.selectedNodeId,
  }

  const userMsg: CopilotMessage = { role: 'user', content: msg, timestamp: new Date() }
  addCopilotMessage(userMsg)
  const threadMessages = buildThreadMessages(useWorkflowStore.getState().copilotMessages)
  const threadBeforeUser = buildThreadMessages(useWorkflowStore.getState().copilotMessages, {
    excludeLast: true,
  })
  const sampleRunAccept =
    looksLikeActionAcceptance(msg) &&
    lastAssistantOfferedSampleRun(threadBeforeUser) &&
    Boolean(currentWorkflow?.nodes?.length)

  beginStreamUi()

  const workflowBeforeEdit = currentWorkflow
    ? (JSON.parse(JSON.stringify(currentWorkflow)) as Workflow)
    : null
  const allErrorHints = collectErrorHints(validationIssues, runLog, runError)
  const askContext = {
    current_workflow: currentWorkflow ?? null,
    recent_errors: allErrorHints.length ? allErrorHints : null,
  }

  const controller = new AbortController()
  activeAbortController = controller

  let gotWorkflowOnComplete = false
  let shouldFocusOnComplete = true

  try {
    let routeWorkflowName = currentWorkflow?.name?.trim() || null
    const quotedCatalog = await resolveFirstQuotedWorkflowInMessage(msg)
    if (quotedCatalog) {
      routeWorkflowName = quotedCatalog.canonicalName
    }

    const route = sampleRunAccept
      ? clientSampleRunAcceptRoute()
      : await api.copilotRoute(msg, {
          has_workflow: Boolean(currentWorkflow),
          has_run_log: runLog.length > 0,
          workflow_name: routeWorkflowName,
          run_id: runResult?.run_id ?? null,
          run_workflow_name: routeWorkflowName ?? runResult?.workflow ?? null,
          recent_errors: allErrorHints.length ? allErrorHints : null,
          session_id: copilotSessionId,
          thread_messages: threadMessages,
          current_workflow: currentWorkflow ?? null,
        })

    const thinkingPreview = route.thinking_preview || route.disposition?.thinking
    if (thinkingPreview?.trim()) {
      syncThinking(() => [thinkingStepFromPreview(thinkingPreview, false)])
    }

    patchActivityMode({
      disposition: route.disposition,
      routeIntent: route.intent,
      planPhaseStreaming: Boolean(
        route.metadata?.propose_build_plan || route.metadata?.propose_fix_plan,
      ),
    })

    const pendingClar = clarificationFromRoute(route, msg)
    if (pendingClar) {
      shouldFocusOnComplete = false
      store.setCopilotPendingClarification(pendingClar)
      patchActivityMode({ pendingClarification: true })
      addCopilotMessage({
        role: 'assistant',
        content: pendingClar.questions[0]?.question ?? 'I need a quick clarification before I proceed.',
        timestamp: new Date(),
      })
      endStreamUi()
      clearStreamUiAfterMessage()
      return
    }

    const gotWorkflowFlag = { value: false }
    const shouldFocusFlag = { value: shouldFocusOnComplete }
    await continueAfterRoute({
      route,
      msg,
      criticIter,
      controller,
      workflowBeforeEdit,
      threadMessages,
      askContext,
      allErrorHints,
      gotWorkflowFlag,
      shouldFocusFlag,
    })
    gotWorkflowOnComplete = gotWorkflowFlag.value
    shouldFocusOnComplete = shouldFocusFlag.value
  } catch (e) {
    shouldFocusOnComplete = false
    if ((e as Error).name === 'AbortError') {
      addCopilotMessage({
        role: 'assistant',
        content: 'Processing stopped by user.',
        timestamp: new Date(),
      })
    } else {
      addCopilotMessage({
        role: 'assistant',
        content: `Error: ${(e as Error).message}\n\nMake sure the backend is running (check /api/health and GEMINI_API_KEY in backend/.env).`,
        timestamp: new Date(),
      })
    }
  } finally {
    endStreamUi()
    clearStreamUiAfterMessage()
    if (shouldFocusOnComplete) {
      focusStudioOnCopilotComplete({ gotWorkflow: gotWorkflowOnComplete })
    }
  }
}

