import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, ChevronLeft, ChevronRight, CornerDownLeft, MessageCircle } from 'lucide-react'
import { useEscapeKey } from '../../hooks/useFocusTrap'
import type { SherpaClarificationOption } from '../../services/api'
import { MarkdownMessage } from './CopilotMarkdown'
import {
  formatAnswersForChat,
  isOtherOption,
  type SherpaClarificationAnswer,
  type SherpaClarificationQuestion,
  type SherpaPendingClarification,
} from './sherpaClarificationTypes'
import '../../styles/sherpa-clarification.css'

type Props = {
  pending: SherpaPendingClarification
  onSubmit: (answers: SherpaClarificationAnswer[]) => void
  onSkip: () => void
}

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

function optionLetter(index: number, id: string, kind: SherpaClarificationQuestion['kind']): string {
  if ((kind === 'choice' || kind === 'plan_approval') && /^[a-z]$/i.test(id)) {
    return id.toUpperCase()
  }
  return LETTERS[index] ?? String(index + 1)
}

function optionDisplayText(opt: SherpaClarificationOption, planApproval?: boolean): string {
  const label = (opt.label || '').trim()
  const desc = (opt.description || '').trim()
  if (planApproval) return label
  if (label && desc && !label.toLowerCase().includes(desc.slice(0, 12).toLowerCase())) {
    return `${label} — ${desc}`
  }
  return desc || label
}

function plainQuestion(text: string): string {
  return (text || '').replace(/\*\*([^*]+)\*\*/g, '$1').trim()
}

function defaultSelectionForQuestion(q: SherpaClarificationQuestion): string[] {
  const id = q.defaultOptionId ?? q.options[0]?.id
  return id ? [id] : []
}

export function SherpaClarificationPanel({ pending, onSubmit, onSkip }: Props) {
  const rootRef = useRef<HTMLDivElement>(null)
  const questions = pending.questions
  const total = questions.length
  const [questionIndex, setQuestionIndex] = useState(0)
  const [completed, setCompleted] = useState<SherpaClarificationAnswer[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>(() =>
    defaultSelectionForQuestion(questions[0]),
  )
  const [otherText, setOtherText] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [rejectReasonStep, setRejectReasonStep] = useState(false)
  const [queueOpen, setQueueOpen] = useState(true)

  const current = questions[questionIndex]
  const isLast = questionIndex >= total - 1
  const multi = current.allowMultiple && current.kind === 'choice'
  const otherSelected = selectedIds.includes('other')
  const planApproval = Boolean(pending.planApproval)

  const submitPlanApproval = useCallback(
    (selectionId: 'a' | 'b', reason = '') => {
      const opt = current.options.find((o) => o.id === selectionId)
      onSubmit([
        {
          questionId: current.id,
          question: current.question,
          kind: current.kind,
          selectionIds: [selectionId],
          otherText: reason.trim(),
          labels: [opt?.label || selectionId],
        },
      ])
    },
    [current, onSubmit],
  )

  useEffect(() => {
    setQuestionIndex(0)
    setCompleted([])
    setSelectedIds(defaultSelectionForQuestion(questions[0]))
    setOtherText('')
    setRejectReason('')
    setRejectReasonStep(false)
  }, [pending])

  useEffect(() => {
    setSelectedIds(defaultSelectionForQuestion(current))
    setOtherText('')
    setRejectReason('')
    setRejectReasonStep(false)
  }, [questionIndex, current.id])

  const canContinue = useMemo(() => {
    if (planApproval) return false
    if (selectedIds.length === 0) return false
    if (otherSelected && !otherText.trim()) return false
    return true
  }, [otherSelected, otherText, planApproval, selectedIds.length])

  const buildCurrentAnswer = useCallback((): SherpaClarificationAnswer => {
    const labels = selectedIds.map((id) => {
      const opt = current.options.find((o) => o.id === id)
      return opt ? optionDisplayText(opt, planApproval) : id
    })
    return {
      questionId: current.id,
      question: current.question,
      kind: current.kind,
      selectionIds: [...selectedIds],
      otherText: otherText.trim(),
      labels,
    }
  }, [current, otherText, selectedIds])

  const handleOptionClick = useCallback(
    (opt: SherpaClarificationOption) => {
      const id = opt.id
      if (isOtherOption(opt)) {
        setSelectedIds([id])
        return
      }
      if (!multi) {
        setSelectedIds([id])
        return
      }
      setSelectedIds((prev) => {
        const withoutOther = prev.filter((x) => x !== 'other')
        if (withoutOther.includes(id)) {
          return withoutOther.filter((x) => x !== id)
        }
        return [...withoutOther, id]
      })
    },
    [multi],
  )

  const handleContinue = useCallback(() => {
    if (!canContinue) return
    const answer = buildCurrentAnswer()
    const nextCompleted = [...completed, answer]
    if (!isLast) {
      setCompleted(nextCompleted)
      setQuestionIndex((i) => Math.min(i + 1, total - 1))
      return
    }
    onSubmit(nextCompleted)
  }, [buildCurrentAnswer, canContinue, completed, isLast, onSubmit, total])

  const handleBack = useCallback(() => {
    if (rejectReasonStep) {
      setRejectReasonStep(false)
      return
    }
    if (questionIndex <= 0) return
    const prevIndex = questionIndex - 1
    const prevAnswers = completed.slice(0, -1)
    setCompleted(prevAnswers)
    setQuestionIndex(prevIndex)
    const restored = prevAnswers[prevIndex]
    if (restored) {
      setSelectedIds(restored.selectionIds)
      setOtherText(restored.otherText)
    }
  }, [completed, questionIndex, rejectReasonStep])

  useEscapeKey(onSkip, true)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Enter' && !e.shiftKey) {
        const tag = (e.target as HTMLElement)?.tagName
        if (tag === 'TEXTAREA') {
          if (planApproval && rejectReasonStep && rejectReason.trim()) {
            e.preventDefault()
            submitPlanApproval('b', rejectReason)
          }
          return
        }
        if (planApproval) return
        if (!canContinue) return
        e.preventDefault()
        handleContinue()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [canContinue, handleContinue, planApproval, rejectReason, rejectReasonStep, submitPlanApproval])

  const queuedPreview = pending.pendingMessage.trim()
  const continueLabel = isLast ? 'Continue' : 'Next'

  return (
    <>
      <div
        ref={rootRef}
        className="sherpa-clarify"
        role="region"
        aria-label="Sherpa clarification questions"
      >
        <header className="sherpa-clarify__header">
          <div className="sherpa-clarify__title-row">
            <span className="sherpa-clarify__title-icon" aria-hidden>
              <MessageCircle size={15} strokeWidth={1.75} />
            </span>
            <span className="sherpa-clarify__title">
              {planApproval ? 'Plan approval' : 'Questions'}
            </span>
          </div>
          {!planApproval ? (
            <div className="sherpa-clarify__pager">
              <button
                type="button"
                className="sherpa-clarify__pager-btn"
                disabled={questionIndex <= 0}
                aria-label="Previous question"
                onClick={handleBack}
              >
                <ChevronLeft size={14} />
              </button>
              <span>
                {questionIndex + 1} of {total}
              </span>
              <button
                type="button"
                className="sherpa-clarify__pager-btn"
                disabled={questionIndex >= total - 1}
                aria-label="Next question"
                onClick={() => canContinue && handleContinue()}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          ) : null}
        </header>

        <div className="sherpa-clarify__body">
          {planApproval && pending.planSteps && pending.planSteps.length > 0 ? (
            <div className="sherpa-clarify__plan">
              <div className="sherpa-clarify__plan-title">Plan</div>
              <ol className="sherpa-clarify__plan-steps">
                {pending.planSteps.map((step, i) => (
                  <li key={`${i}-${step.slice(0, 24)}`}>
                    <div className="sherpa-clarify__plan-step-md">
                      <MarkdownMessage content={step} />
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}

          {multi ? (
            <p className="sherpa-clarify__hint">Select one or more options, then continue.</p>
          ) : null}

          {planApproval && rejectReasonStep ? (
            <>
              <p className="sherpa-clarify__question">What should change in this plan?</p>
              <textarea
                className="sherpa-clarify__other-input"
                placeholder="Describe what to revise — data sources, columns, outputs, GitHub path…"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                autoFocus
              />
            </>
          ) : (
            <>
              <p className="sherpa-clarify__question">
                {!planApproval ? (
                  <span className="sherpa-clarify__question-num">{questionIndex + 1}.</span>
                ) : null}
                {plainQuestion(current.question)}
              </p>

              {!planApproval ? (
                <div
                  className="sherpa-clarify__options"
                  role={multi ? 'group' : 'radiogroup'}
                  aria-label={current.question}
                >
                  {current.options.map((opt, index) => {
                    const active = selectedIds.includes(opt.id)
                    const otherOpt = isOtherOption(opt)
                    const dimmed = otherOpt && !active && selectedIds.length > 0 && !otherSelected
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        role={multi ? 'checkbox' : 'radio'}
                        aria-checked={active}
                        className={[
                          'sherpa-clarify__option',
                          active ? 'sherpa-clarify__option--selected' : '',
                          dimmed ? 'sherpa-clarify__option--dimmed' : '',
                          multi ? 'sherpa-clarify__option--multi' : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                        onClick={() => handleOptionClick(opt)}
                      >
                        <span className="sherpa-clarify__badge" aria-hidden>
                          {multi && active ? (
                            <Check size={12} strokeWidth={2.5} />
                          ) : (
                            optionLetter(index, opt.id, current.kind)
                          )}
                        </span>
                        <span className="sherpa-clarify__option-text">
                          {optionDisplayText(opt)}
                        </span>
                      </button>
                    )
                  })}
                </div>
              ) : null}
            </>
          )}

          {otherSelected && !planApproval ? (
            <textarea
              className="sherpa-clarify__other-input"
              placeholder="Describe what you want Sherpa to do…"
              value={otherText}
              onChange={(e) => setOtherText(e.target.value)}
              autoFocus
            />
          ) : null}
        </div>

        <footer className="sherpa-clarify__footer">
          <button
            type="button"
            className="sherpa-clarify__skip"
            onClick={planApproval && rejectReasonStep ? handleBack : onSkip}
          >
            {planApproval && rejectReasonStep ? 'Back' : 'Skip'}
            {!(planApproval && rejectReasonStep) ? <span className="sherpa-clarify__kbd">Esc</span> : null}
          </button>
          {planApproval ? (
            rejectReasonStep ? (
              <button
                type="button"
                className="sherpa-clarify__continue"
                disabled={!rejectReason.trim()}
                onClick={() => submitPlanApproval('b', rejectReason)}
              >
                Submit revision
                <CornerDownLeft size={13} strokeWidth={2} aria-hidden />
              </button>
            ) : (
              <div className="sherpa-clarify__plan-actions">
                <button
                  type="button"
                  className="sherpa-clarify__plan-btn sherpa-clarify__plan-btn--reject"
                  onClick={() => setRejectReasonStep(true)}
                >
                  Reject
                </button>
                <button
                  type="button"
                  className="sherpa-clarify__plan-btn sherpa-clarify__plan-btn--approve"
                  onClick={() => submitPlanApproval('a')}
                >
                  Approve
                  <CornerDownLeft size={13} strokeWidth={2} aria-hidden />
                </button>
              </div>
            )
          ) : (
            <button
              type="button"
              className="sherpa-clarify__continue"
              disabled={!canContinue}
              onClick={handleContinue}
            >
              {continueLabel}
              <CornerDownLeft size={13} strokeWidth={2} aria-hidden />
            </button>
          )}
        </footer>
      </div>

      {queuedPreview && !planApproval ? (
        <div className="sherpa-clarify__queue">
          <button
            type="button"
            className="sherpa-clarify__queue-head"
            style={{
              border: 'none',
              background: 'transparent',
              padding: 0,
              cursor: 'pointer',
              width: '100%',
              textAlign: 'left',
            }}
            onClick={() => setQueueOpen((o) => !o)}
            aria-expanded={queueOpen}
          >
            <ChevronDown
              size={12}
              style={{
                transform: queueOpen ? 'rotate(0deg)' : 'rotate(-90deg)',
                transition: 'transform 160ms ease',
              }}
            />
            1 Queued
          </button>
          {queueOpen ? (
            <div className="sherpa-clarify__queue-item">
              <span className="sherpa-clarify__queue-dot" aria-hidden />
              <span className="sherpa-clarify__queue-text" title={queuedPreview}>
                {queuedPreview}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  )
}

export { formatAnswersForChat }
