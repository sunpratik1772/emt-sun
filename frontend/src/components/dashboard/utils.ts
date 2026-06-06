import type { RunLogSummary } from '../../services/api'
import type { RunActivityCalendarData, RunCalendarCell, WorkflowRunStatus } from './types'
import { greetingForHour } from '../../lib/timeGreeting'

export { greetingForHour }

export function relativeTime(ms?: number): string {
  if (!ms) return 'Unknown'
  const diff = Date.now() - ms
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(ms).toLocaleDateString()
}

export function formatActivityTime(iso: string): string {
  const ms = Date.parse(iso)
  return relativeTime(Number.isFinite(ms) ? ms : undefined)
}

export function formatNodeType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function runStatusLabel(status: WorkflowRunStatus): string {
  if (status === 'success') return 'Last run succeeded'
  if (status === 'error') return 'Last run failed'
  if (status === 'running') return 'Running now'
  if (status === 'warning') return 'Last run completed with warnings'
  return 'Not run yet'
}

function isSameMonth(d: Date, ref: Date): boolean {
  return d.getMonth() === ref.getMonth() && d.getFullYear() === ref.getFullYear()
}

function isSameDay(d: Date, ref: Date): boolean {
  return (
    d.getFullYear() === ref.getFullYear() &&
    d.getMonth() === ref.getMonth() &&
    d.getDate() === ref.getDate()
  )
}

function dateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function countToLevel(count: number, maxCount: number): RunCalendarCell['level'] {
  if (count <= 0) return 0
  const ratio = count / maxCount
  if (ratio <= 0.25) return 1
  if (ratio <= 0.5) return 2
  if (ratio <= 0.75) return 3
  return 4
}

function computeStreaks(cells: RunCalendarCell[]): { streakDays: number; longestStreak: number } {
  let longest = 0
  let running = 0
  for (const cell of cells) {
    if (cell.count > 0) {
      running += 1
      longest = Math.max(longest, running)
    } else {
      running = 0
    }
  }

  let streakDays = 0
  for (let i = cells.length - 1; i >= 0; i -= 1) {
    if (cells[i].count > 0) streakDays += 1
    else break
  }

  return { streakDays, longestStreak: longest }
}

export function buildRunActivityCalendar(
  runLogs: RunLogSummary[],
  weekCount = 5,
): RunActivityCalendarData {
  const countsByDay = new Map<string, number>()
  for (const r of runLogs) {
    const t = Date.parse(r.started_at)
    if (!Number.isFinite(t)) continue
    const key = dateKey(new Date(t))
    countsByDay.set(key, (countsByDay.get(key) ?? 0) + 1)
  }

  const maxCount = Math.max(1, ...countsByDay.values())

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const end = new Date(today)
  const start = new Date(today)
  start.setDate(start.getDate() - weekCount * 7 + 1)
  start.setDate(start.getDate() - start.getDay())

  const cells: RunCalendarCell[] = []
  const cursor = new Date(start)
  while (cursor <= end) {
    const key = dateKey(cursor)
    const count = countsByDay.get(key) ?? 0
    cells.push({ date: key, count, level: countToLevel(count, maxCount) })
    cursor.setDate(cursor.getDate() + 1)
  }

  const { streakDays, longestStreak } = computeStreaks(cells)
  return { cells, streakDays, longestStreak }
}

export function buildRunHealth(runLogs: RunLogSummary[], engineOnline: boolean) {
  const now = new Date()
  const thisMonth = runLogs.filter((r) => {
    const t = Date.parse(r.started_at)
    return Number.isFinite(t) && isSameMonth(new Date(t), now)
  })
  const success = thisMonth.filter((r) => r.status === 'success' || r.status === 'warning').length
  const failed = thisMonth.filter((r) => r.status === 'error').length
  const total = thisMonth.length
  const successRate = total > 0 ? success / total : null

  const dailyCounts: number[] = []
  for (let i = 6; i >= 0; i -= 1) {
    const day = new Date(now)
    day.setHours(0, 0, 0, 0)
    day.setDate(day.getDate() - i)
    const count = runLogs.filter((r) => {
      const t = Date.parse(r.started_at)
      return Number.isFinite(t) && isSameDay(new Date(t), day)
    }).length
    dailyCounts.push(count)
  }

  return {
    successRate,
    runsThisMonth: total,
    failedThisMonth: failed,
    engineOnline,
    dailyCounts,
    calendar: buildRunActivityCalendar(runLogs),
  }
}

export function lastRunForWorkflow(
  filename: string,
  name: string,
  runLogs: RunLogSummary[],
): { status: WorkflowRunStatus; at: string; label: string } | undefined {
  const normalizedName = name.toLowerCase()
  const normalizedFile = filename.toLowerCase()
  const match = runLogs.find((r) => {
    const wf = (r.workflow ?? '').toLowerCase()
    if (!wf) return false
    return (
      wf === normalizedName ||
      wf === normalizedFile ||
      wf.includes(normalizedName) ||
      normalizedFile.includes(wf.replace(/\.json$/i, ''))
    )
  })
  if (!match) return undefined
  const status: WorkflowRunStatus =
    match.status === 'success' ||
    match.status === 'error' ||
    match.status === 'running' ||
    match.status === 'warning'
      ? match.status
      : null
  const label = `${runStatusLabel(status)} · ${formatActivityTime(match.started_at)}`
  return { status, at: match.started_at, label }
}

/** Last N calendar days of counts (oldest → newest). */
export function sparklineLastNDays(countForDay: (day: Date) => number, days = 7): number[] {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const out: number[] = []
  for (let i = days - 1; i >= 0; i -= 1) {
    const day = new Date(today)
    day.setDate(day.getDate() - i)
    out.push(countForDay(day))
  }
  return out
}

export function buildDashboardStatSparklines(
  runLogs: RunLogSummary[],
  saved: Array<{ modified_ms?: number }>,
  drafts: Array<{ modified_ms?: number }>,
  automationsActive: number,
): { runs: number[]; workflows: number[]; automations: number[] } {
  const library = [...saved, ...drafts]

  const runs = sparklineLastNDays((day) =>
    runLogs.filter((r) => {
      const t = Date.parse(r.started_at)
      return Number.isFinite(t) && isSameDay(new Date(t), day)
    }).length,
  )

  const workflows = sparklineLastNDays((day) => {
    const touched = library.filter((w) => {
      if (!w.modified_ms) return false
      return isSameDay(new Date(w.modified_ms), day)
    }).length
    return touched > 0 ? touched : library.length > 0 ? 1 : 0
  })

  const automations = sparklineLastNDays(() => automationsActive)

  return { runs, workflows, automations }
}
