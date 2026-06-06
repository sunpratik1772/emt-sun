/** Detect automate intents that need a schedule before sending to Sherpa. */

const SCHEDULE_CUES_RE =
  /\b(every\s+\d+|hourly|daily|weekday|weekly|cron|at\s+\d|\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm))\b/i

const AUTOMATE_SLASH_RE = /^\/(?:automate|automation)(?:\s+(.*))?$/i
const AUTOMATE_PLAIN_RE = /^(?:\/)?automate(?:\s+this)?(?:\s+workflow)?\s*$/i

export function messageHasScheduleCue(text: string): boolean {
  return SCHEDULE_CUES_RE.test(text)
}

export function needsAutomateSchedulePrompt(message: string): boolean {
  const trimmed = message.trim()
  if (!trimmed) return false

  const slash = trimmed.match(AUTOMATE_SLASH_RE)
  if (slash) {
    const body = (slash[1] ?? '').trim()
    if (!body) return true
    return !messageHasScheduleCue(body)
  }

  if (AUTOMATE_PLAIN_RE.test(trimmed)) return true

  if (/^(?:\/)?automate\b/i.test(trimmed) && !messageHasScheduleCue(trimmed)) {
    return true
  }

  return false
}

export function mergeAutomateWithSchedule(base: string, scheduleDetail: string): string {
  const detail = scheduleDetail.trim()
  const trimmed = base.trim()
  const slash = trimmed.match(AUTOMATE_SLASH_RE)
  if (slash) {
    const body = (slash[1] ?? '').trim()
    if (!body) return `/automate ${detail}`
    if (!messageHasScheduleCue(body)) return `/automate ${detail}`
    return `/automate ${body} (${detail})`
  }
  if (/^(?:\/)?automate\b/i.test(trimmed)) {
    return `/automate ${detail}`
  }
  return `/automate ${detail}`
}
