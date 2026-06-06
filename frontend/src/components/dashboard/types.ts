import type { LucideIcon } from 'lucide-react'

export type WorkflowRunStatus = 'success' | 'error' | 'warning' | 'running' | null

export interface DashboardWorkflow {
  id: string
  name: string
  filename?: string
  kind: 'saved' | 'draft'
  nodeCount: number
  updatedLabel: string
  nodeTypes: string[]
  lastRun?: {
    status: WorkflowRunStatus
    at: string
    label: string
  }
  upvoteCount?: number
  downvoteCount?: number
}

export interface DashboardStat {
  label: string
  value: string
  sub: string
  sparkline?: number[]
}

export interface DashboardGetStartedStep {
  id: string
  label: string
  done: boolean
  onClick?: () => void
}

export interface DashboardRunActivity {
  id: string
  workflowName: string
  status: 'success' | 'error' | 'warning' | 'running'
  time: string
}

export interface RunCalendarCell {
  date: string
  count: number
  level: 0 | 1 | 2 | 3 | 4
}

export interface RunActivityCalendarData {
  cells: RunCalendarCell[]
  streakDays: number
  longestStreak: number
}

export interface DashboardRunHealth {
  successRate: number | null
  runsThisMonth: number
  failedThisMonth: number
  engineOnline: boolean
  dailyCounts: number[]
  calendar: RunActivityCalendarData
}

export interface DashboardNavItem {
  id: string
  label: string
  icon: LucideIcon
}

export interface DashboardIntegration {
  id: string
  label: string
  detail: string
  status: 'connected' | 'partial' | 'off'
}

export interface DashboardShellProps {
  variant?: 'full' | 'content'
  preview?: boolean
  userName?: string
  stats: DashboardStat[]
  workflows: DashboardWorkflow[]
  runHealth: DashboardRunHealth
  recentRuns?: DashboardRunActivity[]
  activeNavId?: string
  onNavClick?: (id: string) => void
  onNewWorkflow?: () => void
  onOpenWorkflow?: (workflow: DashboardWorkflow) => void
  onNewFromScratch?: () => void
  onNewFromTemplate?: () => void
  onViewAllRuns?: () => void
  onViewAllWorkflows?: () => void
  onSearchClick?: () => void
  onSherpaPrompt?: (message: string) => void
  onOpenSettings?: () => void
}
