import type { CopilotErrorHint, RunLogEntry, ValidationIssue } from '../../types'

export type ExamplePrompt = { text: string; tag: string }

export const TAG_COLORS: Record<string, string> = {
  excel: 'var(--success)',
  csv: 'var(--success)',
  ai: 'var(--info)',
  mcp: 'var(--warning)',
  github: 'var(--text-2)',
  slack: 'var(--warning)',
  notion: 'var(--text-2)',
  email: 'var(--info)',
  surveillance: 'var(--danger)',
  pipeline: 'var(--accent)',
  advanced: 'var(--accent)',
  data: 'var(--success)',
  nodes: 'var(--text-3)',
  integrations: 'var(--warning)',
  logic: 'var(--info)',
}

export const SAMPLE_RUN_PAYLOAD = {
  trader_id: 'T001',
  book: 'FX-SPOT',
  alert_date: '2024-01-15',
  currency_pair: 'EUR/USD',
  alert_id: 'ALT-001',
}

export function normalizeTextareaHeight(el: HTMLTextAreaElement | null): void {
  if (!el) return
  el.style.height = 'auto'
  // Keep the input compact but allow a few lines before scrolling.
  const next = Math.min(160, Math.max(44, el.scrollHeight))
  el.style.height = `${next}px`
}
const RUN_OUTPUT_QUESTION =
  /\b(analy[sz]e|describe|explain|summari[sz]e|review|walk me through|tell me about|what happened|what was the output|what did it produce|what did the run|how many rows|row count|show me the (results?|output|data)|top\s+\d+|who are the|which trader|name.*trader|output of|results of|run summary|execution summary|latest run|last run|reliability|suggest.*change)\b/i

const BUILD_OVERRIDE =
  /\b(build|create|generate|fix|repair|add node|remove node|edit workflow)\b/i

/** True when the user is asking about a completed run (needs run_log), not platform Q&A. */
export function isRunOutputQuestion(prompt: string): boolean {
  const text = prompt.trim()
  if (!text) return false
  if (BUILD_OVERRIDE.test(text)) return false
  return RUN_OUTPUT_QUESTION.test(text)
}

const ACTION_ACCEPTANCE =
  /^(?:do it|do that|do this|yes(?: please)?|please do|go ahead|sure|ok(?:ay)?|yep|yeah|yup|eys|yse|sounds good)\.?$/i

export function looksLikeActionAcceptance(prompt: string): boolean {
  const text = prompt.trim()
  if (!text) return false
  if (ACTION_ACCEPTANCE.test(text)) return true
  const words = text.split(/\s+/)
  return words.length <= 5 && /\b(do it|do that|apply|fix it|yes|go ahead|sure|okay|eys)\b/i.test(text)
}

const SAMPLE_RUN_OFFER =
  /want me to start a sample run|run .{0,80}sample data|re-run .{0,80}sample data/i

/** True when the last assistant turn offered a sample run the user can accept with "yes". */
export function lastAssistantOfferedSampleRun(messages: CopilotThreadMessage[]): boolean {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i]
    if (msg.role !== 'assistant') continue
    const tail = (msg.content || '').slice(-900)
    return SAMPLE_RUN_OFFER.test(tail)
  }
  return false
}

export function shouldEditExistingWorkflow(
  prompt: string,
  opts?: { threadMessages?: CopilotThreadMessage[] },
): boolean {
  const text = prompt.toLowerCase()
  if (looksLikeActionAcceptance(prompt) && lastAssistantOfferedSampleRun(opts?.threadMessages ?? [])) {
    return false
  }
  if (/\b(create|generate|build|make|new)\b/.test(text) && !/\b(improve|extend|enhance)\b/.test(text)) {
    return false
  }
  return /\b(fix|repair|edit|update|change|modify|add|remove|delete|replace|improve|enhance|extend|this|current|existing|canvas)\b/.test(
    text,
  )
}

export function inputModeHint(
  prompt: string,
  workflowName: string,
  opts?: { threadMessages?: CopilotThreadMessage[] },
): 'run' | 'edit' | 'generate' {
  if (looksLikeActionAcceptance(prompt) && lastAssistantOfferedSampleRun(opts?.threadMessages ?? [])) {
    return 'run'
  }
  if (shouldEditExistingWorkflow(prompt, opts)) return 'edit'
  if (prompt.trim()) return 'generate'
  return 'edit'
}

export type CopilotThreadMessage = { role: 'user' | 'assistant'; content: string }

/** Prior turns for backend thread context (excludes the message being sent now). */
export function buildThreadMessages(
  messages: Array<{ role: string; content: string }>,
  opts?: { excludeLast?: boolean; maxTurns?: number },
): CopilotThreadMessage[] {
  const excludeLast = opts?.excludeLast ?? true
  const maxTurns = opts?.maxTurns ?? 16
  const slice = excludeLast && messages.length ? messages.slice(0, -1) : messages
  return slice.slice(-maxTurns).map((m) => ({
    role: m.role === 'assistant' ? 'assistant' : 'user',
    content: (m.content || '').slice(0, 4000),
  }))
}

export function collectErrorHints(
  validationIssues: ValidationIssue[] | null,
  runLog: RunLogEntry[],
  runError: string | null,
): CopilotErrorHint[] {
  const hints: CopilotErrorHint[] = []
  const seen = new Set<string>()

  const push = (h: CopilotErrorHint) => {
    const key = `${h.node_id ?? ''}::${h.message}`
    if (seen.has(key)) return
    seen.add(key)
    hints.push(h)
  }

  for (const issue of validationIssues ?? []) {
    push({
      kind: 'validation',
      code: issue.code,
      node_id: issue.node_id ?? undefined,
      severity: issue.severity,
      message: issue.message,
    })
  }

  for (const entry of runLog) {
    if (entry.status !== 'error' || !entry.error) continue
    push({
      kind: 'runtime',
      node_id: entry.node_id,
      severity: 'error',
      // Include the node type in the message so the LLM doesn't have
      // to cross-reference it against the attached DAG to diagnose.
      message: entry.node_type
        ? `${entry.node_type} (${entry.node_id}): ${entry.error}`
        : `${entry.node_id}: ${entry.error}`,
    })
  }

  if (runError && !validationIssues?.length) {
    // Only include the generic runError if the structured validator
    // path didn't already cover the failure — otherwise we'd double-
    // report the same underlying issue.
    push({ kind: 'runtime', severity: 'error', message: runError })
  }

  return hints.slice(0, 20)
}

const NEXT_STEP_BLOCK_RE =
  /(?:\*\*)?Next step:(?:\*\*)?\s*[\s\S]*$/i

const PLAN_STEP_RE = /^\s*\d+[.)]\s+\S/m
const PLAN_HEADER_RE = /\b(?:numbered\s+)?plan\b/i
const PLAN_LABELED_STEP_RE = /^\s*[A-Za-z][\w\s]{1,40}:\s+\S/

/** Short chat line shown while the full plan lives in the approval panel only. */
export const PLAN_PHASE_CHAT_ACK = 'Below is the plan.'

export function planPhaseChatAcknowledgement(_fullText?: string): string {
  return PLAN_PHASE_CHAT_ACK
}

/** Markdown plan block shown in chat before the user approves. */
export function formatApprovedPlanForChat(steps: string[]): string {
  if (!steps.length) return ''
  const lines = steps.map((step, i) => `${i + 1}. ${step.trim()}`)
  return `**Plan**\n\n${lines.join('\n')}`
}

/** Assistant chat line for plan approval — intro plus numbered steps. */
export function formatPlanPhaseChatMessage(steps: string[]): string {
  const plan = formatApprovedPlanForChat(steps)
  return plan ? `${PLAN_PHASE_CHAT_ACK}\n\n${plan}` : PLAN_PHASE_CHAT_ACK
}

/** Text before the first numbered or labeled plan step (not shown in chat during plan phase). */
export function extractPlanIntro(text: string): string {
  const body = stripNextActionFooter(text)
  if (!body) return ''
  let cutAt = body.length
  const numbered = body.search(PLAN_STEP_RE)
  if (numbered >= 0) cutAt = Math.min(cutAt, numbered)
  const labeled = body.search(PLAN_LABELED_STEP_RE)
  if (labeled >= 0) cutAt = Math.min(cutAt, labeled)
  return body.slice(0, cutAt).trim()
}

export function stripNextActionFooter(text: string): string {
  return (text || '').replace(NEXT_STEP_BLOCK_RE, '').trim()
}

/** True when assistant text contains a concrete numbered build plan. */
export function hasBuildPlanContent(text: string): boolean {
  const body = stripNextActionFooter(text)
  if (!body || body.length < 40) return false
  const stepMatches = body.match(new RegExp(PLAN_STEP_RE.source, 'gm')) ?? []
  if (stepMatches.length >= 2) return true
  if (stepMatches.length === 1 && PLAN_HEADER_RE.test(body)) return true
  return false
}

/** Numbered / labeled plan steps for the approval modal. */
export function extractPlanSteps(text: string): string[] {
  const body = stripNextActionFooter(text)
  if (!body) return []
  const steps: string[] = []
  const inPlan = PLAN_HEADER_RE.test(body) || /here is a (?:revised )?plan/i.test(body)
  for (const raw of body.split('\n')) {
    const line = raw.trim()
    if (!line) continue
    const numbered = line.match(/^\d+[.)]\s*(.+)/)
    if (numbered) {
      steps.push(numbered[1].trim())
      continue
    }
    const labeled = line.match(/^([A-Za-z][\w\s]*):\s*(.+)/)
    if (labeled && (inPlan || steps.length > 0 || PLAN_LABELED_STEP_RE.test(line))) {
      steps.push(`${labeled[1].trim()}: ${labeled[2].trim()}`)
    }
  }
  return steps
}

/** Build prompt for harness after plan approval — original request plus approved plan. */
export function buildPromptWithApprovedPlan(
  threadMessages: Array<{ role: string; content: string }>,
  fallback: string,
  planSteps: string[],
): string {
  const userPart = buildPromptFromThread(threadMessages, fallback)
  const planBlock = formatApprovedPlanForChat(planSteps)
  if (!planBlock) return userPart
  return `${userPart}\n\nApproved plan to build on the canvas:\n${planBlock}`
}

export function buildPromptFromThread(
  threadMessages: Array<{ role: string; content: string }>,
  fallback: string,
): string {
  const users = threadMessages
    .filter((m) => m.role === 'user')
    .map((m) => (m.content || '').trim())
    .filter(Boolean)
  if (users.length === 0) return fallback.trim()
  return users.join('\n\n')
}
