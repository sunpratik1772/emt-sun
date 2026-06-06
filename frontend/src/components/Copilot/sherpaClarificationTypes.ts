import type { CopilotRouteResponse, SherpaClarificationOption } from '../../services/api'
import { buildPromptWithApprovedPlan } from './copilotUtils'

export const PLAN_APPROVAL_QUESTION_ID = 'q_plan_approve'

export type SherpaClarificationQuestion = {
  id: string
  kind: 'confirm' | 'choice' | 'plan_approval'
  question: string
  options: SherpaClarificationOption[]
  defaultOptionId: string | null
  allowMultiple: boolean
}

export type SherpaClarificationAnswer = {
  questionId: string
  question: string
  kind: 'confirm' | 'choice' | 'plan_approval'
  selectionIds: string[]
  otherText: string
  labels: string[]
}

export type SherpaPendingClarification = {
  questions: SherpaClarificationQuestion[]
  pendingMessage: string
  pendingRoute: CopilotRouteResponse
  /** Plan approval uses Approve/Reject only — no "Something else". */
  planApproval?: boolean
  /** Step-by-step plan shown above Approve / Reject. */
  planSteps?: string[]
}

const OTHER_ID = 'other'

export function isOtherOption(opt: SherpaClarificationOption): boolean {
  return opt.id === OTHER_ID || /something else/i.test(opt.label || '')
}

export function clarificationFromRoute(
  route: CopilotRouteResponse,
  pendingMessage: string,
): SherpaPendingClarification | null {
  const clar = route.clarification
  if (!clar?.needed) return null

  const rawQuestions = clar.questions?.length
    ? clar.questions
    : clar.question && clar.options?.length
      ? [
          {
            id: 'q1',
            kind: clar.kind === 'choice' ? 'choice' : 'confirm',
            question: clar.question,
            options: clar.options,
            default_option_id: clar.default_option_id,
            allow_multiple: clar.kind === 'choice',
          },
        ]
      : []

  const questions: SherpaClarificationQuestion[] = rawQuestions.map((q, i) => {
    const isPlanApproval = (q.id || '') === PLAN_APPROVAL_QUESTION_ID
    const kind = isPlanApproval ? 'plan_approval' : q.kind === 'choice' ? 'choice' : 'confirm'
    const baseOpts = (q.options || []).filter((o) => !isOtherOption(o))
    const options = isPlanApproval
      ? baseOpts
      : [
          ...baseOpts,
          {
            id: OTHER_ID,
            label: 'Something else',
            description: 'Describe what you want in your own words',
          },
        ]
    return {
      id: q.id || `q${i + 1}`,
      kind,
      question: q.question,
      options,
      defaultOptionId: q.default_option_id ?? options[0]?.id ?? null,
      allowMultiple: kind === 'choice' ? q.allow_multiple !== false : false,
    }
  })

  if (!questions.length) return null

  const planApproval = questions.some((q) => q.kind === 'plan_approval')
  return { questions, pendingMessage, pendingRoute: route, planApproval }
}

/** Executable build route after the user approves a presented plan — no second clarify round. */
export function buildRouteFromPlanApproval(
  pending: SherpaPendingClarification,
  threadMessages: Array<{ role: 'user' | 'assistant'; content: string }>,
): CopilotRouteResponse {
  const base = pending.pendingRoute
  const meta = { ...(base.metadata ?? {}) }
  const original = meta.original_user_request?.trim() || pending.pendingMessage.trim()
  const buildPrompt = buildPromptWithApprovedPlan(
    threadMessages,
    original,
    pending.planSteps ?? [],
  )
  const isFixPlan = Boolean(meta.propose_fix_plan)
  return {
    ...base,
    intent: 'build',
    reason: isFixPlan ? 'User approved the fix plan' : 'User approved the build plan',
    enhanced_question: buildPrompt,
    source: 'clarification_confirmed_build',
    clarification: undefined,
    metadata: {
      ...meta,
      build_plan_confirmed: true,
      propose_build_plan: false,
      propose_fix_plan: false,
      awaiting_plan_revision: false,
      clarification_resolved: true,
      edit_existing_workflow: isFixPlan,
      wants_sample_run: false,
      original_user_request: buildPrompt,
      clarification_answer: isFixPlan ? 'Approve — apply fix on canvas' : 'Approve — create on canvas',
    },
  }
}

export function planApprovalFromRoute(
  route: CopilotRouteResponse,
  pendingMessage: string,
  planText?: string,
  planSteps?: string[],
): SherpaPendingClarification {
  const wfName = route.metadata?.workflow_name?.trim() || 'the workflow'
  const isFixPlan = Boolean(route.metadata?.propose_fix_plan)
  return {
    planApproval: true,
    pendingMessage,
    pendingRoute: route,
    planSteps,
    questions: [
      {
        id: PLAN_APPROVAL_QUESTION_ID,
        kind: 'plan_approval',
        question: isFixPlan
          ? `Approve this fix plan and apply changes to **${wfName}**?`
          : `Approve this plan and create **${wfName}** on the canvas?`,
        options: [
          {
            id: 'a',
            label: 'Approve',
            description: isFixPlan
              ? 'Apply the fix plan on the canvas'
              : 'Build on the canvas from the plan above',
          },
          {
            id: 'b',
            label: 'Reject',
            description: 'Revise the plan before building',
          },
        ],
        defaultOptionId: 'a',
        allowMultiple: false,
      },
    ],
  }
}

export function formatAnswersForChat(answers: SherpaClarificationAnswer[]): string {
  return answers
    .map((a) => {
      if (a.kind === 'plan_approval' && a.selectionIds.includes('b') && a.otherText.trim()) {
        return `Reject plan — ${a.otherText.trim()}`
      }
      if (a.selectionIds.includes(OTHER_ID) && a.otherText.trim()) {
        return a.otherText.trim()
      }
      return a.labels.filter(Boolean).join('; ')
    })
    .filter(Boolean)
    .join('\n')
}
