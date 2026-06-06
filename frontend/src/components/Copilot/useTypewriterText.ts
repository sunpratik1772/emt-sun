import { useEffect, useRef, useState } from 'react'

export type TypewriterOptions = {
  /** Reveal one line at a time (thinking monologue) or char-by-char (reply). */
  mode?: 'char' | 'line'
  paceMs?: number
  /** Chars revealed per tick in char mode (default 2). */
  chunkSize?: number
  /** When target grows (streaming reply), continue typing without resetting. */
  catchUp?: boolean
  onComplete?: () => void
}

export type TypewriterResult = {
  text: string
  isTyping: boolean
}

/** Reveal text progressively — line-by-line for thinking, catch-up for streaming replies. */
export function useTypewriterText(
  fullText: string,
  active: boolean,
  options: TypewriterOptions = {},
): TypewriterResult {
  const { mode = 'char', catchUp = false, onComplete, chunkSize = 2 } = options
  const charPace = options.paceMs ?? 18
  const linePace = options.paceMs ?? 360
  const target = fullText ?? ''
  const lines = mode === 'line' ? target.split('\n') : []

  const [visibleLen, setVisibleLen] = useState(0)
  const [visibleLines, setVisibleLines] = useState(0)
  const completedRef = useRef(false)
  const prevTargetRef = useRef('')

  useEffect(() => {
    completedRef.current = false
  }, [active, mode])

  useEffect(() => {
    if (!target) {
      setVisibleLen(0)
      setVisibleLines(0)
      prevTargetRef.current = ''
      return
    }
    if (!active) {
      setVisibleLen(target.length)
      setVisibleLines(lines.length)
      return
    }

    const prev = prevTargetRef.current
    const isExtension = catchUp && prev && target.startsWith(prev)
    if (!isExtension) {
      setVisibleLen(0)
      setVisibleLines(0)
      completedRef.current = false
    } else if (lines.length > prev.split('\n').length) {
      completedRef.current = false
    }
    prevTargetRef.current = target
  }, [target, active, catchUp, lines.length])

  useEffect(() => {
    if (!active || !target) return undefined

    if (mode === 'line') {
      const timer = window.setInterval(() => {
        setVisibleLines((prev) => {
          const next = Math.min(lines.length, prev + 1)
          if (next >= lines.length && !completedRef.current) {
            completedRef.current = true
            onComplete?.()
          }
          return next
        })
      }, linePace)
      return () => window.clearInterval(timer)
    }

    const timer = window.setInterval(() => {
      setVisibleLen((prev) => {
        const next = Math.min(target.length, prev + Math.max(1, chunkSize))
        if (next >= target.length && !completedRef.current) {
          completedRef.current = true
          onComplete?.()
        }
        return next
      })
    }, charPace)
    return () => window.clearInterval(timer)
  }, [active, target, mode, linePace, charPace, chunkSize, lines.length, onComplete])

  if (!target) return { text: '', isTyping: false }
  if (!active) return { text: target, isTyping: false }

  if (mode === 'line') {
    const text = lines.slice(0, visibleLines).join(visibleLines > 0 ? '\n' : '')
    return { text, isTyping: visibleLines < lines.length }
  }

  const text = target.slice(0, visibleLen)
  return { text, isTyping: visibleLen < target.length }
}

/** @deprecated Use destructured `.text` from useTypewriterText return value. */
export function useTypewriterTextLegacy(fullText: string, active: boolean, paceMs = 14): string {
  return useTypewriterText(fullText, active, { mode: 'char', paceMs }).text
}

export function firstSentence(text: string): string {
  const t = (text || '').trim()
  if (!t) return ''
  const masked = t.replace(/\.(csv|xlsx|xls|json|txt|sql|parquet)\b/gi, '<<DOT>>$1')
  const match = masked.match(/^[^.!?]+[.!?]/)
  if (!match) {
    return t.length > 140 ? `${t.slice(0, 137).trim()}…` : t
  }
  return match[0].replace(/<<DOT>>([a-z0-9]+)/gi, '.$1').trim()
}

export function collapsedStepCaption(step: {
  text: string
  detail?: string
  outcome?: string
  kind?: string
  contextualPlan?: boolean
}): string {
  const body = (step.detail || step.outcome || '').trim()
  const title = (step.text || '').trim()
  if (step.contextualPlan && body) return firstSentence(body) || title
  if (!body || body.toLowerCase() === title.toLowerCase()) return title || 'Done'
  if (step.kind === 'parallel' && isGenericPlanningFluff(body)) return title
  const sentence = firstSentence(body)
  if (sentence.length < 16 && title) return title
  return sentence || title
}

export function isGenericPlanningFluff(text: string): boolean {
  const lower = (text || '').toLowerCase()
  if (text.includes('→') || lower.includes('your prompt') || lower.includes('your request')) {
    return false
  }
  return (
    lower.includes('key performance indicator') ||
    lower.includes('initial constraints') ||
    lower.includes('data integrity') ||
    lower.includes('character encoding') ||
    lower.includes('contract-backed') ||
    lower.includes('mandatory columns') ||
    lower.includes('overarching project') ||
    lower.includes('existing system limitations') ||
    lower.includes('pipeline should work') ||
    lower.includes('step pipeline should') ||
    /^user wants\b/i.test(text.trim()) ||
    /^-\s*access to the/i.test(text.trim())
  )
}
