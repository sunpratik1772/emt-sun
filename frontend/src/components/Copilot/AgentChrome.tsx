import { useEffect, useMemo, useState } from 'react'
import {
  Check,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Sparkles,
  X,
} from '../../icons/arc'
import { SherpaMark } from '../SherpaMark'
import { MarkdownMessage } from './CopilotMarkdown'
import type { AgentFinalSummary, ThinkingStep } from './thinkingTypes'
import { collapsedStepCaption, isGenericPlanningFluff, useTypewriterText } from './useTypewriterText'

export function AgentIcon({ live, size = 28 }: { live?: boolean; size?: number }) {
  const mark = Math.round(size * 0.62)
  return (
    <span
      className={`agent-icon shrink-0${live ? ' agent-icon--live' : ''}`}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <SherpaMark size={mark} />
    </span>
  )
}

export function AgentIdleWave() {
  return (
    <div className="think__step min-w-0" data-step-kind="idle">
      <span
        className="think__bullet"
        style={{
          background: 'color-mix(in srgb, var(--accent) 14%, transparent)',
          color: 'var(--accent)',
          marginTop: 2,
        }}
      >
        <Loader2 size={10} className="animate-spin" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="think__step-label" style={{ color: 'var(--text-2)', fontWeight: 400 }}>
          Working…
        </div>
      </div>
    </div>
  )
}

function LiveActivityText({ text, muted }: { text: string; muted?: boolean }) {
  return (
    <span
      key={text}
      className="agent-activity-text text-[13px] leading-snug min-w-0"
      style={{ color: muted ? 'var(--text-2)' : 'var(--text-0)' }}
    >
      {text}
    </span>
  )
}

function stepBodyText(step: ThinkingStep): string {
  const raw = (step.detail || step.outcome || '').trim()
  if (!raw) return ''
  const title = step.text.trim().toLowerCase()
  if (raw.toLowerCase() === title) return ''
  return raw
}

function collapsedCaption(step: ThinkingStep): string {
  return collapsedStepCaption(step)
}

function UnderstandingContextRow() {
  return (
    <div className="think__step min-w-0" data-step-kind="context">
      <span
        className="think__bullet"
        style={{
          background: 'color-mix(in srgb, var(--accent) 14%, transparent)',
          color: 'var(--accent)',
          marginTop: 2,
        }}
      >
        <Loader2 size={10} className="animate-spin" />
      </span>
      <div className="flex-1 min-w-0">
        <div className="think__step-label">
          Understanding context…
          <span className="num live-blink" style={{ color: 'var(--text-3)' }}> ▍</span>
        </div>
      </div>
    </div>
  )
}

function isThinkingStep(step: ThinkingStep): boolean {
  return step.kind === 'thinking' || step.subagentType === 'thinking'
}

function thoughtDurationSec(step: ThinkingStep): number {
  if (step.durationSec != null) return Math.max(1, step.durationSec)
  if (step.startedAt) return Math.max(1, Math.round((Date.now() - step.startedAt) / 1000))
  return 1
}

function ThoughtForBlock({
  step,
  isStreaming,
  outputPhase,
  onMonologueComplete,
}: {
  step: ThinkingStep
  isStreaming: boolean
  outputPhase: boolean
  onMonologueComplete?: () => void
}) {
  const [open, setOpen] = useState(false)
  const monologue = (step.detail || step.outcome || '').trim()
  const thinkingActive = isStreaming && !outputPhase && !step.done
  const typingActive = Boolean(monologue) && !outputPhase && (isStreaming || !step.done)
  const duration = useMemo(
    () => thoughtDurationSec(step),
    [step.durationSec, step.startedAt, step.done],
  )

  const { text: streamed, isTyping } = useTypewriterText(monologue, typingActive, {
    mode: 'line',
    catchUp: true,
    paceMs: 520,
  })

  const showSpinner = thinkingActive || isTyping
  const label = showSpinner ? 'Thinking…' : `Thought for ${duration}s`

  useEffect(() => {
    if (monologue && !isTyping) {
      onMonologueComplete?.()
    }
  }, [monologue, isTyping, onMonologueComplete])

  const showBody = Boolean(monologue) && (typingActive || open)
  const bodyText = typingActive ? streamed : monologue

  return (
    <div className="think__step min-w-0" data-step-kind="thinking">
      <span className="think__bullet" style={{ background: 'color-mix(in srgb, var(--accent) 14%, transparent)', color: 'var(--accent)', marginTop: 2 }}>
        {showSpinner ? (
          <Loader2 size={10} className="animate-spin" />
        ) : (
          <Check size={10} strokeWidth={3} />
        )}
      </span>
      <div className="flex-1 min-w-0">
        <button
          type="button"
          className="flex items-center gap-1.5 w-full text-left py-0.5 min-w-0 cursor-pointer"
          onClick={() => monologue && !showSpinner && setOpen((v) => !v)}
          aria-expanded={showBody}
          disabled={!monologue || showSpinner}
        >
          <span className="think__step-label flex-1 truncate">
            {label}
          </span>
          {monologue && !showSpinner && (
            <ChevronRight
              size={11}
              className={`shrink-0 transition-transform${open ? ' rotate-90' : ''}`}
              style={{ color: 'var(--text-3)' }}
            />
          )}
        </button>
        {showBody ? (
          <div
            className="think__step-detail break-words min-w-0"
          >
            <MarkdownMessage content={bodyText} variant="compact" />
            {isTyping ? (
              <span className="num live-blink" style={{ color: 'var(--text-3)' }}> ▍</span>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function shouldShowCollapsedStep(step: ThinkingStep): boolean {
  if (isThinkingStep(step)) return false
  if (step.contextualPlan) return false
  if (step.kind !== 'parallel') return true
  const body = stepBodyText(step)
  if (!body) return true
  return !isGenericPlanningFluff(body)
}

/** Drop duplicate completed rows (e.g. two general parallel tasks mapped to the same label). */
function dedupeCompletedSteps(steps: ThinkingStep[]): ThinkingStep[] {
  const seen = new Set<string>()
  return steps.filter((step) => {
    const key = `${step.text}|${step.subagentType ?? ''}|${step.outcome ?? ''}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function CollapsedStepRow({ step }: { step: ThinkingStep }) {
  const [open, setOpen] = useState(false)
  const body = stepBodyText(step)
  const caption = collapsedCaption(step)
  const isFailed = step.status === 'error'

  return (
    <div className="think__step min-w-0" data-step-kind={step.kind ?? 'stage'}>
      <span
        className="think__bullet"
        style={{
          background: isFailed
            ? 'color-mix(in srgb, var(--danger) 14%, transparent)'
            : 'color-mix(in srgb, var(--success) 14%, transparent)',
          color: isFailed ? 'var(--danger)' : 'var(--success)',
          marginTop: 2,
        }}
      >
        {isFailed ? (
          <X size={10} strokeWidth={3} />
        ) : (
          <Check size={10} strokeWidth={3} />
        )}
      </span>
      <div className="flex-1 min-w-0">
        <button
          type="button"
          className="flex items-center gap-1.5 w-full text-left py-0.5 min-w-0 cursor-pointer"
          onClick={() => body && setOpen((v) => !v)}
          aria-expanded={open}
          disabled={!body}
        >
          <span className="think__step-label flex-1 truncate">
            {caption}
          </span>
          {body && (
            <ChevronRight
              size={11}
              className={`shrink-0 transition-transform${open ? ' rotate-90' : ''}`}
              style={{ color: 'var(--text-3)' }}
            />
          )}
        </button>
        {open && body ? (
          <div
            className="think__step-detail break-words min-w-0"
          >
            <MarkdownMessage content={body} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

function ActiveStepRow({ step }: { step: ThinkingStep }) {
  const body = stepBodyText(step) || 'In progress.'
  const { text: streamed, isTyping } = useTypewriterText(body, true, { mode: 'line' })

  return (
    <div className="think__step min-w-0" data-step-kind={step.kind ?? 'stage'}>
      <span
        className="think__bullet"
        style={{
          background: 'color-mix(in srgb, var(--accent) 14%, transparent)',
          color: 'var(--accent)',
          marginTop: 2,
        }}
      >
        <Loader2 size={10} className="animate-spin" />
      </span>
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <div className="think__step-label truncate">{step.text}</div>
        <div className="think__step-detail break-words min-w-0">
          <MarkdownMessage content={streamed} variant="compact" />
          {isTyping ? (
            <span className="num live-blink" style={{ color: 'var(--text-3)' }}> ▍</span>
          ) : null}
        </div>
      </div>
    </div>
  )
}

interface AgentActivityTimelineProps {
  steps: ThinkingStep[]
  summary?: AgentFinalSummary | null
  isStreaming: boolean
  outputPhase?: boolean
  onMonologueComplete?: () => void
}

export function AgentActivityTimeline({
  steps,
  summary,
  isStreaming,
  outputPhase = false,
  onMonologueComplete,
}: AgentActivityTimelineProps) {
  const thinkingStep = steps.find(isThinkingStep)
  const thinkingMonologue = thinkingStep
    ? (thinkingStep.detail || thinkingStep.outcome || '').trim()
    : ''
  const operationalSteps = steps.filter((s) => !isThinkingStep(s))
  const showUnderstanding =
    isStreaming && !outputPhase && !thinkingMonologue && operationalSteps.length === 0
  const errorSteps = steps.filter((s) => s.status === 'error')
  const thoughtExclusive =
    Boolean(thinkingStep) && isStreaming && !outputPhase && thinkingStep!.done !== true

  if (isStreaming && steps.length === 0) {
    return (
      <div className="agent-activity-timeline flex flex-col gap-1.5 py-1 select-text">
        <div className="think">
          <div className="think__head">
            <Sparkles size={13} style={{ color: 'var(--accent)' }} />
            <span>Thinking process…</span>
          </div>
          <div className="think__steps">
            <UnderstandingContextRow />
          </div>
        </div>
      </div>
    )
  }

  if (thoughtExclusive) {
    return (
      <div className="agent-activity-timeline flex flex-col gap-1.5 py-1 select-text">
        <div className="think">
          <div className="think__head">
            <Sparkles size={13} style={{ color: 'var(--accent)' }} />
            <span>Thinking process…</span>
          </div>
          <div className="think__steps">
            <ThoughtForBlock
              step={thinkingStep!}
              isStreaming={isStreaming}
              outputPhase={outputPhase}
              onMonologueComplete={onMonologueComplete}
            />
            {errorSteps.map((step) => (
              <CollapsedStepRow key={step.id} step={{ ...step, collapsed: true }} />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (showUnderstanding) {
    return (
      <div className="agent-activity-timeline flex flex-col gap-1.5 py-1 select-text">
        <div className="think">
          <div className="think__head">
            <Sparkles size={13} style={{ color: 'var(--accent)' }} />
            <span>Thinking process…</span>
          </div>
          <div className="think__steps">
            <UnderstandingContextRow />
            {errorSteps.map((step) => (
              <CollapsedStepRow key={step.id} step={{ ...step, collapsed: true }} />
            ))}
          </div>
        </div>
      </div>
    )
  }

  const completed = dedupeCompletedSteps(operationalSteps.filter((s) => s.done)).filter(
    shouldShowCollapsedStep,
  )
  const active = operationalSteps.filter((s) => !s.done)
  const forceCollapsed = outputPhase || (!isStreaming && completed.length > 0 && active.length === 0)

  if (!thinkingStep && completed.length === 0 && active.length === 0 && !isStreaming) {
    return null
  }

  const duration = thinkingStep ? thoughtDurationSec(thinkingStep) : 2
  const headerText = isStreaming && !outputPhase ? 'Thinking process…' : `Thought for ${duration}s`

  return (
    <div className="agent-activity-timeline flex flex-col gap-1.5 py-1 select-text">
      <div className="think">
        <div className="think__head">
          <Sparkles size={13} style={{ color: 'var(--accent)' }} />
          <span>{headerText}</span>
        </div>
        <div className="think__steps">
          {thinkingStep && thinkingMonologue ? (
            <ThoughtForBlock
              step={thinkingStep}
              isStreaming={isStreaming}
              outputPhase={outputPhase}
              onMonologueComplete={onMonologueComplete}
            />
          ) : null}

          {completed.length > 0 ? (
            <>
              {completed.map((step) => (
                <CollapsedStepRow key={step.id} step={{ ...step, collapsed: true }} />
              ))}
            </>
          ) : null}

          {active.length > 0 ? (
            <>
              {active.map((step) => (
                <ActiveStepRow key={step.id} step={step} />
              ))}
            </>
          ) : isStreaming && !outputPhase && operationalSteps.length === 0 ? (
            <AgentIdleWave />
          ) : null}

          {errorSteps.map((step) =>
            operationalSteps.some((s) => s.id === step.id) ? null : (
              <CollapsedStepRow key={step.id} step={{ ...step, collapsed: true }} />
            ),
          )}
        </div>
      </div>

      {summary && forceCollapsed && !isStreaming ? (
        <div
          className="mt-1 p-2.5 rounded-lg border"
          style={{
            background: 'color-mix(in srgb, var(--accent) 5%, transparent)',
            borderColor: 'color-mix(in srgb, var(--accent) 15%, var(--border-soft))',
          }}
        >
          <div
            className="font-mono text-[10px] font-bold tracking-wider"
            style={{ color: 'var(--accent)', textTransform: 'uppercase', marginBottom: 6 }}
          >
            {summary.title}
          </div>
          {summary.bullets.map((bullet, index) => (
            <div key={index} className="text-[11px] leading-relaxed" style={{ color: 'var(--text-2)' }}>
              {bullet}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

interface RailwayStepListProps {
  steps: ThinkingStep[]
  summary?: AgentFinalSummary | null
  open: boolean
  isStreaming: boolean
  outputPhase?: boolean
  onToggle: () => void
  onMonologueComplete?: () => void
}

/** Cursor-style inline activity: streaming active steps, collapsed completed steps above output. */
export function RailwayStepList({
  steps,
  summary,
  isStreaming,
  outputPhase,
  onMonologueComplete,
}: RailwayStepListProps) {
  return (
    <AgentActivityTimeline
      steps={steps}
      summary={summary}
      isStreaming={isStreaming}
      outputPhase={outputPhase}
      onMonologueComplete={onMonologueComplete}
    />
  )
}
