import { useEffect, useMemo, useState } from 'react'
import StudioOverlay from '../StudioOverlay'
import { api } from '../../services/api'
import {
  ArcIcon, Zap, Loader2, Trash2, Play, Plus, Check, Clock, Sliders, Settings,
  RefreshCw, ChevronRight, ChevronDown, ExternalLink, Download, FileOutput,
  CheckCircle2, XCircle, Search, Activity, AlertTriangle, Workflow, X, PauseCircle, Pencil,
  CalendarClock, Pause,
} from '../../icons/arc'
import { useAuthStore } from '../../store/authStore'
import { toast } from '../../store/toastStore'
import { useWorkflowStore } from '../../store/workflowStore'
import { useStudioSectionStore } from '../../store/studioSectionStore'
import type { Automation, AutomationRun, RunLogSummary } from '../../services/api'
import {
  useAutomations,
  useAutomationRuns,
  useClearAutomationRuns,
  useCreateAutomation,
  useDeleteAutomation,
  useDeleteAutomationRun,
  useRunLogs,
  useTriggerAutomation,
  useUpdateAutomation,
  useWorkflowsList,
} from '../../hooks/useLibraryQueries'
import { explainCron, getNextCronRuns } from './cronUtils'
import { generateStepsForRun } from './runHistoryUtils'
import { buildRunLogFromAutomationRun } from '../../lib/runHistoryOutput'
import {
  KV,
  PanelEmpty,
  PanelError,
  PanelLoading,
  SectionLabel,
  Stat,
  StatusIcon,
  SearchInput,
  ListRow,
  formatDur,
  formatTime,
  thStyle,
  tdNameStyle,
  tdTypeStyle,
  tdDescStyle,
  StatusBadge,
  DSection,
  DCell,
} from './shared'

export function AutomationsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const currentUser = useAuthStore((s) => s.user)
  const defaultAuthor = currentUser?.name || 'John Doe'

  const { data: automations = [], isLoading: automationsLoading, isError: automationsError, error: automationsFetchError, refetch: refetchAutomations } = useAutomations(open)
  const { data: workflows = [], isError: workflowsError, error: workflowsFetchError } = useWorkflowsList(open)
  const focusAutomationId = useStudioSectionStore((s) => s.automationId)
  const openRunOutputModal = useStudioSectionStore((s) => s.openRunOutputModal)
  const [activeId, setActiveId] = useState<string | null>(null)
  const { data: runs = [], refetch: refetchRuns, isError: runsError, error: runsFetchError } = useAutomationRuns(activeId, open)
  const { data: allRunLogs = [] } = useRunLogs(open, 0)
  const createAutomation = useCreateAutomation()
  const updateAutomation = useUpdateAutomation()
  const deleteAutomation = useDeleteAutomation()
  const triggerAutomation = useTriggerAutomation()
  const deleteAutomationRun = useDeleteAutomationRun()
  const [tab, setTab] = useState<'settings' | 'history'>('settings')

  const [saving, setSaving] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'active' | 'paused'>('all')
  const [optimisticRuns, setOptimisticRuns] = useState<AutomationRun[] | null>(null)
  const displayRuns = optimisticRuns ?? runs
  const loading = automationsLoading || createAutomation.isPending || deleteAutomation.isPending

  // Form State
  const [name, setName] = useState('')
  const [workflowFilename, setWorkflowFilename] = useState('')
  const [scheduleType, setScheduleType] = useState<'cron' | 'interval'>('cron')
  const [cronExpression, setCronExpression] = useState('0 11 * * *')
  const [intervalMins, setIntervalMins] = useState(2)
  const [durationMins, setDurationMins] = useState(30)
  const [active, setActive] = useState(true)
  const [author, setAuthor] = useState(defaultAuthor)
  const [outputFilenamePattern, setOutputFilenamePattern] = useState('')
  const [confirmDialog, setConfirmDialog] = useState<{ title: string; message: string; onConfirm: () => void } | null>(null)

  // Pick focused or first automation when list loads
  useEffect(() => {
    if (!open) {
      setActiveId(null)
      setOptimisticRuns(null)
      return
    }
    if (focusAutomationId) {
      setActiveId(focusAutomationId)
      return
    }
  }, [open, focusAutomationId])

  // Sync Form State when Active Automation Changes
  const activeAuto = useMemo(() => automations.find((a) => a.id === activeId) ?? null, [automations, activeId])

  useEffect(() => {
    if (!activeAuto) return
    setName(activeAuto.name)
    setWorkflowFilename(activeAuto.workflow_filename)
    setScheduleType(activeAuto.schedule_type)
    setCronExpression(activeAuto.cron_expression || '0 11 * * *')
    setIntervalMins(activeAuto.interval_mins || 2)
    setDurationMins(activeAuto.duration_mins || 30)
    setActive(activeAuto.active)
    setAuthor(activeAuto.author || defaultAuthor)
    setOutputFilenamePattern(activeAuto.output_filename_pattern || '')
  }, [activeAuto, defaultAuthor])

  // Save changes
  const handleSaveChanges = async (overrides: Partial<Automation> = {}) => {
    if (!activeId) return
    setSaving(true)
    const payload = {
      name: overrides.name !== undefined ? overrides.name : name,
      workflow_filename: overrides.workflow_filename !== undefined ? overrides.workflow_filename : workflowFilename,
      schedule_type: overrides.schedule_type !== undefined ? overrides.schedule_type : scheduleType,
      cron_expression: overrides.cron_expression !== undefined ? overrides.cron_expression : cronExpression,
      interval_mins: overrides.interval_mins !== undefined ? overrides.interval_mins : Number(intervalMins),
      duration_mins: overrides.duration_mins !== undefined ? overrides.duration_mins : Number(durationMins),
      active: overrides.active !== undefined ? overrides.active : active,
      author: overrides.author !== undefined ? overrides.author : author,
      output_filename_pattern: overrides.output_filename_pattern !== undefined ? overrides.output_filename_pattern : outputFilenamePattern,
    }

    try {
      await updateAutomation.mutateAsync({ id: activeId, payload })
      toast.success('Automation settings saved')
    } catch (err) {
      toast.error(`Failed to save automation settings: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  // Handle active toggle directly
  const handleActiveToggle = (val: boolean) => {
    setActive(val)
    void handleSaveChanges({ active: val })
  }

  // Create new automation
  const handleCreateNew = async () => {
    const randomName = `Automated Pipeline ${automations.length + 1}`
    const defaultWf = workflows.length > 0 ? workflows[0].filename : 'studio_01_mcp_ticket_swarm.json'

    const payload = {
      name: randomName,
      workflow_filename: defaultWf,
      schedule_type: 'cron' as const,
      cron_expression: '*/5 * * * *',
      interval_mins: 5,
      duration_mins: 60,
      active: true,
      author: defaultAuthor,
    }

    try {
      const data = await createAutomation.mutateAsync(payload)
      setActiveId(data.id)
      setTab('settings')
      toast.success('Automation created')
    } catch (err) {
      toast.error(`Failed to create automation: ${(err as Error).message}`)
    }
  }

  // Delete automation
  const handleDelete = async () => {
    if (!activeId) return
    setConfirmDialog({
      title: 'Delete Automation',
      message: 'Are you sure you want to delete this automation configuration? This cannot be undone.',
      onConfirm: async () => {
        setConfirmDialog(null)
        try {
          await deleteAutomation.mutateAsync(activeId)
          setActiveId(null)
          toast.success('Automation deleted')
        } catch (err) {
          toast.error(`Failed to delete automation: ${(err as Error).message}`)
        }
      }
    })
  }

  // Force run now
  const handleTriggerNow = async () => {
    if (!activeId) return
    setTriggering(true)
    try {
      await triggerAutomation.mutateAsync(activeId)
      void refetchRuns()
      toast.success('Execution triggered')
    } catch (err) {
      toast.error(`Failed to trigger manual execution: ${(err as Error).message}`)
    } finally {
      setTriggering(false)
    }
  }

  const handleOpenRunOutput = (run: AutomationRun) => {
    if (!activeAuto) return
    const persisted = allRunLogs.find((r) => r.run_id === run.run_id) ?? null
    const summary = buildRunLogFromAutomationRun(run, activeAuto.workflow_filename, persisted)
    openRunOutputModal(summary)
  }

  // Filter automations
  const filteredAutos = useMemo(() => {
    const query = search.trim().toLowerCase()
    let list = automations
    if (filter === 'active') {
      list = list.filter((a) => a.active)
    } else if (filter === 'paused') {
      list = list.filter((a) => !a.active)
    }
    if (query) {
      list = list.filter((a) =>
        a.name.toLowerCase().includes(query) ||
        a.workflow_filename.toLowerCase().includes(query)
      )
    }
    return list
  }, [automations, search, filter])

  // General Stats calculation
  const stats = useMemo(() => {
    const total = automations.length
    const activeCount = automations.filter((a) => a.active).length
    const pausedCount = total - activeCount
    return {
      total,
      active: activeCount,
      paused: pausedCount,
    }
  }, [automations])

  return (
    <StudioOverlay
      open={open}
      onClose={onClose}
      eyebrow="Running on autopilot"
      title="Automations"
      subtitle="Control every scheduled workflow — pause, edit, run on demand, or inspect past runs."
      ariaLabel="Automations"
      bodyClass="ov__body--wide ov__body--mng"
      titleAfter={
        <button type="button" className="ov-bbtn ov-bbtn--primary" onClick={() => void handleCreateNew()}>
          <ArcIcon icon={Plus} size={14} strokeWidth={2.2} />
          New schedule
        </button>
      }
      footLeft={
        <button type="button" className="ov-bbtn" onClick={() => void refetchAutomations()}>
          <ArcIcon icon={RefreshCw} size={14} strokeWidth={2} className={loading ? 'animate-spin' : undefined} />
          Refresh
        </button>
      }
      footRight={
        <span className="ov__foot-meta">
          {automations.length} schedule{automations.length === 1 ? '' : 's'}
        </span>
      }
    >
      <div className="screen__inner h-full flex flex-col" style={{ minHeight: '100%' }}>
        {/* Stats summary strip */}
        <div className="mng-summary">
          <div className="mng-sum">
            <div className="mng-sum__val">{stats.total}</div>
            <div className="mng-sum__label">Schedules</div>
            <div className="mng-sum__sub">{stats.active} active · {stats.paused} paused</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val mng-sum__val--ok">{stats.active}</div>
            <div className="mng-sum__label">Active</div>
            <div className="mng-sum__sub">on autopilot</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val">24</div>
            <div className="mng-sum__label">Runs today</div>
            <div className="mng-sum__sub">across all schedules</div>
          </div>
          <div className="mng-sum">
            <div className="mng-sum__val mng-sum__val--err">1</div>
            <div className="mng-sum__label">Failures · 24h</div>
            <div className="mng-sum__sub">needs attention</div>
          </div>
        </div>

        {/* Toolbar with Search & filter tabs */}
        <div className="mng-toolbar" style={{ marginBottom: 20 }}>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search schedules…"
            icon={<Search size={13} />}
            style={{ width: 240 }}
          />

          <div className="mng-tabs">
            {(['all', 'active', 'paused'] as const).map((tabName) => (
              <button
                key={tabName}
                type="button"
                onClick={() => setFilter(tabName)}
                className={`mng-tab${filter === tabName ? ' mng-tab--on' : ''}`}
                style={{ textTransform: 'capitalize' }}
              >
                {tabName}
              </button>
            ))}
          </div>
        </div>

        {loading && automations.length === 0 && <PanelLoading />}
        {automationsError && (
          <PanelError
            message={(automationsFetchError as Error)?.message ?? 'Failed to load automations'}
            onRetry={() => void refetchAutomations()}
          />
        )}

        {!loading && !automationsError && filteredAutos.length === 0 && (
          <PanelEmpty icon={<ArcIcon icon={Zap} size={18} />}>No automations found.</PanelEmpty>
        )}

        {!loading && !automationsError && filteredAutos.length > 0 && (
          <div className="mng-list">
            {filteredAutos.map((auto) => {
              const nextRun = auto.schedule_type === 'cron' ? (
                (() => {
                  const runs = getNextCronRuns(auto.cron_expression || '0 11 * * *', 1)
                  if (runs.length > 0) {
                    const diffMs = runs[0].getTime() - Date.now()
                    const diffMins = Math.max(1, Math.round(diffMs / 60000))
                    if (diffMins < 60) return `in ${diffMins}m`
                    const diffHours = Math.round(diffMins / 60)
                    if (diffHours < 24) return `in ${diffHours}h`
                    const diffDays = Math.round(diffHours / 24)
                    return `in ${diffDays}d`
                  }
                  return '—'
                })()
              ) : `in ${auto.interval_mins || 30}m`

              const lastRun = auto.last_run_status
                ? `${auto.last_run_status === 'success' ? 'Succeeded' : 'Failed'} ${auto.last_run_ago || '5h ago'}`
                : 'Not run yet'

              return (
                <div
                  className={`mng-row${auto.id === activeId ? ' bg-color-mix' : ''}`}
                  key={auto.id}
                  onClick={() => {
                    setActiveId(auto.id)
                    setTab('history')
                  }}
                  style={auto.id === activeId ? { background: 'color-mix(in srgb, var(--bg-2) 65%, transparent)' } : undefined}
                >
                  <span
                    className="mng-row__ico"
                    style={{
                      background: 'color-mix(in srgb, var(--accent) 15%, transparent)',
                      color: 'var(--accent)',
                    }}
                  >
                    <ArcIcon icon={Clock} size={19} />
                  </span>
                  <div className="mng-row__main">
                    <div className="mng-row__name">
                      {auto.name}
                      <StatusBadge status={auto.active ? (auto.last_run_status || 'success') : 'paused'} />
                    </div>
                    <div className="mng-row__sub">
                      <ArcIcon icon={Workflow} size={13} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
                      <span style={{ marginRight: 8 }}>{auto.workflow_filename}</span>
                      <code style={{ marginRight: 6 }}>{auto.cron_expression || `${auto.interval_mins}m`}</code>
                      <span>{auto.schedule_type === 'cron' ? explainCron(auto.cron_expression) : `Every ${auto.interval_mins} minutes`}</span>
                    </div>
                  </div>
                  <div className="mng-row__meta">
                    <div className="mng-row__meta-1">{auto.active ? 'Next ' + nextRun : 'Paused'}</div>
                    <div className="mng-row__meta-2">{auto.active ? lastRun : 'Paused'}</div>
                  </div>
                  <div className="mng-row__actions" onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className={`sw-toggle${auto.active ? ' sw-toggle--on' : ''}`}
                      aria-pressed={auto.active}
                      title={auto.active ? 'Active' : 'Paused'}
                      onClick={() => {
                        setActiveId(auto.id)
                        setActive(!auto.active)
                        void handleSaveChanges({ active: !auto.active })
                      }}
                    >
                      <span className="sw-toggle__knob" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Floating Right Detail Panel */}
        {activeId !== null && activeAuto && (
          <>
            <div className="studio-detail-drawer-scrim" onClick={() => setActiveId(null)} />
            <aside className="studio-detail-drawer">
              <div className="drawer__head">
                <span
                  className="drawer__ico"
                  style={{
                    background: 'color-mix(in srgb, var(--accent) 15%, transparent)',
                    color: 'var(--accent)',
                  }}
                >
                  <ArcIcon icon={Clock} size={20} />
                </span>
                <div className="drawer__titlewrap">
                  <div className="drawer__eyebrow">Schedule</div>
                  <div className="drawer__title">{activeAuto.name}</div>
                </div>
                <button
                  type="button"
                  className="drawer__close"
                  onClick={() => setActiveId(null)}
                  aria-label="Close"
                >
                  <ArcIcon icon={X} size={15} />
                </button>
              </div>

              <div className="drawer__body">
                {/* Tabs settings vs history */}
                <div className="mng-toolbar" style={{ marginBottom: 16 }}>
                  <div className="mng-tabs">
                    <button
                      type="button"
                      onClick={() => setTab('settings')}
                      className={`mng-tab ${tab === 'settings' ? 'mng-tab--on' : ''}`}
                      style={{ fontSize: 11, height: 26, padding: '0 12px' }}
                    >
                      Settings
                    </button>
                    <button
                      type="button"
                      onClick={() => setTab('history')}
                      className={`mng-tab ${tab === 'history' ? 'mng-tab--on' : ''}`}
                      style={{ fontSize: 11, height: 26, padding: '0 12px' }}
                    >
                      Run History
                    </button>
                  </div>
                </div>

                {tab === 'settings' ? (
                  <div className="flex flex-col gap-4">
                    {/* General Settings */}
                    <div>
                      <SectionLabel>Automation Name</SectionLabel>
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="studio-input"
                      />
                    </div>

                    {/* Workflow File Selector */}
                    <div>
                      <SectionLabel>Associated Workflow</SectionLabel>
                      <select
                        value={workflowFilename}
                        onChange={(e) => setWorkflowFilename(e.target.value)}
                        className="studio-select"
                      >
                        {workflows.map((wf) => (
                          <option key={wf.filename} value={wf.filename}>
                            {wf.name} ({wf.filename})
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Output Filename Override */}
                    <div>
                      <SectionLabel>Output Filename Pattern</SectionLabel>
                      <input
                        type="text"
                        value={outputFilenamePattern}
                        onChange={(e) => setOutputFilenamePattern(e.target.value)}
                        placeholder="e.g. quarterly_report_{timestamp}.xlsx"
                        className="studio-input"
                      />
                    </div>

                    {/* Author / Owner */}
                    <div>
                      <SectionLabel>Author / Owner</SectionLabel>
                      <input
                        type="text"
                        value={author}
                        onChange={(e) => setAuthor(e.target.value)}
                        placeholder="e.g. John Doe"
                        className="studio-input"
                      />
                    </div>

                    {/* Schedule Type Selection */}
                    <div>
                      <SectionLabel>Trigger Schedule Mode</SectionLabel>
                      <div className="mng-tabs mt-1" style={{ display: 'inline-flex' }}>
                        <button
                          type="button"
                          onClick={() => setScheduleType('cron')}
                          className={`mng-tab ${scheduleType === 'cron' ? 'mng-tab--on' : ''}`}
                          style={{ fontSize: 11, height: 26, padding: '0 12px' }}
                        >
                          Cron Expression
                        </button>
                        <button
                          type="button"
                          onClick={() => setScheduleType('interval')}
                          className={`mng-tab ${scheduleType === 'interval' ? 'mng-tab--on' : ''}`}
                          style={{ fontSize: 11, height: 26, padding: '0 12px' }}
                        >
                          Interval & Duration
                        </button>
                      </div>
                    </div>

                    {/* Dynamic Fields */}
                    {scheduleType === 'cron' ? (
                      <div>
                        <SectionLabel>Cron Expression</SectionLabel>
                        <input
                          type="text"
                          value={cronExpression}
                          onChange={(e) => setCronExpression(e.target.value)}
                          placeholder="0 11 * * *"
                          className="studio-input"
                        />
                        <div style={{ marginTop: 10, padding: 10, borderRadius: 6, background: 'var(--bg-3)', border: '1px solid var(--border-soft)', fontSize: 11 }}>
                          <div style={{ fontWeight: 500, color: 'var(--text-1)', marginBottom: 4 }}>Schedule:</div>
                          <div style={{ color: 'var(--text-0)', fontFamily: 'monospace', fontSize: 10.5, marginBottom: 8 }}>{explainCron(cronExpression)}</div>
                          <div style={{ fontWeight: 500, color: 'var(--text-1)', marginBottom: 4 }}>Next 3 Scheduled Runs (UTC):</div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            {getNextCronRuns(cronExpression).map((runDate, idx) => (
                              <div key={idx} style={{ color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                <ArcIcon icon={Clock} size={9} />
                                <span>{runDate.toUTCString()}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <SectionLabel>Interval (mins)</SectionLabel>
                          <input
                            type="number"
                            value={intervalMins}
                            onChange={(e) => setIntervalMins(Number(e.target.value))}
                            className="studio-input"
                          />
                        </div>
                        <div>
                          <SectionLabel>Duration (mins)</SectionLabel>
                          <input
                            type="number"
                            value={durationMins}
                            onChange={(e) => setDurationMins(Number(e.target.value))}
                            className="studio-input"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {(() => {
                      const meta = AUTOMATIONS_MOCKUP_METADATA[activeAuto.name]
                      return (
                        <>
                          <DSection label="Schedule">
                            <div className="dgrid">
                              <DCell k="Workflow" v={activeAuto.workflow_filename} />
                              <DCell k="Cron" v={activeAuto.schedule_type === 'cron' ? activeAuto.cron_expression : `${activeAuto.interval_mins}m`} mono />
                              <DCell k="Frequency" v={activeAuto.schedule_type === 'cron' ? explainCron(activeAuto.cron_expression) : `Every ${activeAuto.interval_mins} minutes`} />
                              <DCell k="Timezone" v={meta?.tz || 'America/New_York'} />
                              <DCell k="Retries" v={meta?.retries ?? 2} />
                              <DCell k="Timeout" v={meta?.timeout || '10 min'} />
                            </div>
                          </DSection>

                          <DSection label="Next run">
                            <div className="dnext__row">
                              <ArcIcon icon={CalendarClock} size={16} />
                              <span className="dnext__when">
                                {activeAuto.active ? (meta?.nextAbs || (() => {
                                  const runs = getNextCronRuns(activeAuto.cron_expression || '0 11 * * *', 1)
                                  return runs.length > 0 ? runs[0].toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Tomorrow · 6:00 AM EST'
                                })()) : 'Paused'}
                              </span>
                              <span className="dnext__rel">
                                {activeAuto.active ? (meta?.next || (() => {
                                  const runs = getNextCronRuns(activeAuto.cron_expression || '0 11 * * *', 1)
                                  if (runs.length > 0) {
                                    const diffMs = runs[0].getTime() - Date.now()
                                    const diffMins = Math.max(1, Math.round(diffMs / 60000))
                                    if (diffMins < 60) return `in ${diffMins}m`
                                    const diffHours = Math.round(diffMins / 60)
                                    if (diffHours < 24) return `in ${diffHours}h`
                                    const diffDays = Math.round(diffHours / 24)
                                    return `in ${diffDays}d`
                                  }
                                  return '—'
                                })()) : '—'}
                              </span>
                            </div>
                          </DSection>

                          <DSection label="Recent runs">
                            <div>
                              {meta?.runs ? (
                                meta.runs.map((r, i) => (
                                  <div className="drun" key={i}>
                                    <StatusBadge status={r.status} />
                                    <span className="drun__when" style={{ marginLeft: 8 }}>
                                      {r.when}
                                    </span>
                                    <span className="drun__meta">
                                      {r.dur} · {r.rows} rows
                                    </span>
                                  </div>
                                ))
                              ) : displayRuns.length === 0 ? (
                                <div style={{ fontSize: 12, color: 'var(--text-3)', fontStyle: 'italic' }}>No runs recorded yet.</div>
                              ) : (
                                displayRuns.slice(0, 3).map((r, idx) => (
                                  <button
                                    type="button"
                                    className="drun drun--link"
                                    key={r.id || idx}
                                    onClick={() => handleOpenRunOutput(r)}
                                    title="View run output"
                                  >
                                    <StatusBadge status={r.status} />
                                    <span className="drun__when" style={{ marginLeft: 8 }}>
                                      {new Date(r.triggered_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                                    </span>
                                    <span className="drun__meta">
                                      {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—'}
                                    </span>
                                  </button>
                                ))
                              )}
                            </div>
                          </DSection>

                          <DSection label="Notifications">
                            <div className="dbody">
                              Notify <strong>{(meta?.notify || 'On failure').toLowerCase()}</strong> · owned by {meta?.owner || 'John Doe'}
                            </div>
                          </DSection>
                        </>
                      )
                    })()}
                  </div>
                )}
              </div>

              {tab === 'settings' ? (
                <div className="drawer__foot">
                  <button type="button" className="ov-bbtn ov-bbtn--primary" onClick={() => void handleSaveChanges()} disabled={saving}>
                    <ArcIcon icon={Check} size={14} strokeWidth={2.2} />
                    <span>{saving ? 'Saving...' : 'Save Settings'}</span>
                  </button>
                  <button type="button" className="ov-bbtn" onClick={() => setTab('history')}>Cancel</button>
                  <div className="drawer__foot-spacer" />
                  <button type="button" className="icon-btn" title="Delete Automation" onClick={handleDelete} style={{ color: 'var(--danger)' }}>
                    <ArcIcon icon={Trash2} size={14} />
                  </button>
                </div>
              ) : (
                <div className="drawer__foot">
                  <button type="button" className="ov-bbtn ov-bbtn--primary" onClick={() => void handleTriggerNow()} disabled={triggering}>
                    <ArcIcon icon={Play} size={14} strokeWidth={2.2} />
                    <span>{triggering ? 'Running…' : 'Run now'}</span>
                  </button>
                  <button type="button" className="ov-bbtn" onClick={() => setTab('settings')}>
                    <ArcIcon icon={Pencil} size={14} strokeWidth={2.2} />
                    <span>Edit</span>
                  </button>
                  <div className="drawer__foot-spacer" />
                  <button
                    type="button"
                    className="icon-btn"
                    title={active ? 'Pause' : 'Resume'}
                    onClick={() => handleActiveToggle(!active)}
                  >
                    <ArcIcon icon={active ? Pause : Play} size={14} />
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    title="Delete"
                    style={{ color: 'var(--danger)' }}
                    onClick={handleDelete}
                  >
                    <ArcIcon icon={Trash2} size={14} />
                  </button>
                </div>
              )}
            </aside>
          </>
        )}
      </div>

      {confirmDialog && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            backdropFilter: 'blur(3px)',
            borderRadius: 8,
          }}
        >
          <div
            style={{
              width: 320,
              padding: 16,
              background: 'var(--bg-1)',
              border: '1px solid var(--border-soft)',
              borderRadius: 8,
              boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-0)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <ArcIcon icon={AlertTriangle} size={14} style={{ color: 'var(--danger)' }} />
              {confirmDialog.title}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--text-2)', lineHeight: 1.4 }}>
              {confirmDialog.message}
            </div>
            <div style={{ display: 'flex', justifyContent: 'end', gap: 6, marginTop: 4 }}>
              <button
                onClick={() => setConfirmDialog(null)}
                style={{
                  height: 26,
                  padding: '0 10px',
                  borderRadius: 4,
                  background: 'transparent',
                  border: '1px solid var(--border-soft)',
                  color: 'var(--text-2)',
                  fontSize: 11,
                  cursor: 'pointer',
                }}
                className="lift"
              >
                Cancel
              </button>
              <button
                onClick={confirmDialog.onConfirm}
                style={{
                  height: 26,
                  padding: '0 10px',
                  borderRadius: 4,
                  background: 'var(--danger)',
                  border: 'none',
                  color: '#fff',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
                className="lift"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </StudioOverlay>
  )
}

function MetricCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div
      style={{
        padding: '10px 12px',
        borderRadius: 6,
        background: 'var(--bg-2)',
        border: '1px solid var(--border-soft)',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      <span style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </span>
      <span className="num" style={{ fontSize: 16, fontWeight: 600, color: color || 'var(--text-0)' }}>
        {value}
      </span>
    </div>
  )
}

const modePillStyle: React.CSSProperties = {
  fontSize: 11,
  padding: '4px 8px',
  borderRadius: 5,
  border: '1px solid var(--border-soft)',
  cursor: 'pointer',
  fontFamily: 'inherit',
}

const AUTOMATIONS_MOCKUP_METADATA: Record<string, {
  tz: string
  retries: number
  timeout: string
  notify: string
  owner: string
  next: string
  nextAbs: string
  runs: { when: string; dur: string; rows: number; status: 'success' | 'error' | 'warning' | 'running' }[]
}> = {
  'Morning data sync': {
    tz: 'America/New_York',
    retries: 2,
    timeout: '10 min',
    notify: 'On failure',
    owner: 'John Doe',
    next: 'in 19h',
    nextAbs: 'Tomorrow · 6:00 AM EST',
    runs: [
      { when: 'Today · 6:00 AM', status: 'success', dur: '1.4s', rows: 96 },
      { when: 'Yesterday · 6:00 AM', status: 'success', dur: '1.3s', rows: 94 },
      { when: 'Jun 2 · 6:00 AM', status: 'success', dur: '1.5s', rows: 102 },
    ]
  },
  'Quarterly business review': {
    tz: 'America/New_York',
    retries: 1,
    timeout: '30 min',
    notify: 'Always',
    owner: 'John Doe',
    next: 'in 12d',
    nextAbs: 'Jul 1 · 9:00 AM EST',
    runs: [
      { when: 'Apr 1 · 9:00 AM', status: 'success', dur: '8.7s', rows: 1204 },
      { when: 'Jan 1 · 9:00 AM', status: 'success', dur: '8.1s', rows: 1180 },
    ]
  },
  'Trade anomaly sweep': {
    tz: 'UTC',
    retries: 3,
    timeout: '5 min',
    notify: 'On failure',
    owner: 'Risk Team',
    next: '—',
    nextAbs: '—',
    runs: [
      { when: 'Jun 2 · 3:30 PM', status: 'success', dur: '5.4s', rows: 512 },
      { when: 'Jun 2 · 3:00 PM', status: 'success', dur: '5.1s', rows: 498 },
    ]
  },
  'Hourly lead refresh': {
    tz: 'America/New_York',
    retries: 2,
    timeout: '10 min',
    notify: 'On failure',
    owner: 'Growth Team',
    next: 'in 42m',
    nextAbs: 'Today · 2:00 PM EST',
    runs: [
      { when: 'Today · 1:00 PM', status: 'success', dur: '3.2s', rows: 248 },
      { when: 'Today · 12:00 PM', status: 'error', dur: '1.1s', rows: 0 },
      { when: 'Today · 11:00 AM', status: 'success', dur: '3.0s', rows: 240 },
    ]
  }
}
