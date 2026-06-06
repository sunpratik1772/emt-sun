import {
  LayoutGrid,
  LayoutTemplate,
  Boxes,
  Database,
  UserRound,
  Settings,
} from '../../icons/arc'
import type {
  DashboardIntegration,
  DashboardNavItem,
  DashboardRunActivity,
  DashboardRunHealth,
  DashboardStat,
  DashboardWorkflow,
} from './types'
import { buildRunActivityCalendar } from './utils'

export const PREVIEW_STATS: DashboardStat[] = [
  { label: 'Workflows', value: '4', sub: '2 drafts ready to open.' },
  { label: 'Runs this month', value: '12', sub: 'Nice momentum — +2 vs last month.' },
  { label: 'Automations', value: '2', sub: '2 scheduled — running on autopilot.' },
]

export const PREVIEW_WORKFLOWS: DashboardWorkflow[] = [
  {
    id: 'leads-pipeline',
    name: 'Lead scoring pipeline',
    filename: 'leads_pipeline.json',
    kind: 'saved',
    nodeCount: 8,
    updatedLabel: '2h ago',
    nodeTypes: ['db_query', 'agent', 'jira_mcp'],
    lastRun: { status: 'success', at: '', label: 'Succeeded 2h ago' },
  },
  {
    id: 'daily-sync',
    name: 'Daily data sync',
    filename: 'daily_sync.json',
    kind: 'saved',
    nodeCount: 5,
    updatedLabel: '5h ago',
    nodeTypes: ['csv_extract', 'transform', 'output'],
    lastRun: { status: 'error', at: '', label: 'Failed 5h ago' },
  },
  {
    id: 'new-draft',
    name: 'Untitled workflow',
    filename: 'draft_01.json',
    kind: 'draft',
    nodeCount: 2,
    updatedLabel: '1d ago',
    nodeTypes: ['trigger', 'agent'],
    lastRun: undefined,
  },
]

export const PREVIEW_RUNS: DashboardRunActivity[] = [
  { id: '1', workflowName: 'Lead scoring pipeline', status: 'success', time: '2h ago' },
  { id: '2', workflowName: 'Daily data sync', status: 'error', time: '5h ago' },
  { id: '3', workflowName: 'Report generator', status: 'success', time: '1d ago' },
]

export const PREVIEW_RUN_HEALTH: DashboardRunHealth = {
  successRate: 0.92,
  runsThisMonth: 12,
  failedThisMonth: 1,
  engineOnline: true,
  dailyCounts: [1, 3, 2, 0, 4, 1, 2],
  calendar: buildRunActivityCalendar(
    [1, 3, 2, 0, 4, 1, 2].flatMap((count, daysAgo) => {
      const d = new Date()
      d.setHours(12, 0, 0, 0)
      d.setDate(d.getDate() - (6 - daysAgo))
      return Array.from({ length: count }, (_, i) => ({
        run_id: `preview-${daysAgo}-${i}`,
        started_at: d.toISOString(),
        status: 'success' as const,
      }))
    }),
  ),
}

export const PREVIEW_INTEGRATIONS: DashboardIntegration[] = [
  {
    id: 'datasets',
    label: 'Data connectors',
    detail: 'Demo datasets ready',
    status: 'connected',
  },
  {
    id: 'mcp-atlassian',
    label: 'Atlassian MCP',
    detail: 'Configure in Settings',
    status: 'partial',
  },
  {
    id: 'mcp-github',
    label: 'GitHub MCP',
    detail: 'Not configured',
    status: 'off',
  },
]

export const PREVIEW_NAV: DashboardNavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutGrid },
  { id: 'projects', label: 'Workflows', icon: Boxes },
  { id: 'templates', label: 'Templates', icon: LayoutTemplate },
  { id: 'data', label: 'Data Sources', icon: Database },
  { id: 'team', label: 'Team', icon: UserRound },
  { id: 'settings', label: 'Settings', icon: Settings },
]
