import { dayPeriod, greetingForHour } from './timeGreeting'

export const DASHBOARD_SUBLINE_FALLBACK = 'What do you want to get started with?'

/** Mirrors backend GREETING_INSPIRATION_EXAMPLES — workflow-focused, no node-type Q&A. */
export const DASHBOARD_SUBLINE_FALLBACKS: readonly string[] = [
  'What would you like to build today?',
  'How can I help you get started on a workflow?',
  'What would you like to run or automate today?',
  'Ready to dive in — what\'s the goal for this session?',
]

export function pickDashboardSublineFallback(): string {
  const index = Math.floor(Math.random() * DASHBOARD_SUBLINE_FALLBACKS.length)
  return DASHBOARD_SUBLINE_FALLBACKS[index] ?? DASHBOARD_SUBLINE_FALLBACK
}

export function firstNameFromDisplayName(name?: string | null): string {
  const trimmed = name?.trim()
  if (!trimmed) return 'there'
  return trimmed.split(/\s+/)[0] ?? 'there'
}

export function buildSherpaWelcome(name?: string | null): {
  greeting: string
  prompt: string
  inputPlaceholder: string
  period: 'morning' | 'afternoon' | 'evening'
  dateEyebrow: string
} {
  const first = firstNameFromDisplayName(name)
  const now = new Date()
  const hour = now.getHours()
  const period = dayPeriod(hour)
  const dateEyebrow = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  }).format(now)
  return {
    greeting: `${greetingForHour(hour)}, ${first}`,
    prompt: DASHBOARD_SUBLINE_FALLBACK,
    inputPlaceholder: 'Describe a workflow, ask a question, or request a fix…',
    period,
    dateEyebrow,
  }
}
