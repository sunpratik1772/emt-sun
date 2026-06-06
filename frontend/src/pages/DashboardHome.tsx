import { useMemo, useEffect, useState } from 'react'
import { useDraftsList, useRunLogs, useWorkflowsList, useAutomations } from '../hooks/useLibraryQueries'
import { api } from '../services/api'
import type { RunLogSummary, StoredWorkflow } from '../services/api'
import { toast } from '../store/toastStore'
import { useStudioSectionStore } from '../store/studioSectionStore'
import { useWorkflowStore } from '../store/workflowStore'
import { useCommandPaletteStore } from '../store/commandPaletteStore'
import { launchSherpaPrompt } from '../lib/launchSherpaPrompt'
import DashboardShell from '../components/dashboard/DashboardShell'
import type {
  DashboardStat,
  DashboardWorkflow,
} from '../components/dashboard/types'
import {
  buildRunHealth,
  buildDashboardStatSparklines,
  lastRunForWorkflow,
  relativeTime,
} from '../components/dashboard/utils'

function workflowToCard(
  w: StoredWorkflow,
  kind: 'saved' | 'draft',
  runLogs: RunLogSummary[],
): DashboardWorkflow {
  const name = w.name || w.filename.replace(/\.json$/i, '')
  const lastRun = lastRunForWorkflow(w.filename, name, runLogs)
  return {
    id: w.filename,
    name,
    filename: w.filename,
    kind,
    nodeCount: w.node_count ?? 0,
    updatedLabel: relativeTime(w.modified_ms),
    nodeTypes: [],
    lastRun,
    upvoteCount: kind === 'saved' ? (w.upvote_count ?? 0) : undefined,
    downvoteCount: kind === 'saved' ? (w.downvote_count ?? 0) : undefined,
  }
}

export default function DashboardHome() {
  const setSection = useStudioSectionStore((s) => s.setSection)
  const loadWorkflowFromFile = useWorkflowStore((s) => s.loadWorkflowFromFile)
  const loadDraftFromFile = useWorkflowStore((s) => s.loadDraftFromFile)
  const newBlankWorkflow = useWorkflowStore((s) => s.newBlankWorkflow)
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const setCommandPaletteOpen = useCommandPaletteStore((s) => s.setOpen)
  const [engineOnline, setEngineOnline] = useState(true)

  const { data: saved = [] } = useWorkflowsList(true)
  const { data: drafts = [] } = useDraftsList(true)
  const { data: runLogs = [] } = useRunLogs(true, 8000)
  const { data: automations = [] } = useAutomations(true)

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const res = await fetch('/api/health', { credentials: 'include' })
        if (!cancelled) setEngineOnline(res.ok)
      } catch {
        if (!cancelled) setEngineOnline(false)
      }
    }
    void check()
    const id = window.setInterval(check, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  const workflows = useMemo(() => {
    const savedCards = saved.map((w) => workflowToCard(w, 'saved', runLogs))
    const draftCards = drafts.map((w) => workflowToCard(w, 'draft', runLogs))
    return [...savedCards, ...draftCards].sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'draft' ? 1 : -1
      return a.name.localeCompare(b.name)
    })
  }, [saved, drafts, runLogs])

  const runsThisMonth = useMemo(() => {
    const now = new Date()
    return runLogs.filter((r) => {
      const t = Date.parse(r.started_at)
      if (!Number.isFinite(t)) return false
      const d = new Date(t)
      return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()
    }).length
  }, [runLogs])

  const stats: DashboardStat[] = useMemo(() => {
    const prevMonth = runLogs.filter((r) => {
      const t = Date.parse(r.started_at)
      if (!Number.isFinite(t)) return false
      const d = new Date(t)
      const now = new Date()
      const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      return d.getMonth() === prev.getMonth() && d.getFullYear() === prev.getFullYear()
    }).length
    const delta = runsThisMonth - prevMonth
    const deltaLabel = delta >= 0 ? `+${delta} vs last month` : `${delta} vs last month`
    const activeAutomations = automations.filter((a) => a.active).length
    const totalAutomations = automations.length
    const sparklines = buildDashboardStatSparklines(
      runLogs,
      saved,
      drafts,
      activeAutomations,
    )

    return [
      {
        label: 'Workflows',
        value: String(saved.length),
        sub:
          drafts.length > 0
            ? `${drafts.length} draft${drafts.length === 1 ? '' : 's'}`
            : saved.length > 0
              ? 'In your library'
              : 'Create your first',
        sparkline: sparklines.workflows,
      },
      {
        label: 'Runs this month',
        value: String(runsThisMonth),
        sub: runsThisMonth === 0 ? 'Run a workflow in Studio' : deltaLabel,
        sparkline: sparklines.runs,
      },
      {
        label: 'Automations',
        value: String(activeAutomations),
        sub:
          totalAutomations === 0
            ? 'Schedule a workflow'
            : activeAutomations > 0
              ? `${activeAutomations} active`
              : `${totalAutomations} configured`,
        sparkline: sparklines.automations,
      },
    ]
  }, [saved.length, drafts.length, runsThisMonth, runLogs, automations])

  const runHealth = useMemo(
    () => buildRunHealth(runLogs, engineOnline),
    [runLogs, engineOnline],
  )

  async function openWorkflow(workflow: DashboardWorkflow) {
    if (!workflow.filename) {
      newBlankWorkflow()
      setSection(null)
      return
    }
    try {
      const dag =
        workflow.kind === 'draft'
          ? await api.getDraft(workflow.filename)
          : await api.getWorkflow(workflow.filename)
      if (workflow.kind === 'draft') loadDraftFromFile(workflow.filename, dag)
      else loadWorkflowFromFile(workflow.filename, dag)
      setSection(null)
    } catch (e) {
      toast.error(`Could not open workflow: ${(e as Error).message}`)
    }
  }

  function handleNav(id: string) {
    if (id === 'dashboard') return
    if (id === 'templates' || id === 'projects') {
      setDrawerOpen(true)
      return
    }
    const map: Record<string, Parameters<typeof setSection>[0]> = {
      data: 'data',
      settings: 'settings',
      team: 'settings',
    }
    const section = map[id]
    if (section) setSection(section)
  }

  function handleSherpaPrompt(message: string) {
    launchSherpaPrompt(message, true)
  }

  return (
    <DashboardShell
      variant="content"
      stats={stats}
      workflows={workflows}
      runHealth={runHealth}
      activeNavId="dashboard"
      onNavClick={handleNav}
      onNewWorkflow={() => {
        newBlankWorkflow()
        setSection(null)
      }}
      onOpenWorkflow={openWorkflow}
      onNewFromScratch={() => {
        newBlankWorkflow()
        setSection(null)
      }}
      onNewFromTemplate={() => setDrawerOpen(true)}
      onViewAllRuns={() => setSection('run-history')}
      onViewAllWorkflows={() => setDrawerOpen(true)}
      onSearchClick={() => setCommandPaletteOpen(true)}
      onSherpaPrompt={handleSherpaPrompt}
    />
  )
}
