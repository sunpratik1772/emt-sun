/**
 * Top action bar — layout aligned with dbSherpa Studio v5 (brand / breadcrumbs /
 * center tabs / Share · theme · profile + workflow tools).
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  ArcIcon,
  Upload,
  Download,
  ShieldCheck,
  Save,
  Play,
  Loader2,
  Trash2,
  AlertTriangle,
  ChevronDown,
  Pencil,
  LayoutGrid,
  Code2,
} from '../../icons/arc'
import { Square } from 'lucide-react'
import { finalizeStuckRunLog, flushRunEventQueue, useWorkflowStore } from '../../store/workflowStore'

import ThemeToggleButton from '../ThemeToggleButton'
import { toast } from '../../store/toastStore'
import Modal from '../Modal'
import { Button } from '../ui/Button'
import { api } from '../../services/api'
import { useWorkflowsList } from '../../hooks/useLibraryQueries'
import { queryKeys } from '../../hooks/queryKeys'
import {
  findWorkflowNameConflicts,
  type WorkflowNameConflict,
} from '../../lib/workflowNameConflict'
import { openOutputPanelSummary } from '../../lib/openOutputPanel'
import WorkflowNameConflictDialog from './WorkflowNameConflictDialog'
import {
  bindWorkflowRunAbort,
  clearWorkflowRunAbort,
  stopWorkflowRun,
} from '../../services/workflowRunService'
import type { Workflow } from '../../types'

const SAMPLE_PAYLOAD = {
  trader_id: 'T001',
  book: 'FX-SPOT',
  alert_date: '2024-01-15',
  currency_pair: 'EUR/USD',
  alert_id: 'ALT-001',
}

type WorkflowContextForm = {
  scenario: string
  alert_id: string
  participant_id: string
  trader_id: string
  trader_name: string
  keyword: string
  currency_pair: string
  date: string
  alert_date: string
  start_time: string
  end_time: string
}

const DEFAULT_CONTEXT: WorkflowContextForm = {
  scenario: 'fxfro',
  alert_id: 'ALERT-FR-001',
  participant_id: '',
  trader_id: '',
  trader_name: '',
  keyword: '',
  currency_pair: '',
  date: '',
  alert_date: '',
  start_time: '',
  end_time: '',
}

/** SQLite surveillance demo alerts — selecting one loads the full fxfro payload into context. */
export const FXFRO_TEST_ALERT_PRESETS: WorkflowContextForm[] = [
  {
    scenario: 'fxfro',
    alert_id: 'ALERT-FR-001',
    participant_id: 'P-T001',
    trader_id: 'T001',
    trader_name: 'Avery Shah',
    keyword: 'fixing',
    currency_pair: 'EUR/USD',
    date: '2024-01-01',
    alert_date: '2024-01-01',
    start_time: '2024-01-01T11:07:00',
    end_time: '2024-01-01T11:52:00',
  },
  {
    scenario: 'fxfro',
    alert_id: 'ALERT-FR-002',
    participant_id: 'P-T002',
    trader_id: 'T002',
    trader_name: 'Morgan Lee',
    keyword: 'client flow',
    currency_pair: 'GBP/USD',
    date: '2024-01-02',
    alert_date: '2024-01-02',
    start_time: '2024-01-02T14:14:00',
    end_time: '2024-01-02T14:59:00',
  },
  {
    scenario: 'fxfro',
    alert_id: 'ALERT-FR-003',
    participant_id: 'P-T003',
    trader_id: 'T003',
    trader_name: 'Riley Chen',
    keyword: 'large order',
    currency_pair: 'USD/JPY',
    date: '2024-01-03',
    alert_date: '2024-01-03',
    start_time: '2024-01-03T09:21:00',
    end_time: '2024-01-03T10:06:00',
  },
  {
    scenario: 'fxfro',
    alert_id: 'ALERT-FR-004',
    participant_id: 'P-T004',
    trader_id: 'T004',
    trader_name: 'Sam Patel',
    keyword: 'pre hedge',
    currency_pair: 'AUD/USD',
    date: '2024-01-04',
    alert_date: '2024-01-04',
    start_time: '2024-01-04T12:28:00',
    end_time: '2024-01-04T13:13:00',
  },
  {
    scenario: 'fxfro',
    alert_id: 'ALERT-FR-005',
    participant_id: 'P-T005',
    trader_id: 'T005',
    trader_name: 'Jordan Blake',
    keyword: 'risk transfer',
    currency_pair: 'USD/CHF',
    date: '2024-01-05',
    alert_date: '2024-01-05',
    start_time: '2024-01-05T15:35:00',
    end_time: '2024-01-05T16:20:00',
  },
]

function contextFromWorkflow(workflow: Workflow | null): WorkflowContextForm {
  const node = workflow?.nodes.find((n) => n.type === 'WORKFLOW_CONTEXT')
  const cfg = (node?.config ?? {}) as Partial<WorkflowContextForm>
  return { ...DEFAULT_CONTEXT, ...cfg }
}

function workflowWithContext(workflow: Workflow, context: WorkflowContextForm): Workflow {
  return {
    ...workflow,
    nodes: workflow.nodes.map((node) => (
      node.type === 'WORKFLOW_CONTEXT'
        ? { ...node, config: { ...node.config, ...context } }
        : node
    )),
  }
}

function slugify(name: string | undefined | null): string {
  const s = (name || 'workflow').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  return s || 'workflow'
}

function filenameStem(filename: string | null | undefined): string {
  if (!filename) return ''
  return filename.replace(/\.(yaml|yml|json)$/i, '').trim()
}

function TopbarStudio({ headless = false }: { headless?: boolean }) {
  const workflow = useWorkflowStore((s) => s.workflow)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const setRightPanelMode = useWorkflowStore((s) => s.setRightPanelMode)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const setRunning = useWorkflowStore((s) => s.setRunning)
  const setRunError = useWorkflowStore((s) => s.setRunError)
  const resetRun = useWorkflowStore((s) => s.resetRun)
  const applyRunEvent = useWorkflowStore((s) => s.applyRunEvent)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const setValidationIssues = useWorkflowStore((s) => s.setValidationIssues)
  const markSaved = useWorkflowStore((s) => s.markSaved)
  const setWorkflow = useWorkflowStore((s) => s.setWorkflow)
  const newBlankWorkflow = useWorkflowStore((s) => s.newBlankWorkflow)
  const runLog = useWorkflowStore((s) => s.runLog)
  const runResult = useWorkflowStore((s) => s.runResult)
  const runError = useWorkflowStore((s) => s.runError)
  const workspaceView = useWorkflowStore((s) => s.workspaceView)
  const setWorkspaceView = useWorkflowStore((s) => s.setWorkspaceView)
  const templatesOpen = useWorkflowStore((s) => s.workflowDrawerOpen)
  const lastSavedSignature = useWorkflowStore((s) => s.lastSavedSignature)
  const isDirty = useMemo(() => {
    if (!workflow) return false
    if (!lastSavedSignature) {
      return workflow.nodes.length > 0
    }
    return lastSavedSignature !== JSON.stringify(workflow)
  }, [workflow, lastSavedSignature])

  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validatedSignature, setValidatedSignature] = useState<string | null>(null)
  const [lastValidationValid, setLastValidationValid] = useState<boolean | null>(null)
  const [contextModalOpen, setContextModalOpen] = useState(false)
  const [contextForm, setContextForm] = useState<WorkflowContextForm>(DEFAULT_CONTEXT)
  const [saveAsDialogOpen, setSaveAsDialogOpen] = useState(false)
  const [saveAsName, setSaveAsName] = useState('')
  const [newWorkflowDialogOpen, setNewWorkflowDialogOpen] = useState(false)
  const [pendingAfterSave, setPendingAfterSave] = useState<'new' | null>(null)
  const [runPromptOpen, setRunPromptOpen] = useState(false)
  const [pendingRunAfterSave, setPendingRunAfterSave] = useState(false)
  const [nameConflictOpen, setNameConflictOpen] = useState(false)
  const [nameConflicts, setNameConflicts] = useState<WorkflowNameConflict[]>([])
  const [deleting, setDeleting] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [pendingSave, setPendingSave] = useState<{
    targetFilename: string
    updated: Workflow
    deleteDraftFilename?: string | null
  } | null>(null)
  const importInputRef = useRef<HTMLInputElement | null>(null)
  const handleCreateNewWorkflowRef = useRef<() => void>(() => {})
  const qc = useQueryClient()
  const { data: savedWorkflows = [], refetch: refetchWorkflows } = useWorkflowsList(true)

  const nodeCount = workflow?.nodes.length ?? 0
  const edgeCount = workflow?.edges.length ?? 0
  const displayWorkflowName = (workflow?.name || '').trim() || filenameStem(sourceFilename) || 'Untitled workflow'
  const title = templatesOpen ? 'Templates' : displayWorkflowName
  const workflowSignature = useMemo(() => (workflow ? JSON.stringify(workflow) : null), [workflow])
  const deleteConfirmMessage = useMemo(() => {
    const label = displayWorkflowName
    if (sourceFilename && sourceKind === 'saved') {
      return `Delete "${label}"? This removes it from your library and cannot be undone.`
    }
    if (sourceFilename && sourceKind === 'draft') {
      return `Delete draft "${sourceFilename}"? This cannot be undone.`
    }
    return `Delete "${label}" from the canvas? Unsaved changes will be lost.`
  }, [displayWorkflowName, sourceFilename, sourceKind])

  async function proceedWithRun(w: Workflow = workflow!) {
    if (!w) return
    if (w.nodes.some((n) => n.type === 'WORKFLOW_CONTEXT')) {
      setContextForm(contextFromWorkflow(w))
      setContextModalOpen(true)
      return
    }
    await runWorkflowWithContext(w, SAMPLE_PAYLOAD)
  }

  async function handleRun() {
    if (!workflow) return
    if (isDirty) {
      setRunPromptOpen(true)
      return
    }
    await proceedWithRun()
  }

  async function handleSaveAndRun() {
    if (!workflow) return
    setRunPromptOpen(false)
    if (sourceFilename) {
      const ok = await requestSave(sourceFilename, workflow, { deleteDraftFilename: null })
      if (ok) await proceedWithRun(workflow)
    } else {
      setPendingRunAfterSave(true)
      openSaveAsDialog()
    }
  }

  function handleStopRun() {
    stopWorkflowRun()
    setRunning(false)
    finalizeStuckRunLog()
    void flushRunEventQueue()
  }

  async function runWorkflowWithContext(dag: Workflow, alertPayload: Record<string, string>) {
    const runAbort = new AbortController()
    bindWorkflowRunAbort(runAbort)
    setRunning(true)
    resetRun()
    setRunError(null)
    try {
      await api.runWorkflowStream(
        dag,
        alertPayload,
        (ev) => applyRunEvent(ev),
        runAbort.signal,
      )
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        setRunError((e as Error).message)
      }
    } finally {
      clearWorkflowRunAbort()
      finalizeStuckRunLog()
      setRunning(false)
      await flushRunEventQueue()
    }
  }

  async function submitContextRun() {
    if (!workflow) return
    setContextModalOpen(false)
    await runWorkflowWithContext(workflowWithContext(workflow, contextForm), {})
  }

  function openSaveAsDialog(afterSave: 'new' | null = null) {
    if (!workflow) return
    const suggested = sourceKind === 'saved' ? workflow.name : workflow.name || 'New workflow'
    setSaveAsName(suggested)
    setPendingAfterSave(afterSave)
    setSaveAsDialogOpen(true)
  }

  async function finishPendingAfterSave(updated: Workflow) {
    if (pendingRunAfterSave) {
      setPendingRunAfterSave(false)
      await proceedWithRun(updated)
    }
    if (pendingAfterSave === 'new') {
      newBlankWorkflow()
      setPendingAfterSave(null)
    }
  }

  async function executeSave(
    targetFilename: string,
    updated: Workflow,
    opts: { replace: boolean; deleteDraftFilename?: string | null },
  ) {
    await api.saveWorkflow(targetFilename, updated, { replace: opts.replace })
    if (opts.deleteDraftFilename) {
      await api.deleteDraft(opts.deleteDraftFilename).catch(() => void 0)
    }
    useWorkflowStore.setState({ workflow: updated })
    markSaved(targetFilename)
    openOutputPanelSummary('save')
    void qc.invalidateQueries({ queryKey: queryKeys.workflows })
    void qc.invalidateQueries({ queryKey: queryKeys.drafts })
  }

  /** Returns true when save completed; false when blocked on name conflict UI. */
  async function requestSave(
    targetFilename: string,
    updated: Workflow,
    opts: { replace?: boolean; deleteDraftFilename?: string | null },
  ): Promise<boolean> {
    const { data: freshList } = await refetchWorkflows()
    const catalog = freshList ?? savedWorkflows
    const conflicts = findWorkflowNameConflicts(
      catalog,
      updated.name || '',
      targetFilename,
    )
    if (conflicts.length > 0 && !opts.replace) {
      setPendingSave({
        targetFilename,
        updated,
        deleteDraftFilename: opts.deleteDraftFilename ?? null,
      })
      setNameConflicts(conflicts)
      setNameConflictOpen(true)
      return false
    }

    setSaving(true)
    try {
      await executeSave(targetFilename, updated, {
        replace: Boolean(opts.replace) || conflicts.length > 0,
        deleteDraftFilename: opts.deleteDraftFilename ?? null,
      })
      setSaveAsDialogOpen(false)
      setNameConflictOpen(false)
      setPendingSave(null)
      toast.success(`Saved as ${targetFilename}`)
      await finishPendingAfterSave(updated)
      return true
    } catch (err) {
      const msg = (err as Error).message
      if (msg.includes('workflow_name_conflict') || msg.includes('already exists')) {
        toast.error('That workflow name is already saved. Choose a different name or replace the existing copy.')
      } else {
        toast.error(`Could not save workflow: ${msg}`)
      }
      return false
    } finally {
      setSaving(false)
    }
  }

  async function commitSaveAs(nameRaw: string) {
    if (!workflow) return
    const name = nameRaw.trim()
    if (!name) return
    const targetFilename =
      sourceKind === 'saved' && name === workflow.name
        ? (sourceFilename ?? `${slugify(name)}.yaml`)
        : `${slugify(name)}.yaml`
    const updated = { ...workflow, name }
    const deleteDraftFilename =
      sourceKind === 'draft' && sourceFilename ? sourceFilename : null
    await requestSave(targetFilename, updated, { deleteDraftFilename })
  }

  function handleNameConflictCancel() {
    setNameConflictOpen(false)
    setPendingSave(null)
    setSaveAsDialogOpen(true)
  }

  async function handleNameConflictReplace() {
    if (!pendingSave) return
    setSaving(true)
    try {
      await executeSave(pendingSave.targetFilename, pendingSave.updated, {
        replace: true,
        deleteDraftFilename: pendingSave.deleteDraftFilename ?? null,
      })
      setNameConflictOpen(false)
      setPendingSave(null)
      setSaveAsDialogOpen(false)
      toast.success(`Replaced and saved as ${pendingSave.targetFilename}`)
      await finishPendingAfterSave(pendingSave.updated)
    } catch (err) {
      toast.error(`Could not replace workflow: ${(err as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  function handleCreateNewWorkflow() {
    if (!workflow) {
      newBlankWorkflow()
      return
    }
    setNewWorkflowDialogOpen(true)
  }

  handleCreateNewWorkflowRef.current = handleCreateNewWorkflow

  function handleDeleteWorkflow() {
    if (!workflow) return
    if (isRunning) {
      toast.warning('Stop the workflow run before deleting.')
      return
    }
    setDeleteDialogOpen(true)
  }

  async function confirmDeleteWorkflow() {
    if (!workflow) return
    setDeleting(true)
    try {
      if (sourceFilename && sourceKind === 'saved') {
        await api.deleteWorkflow(sourceFilename)
        toast.success('Workflow deleted')
      } else if (sourceFilename && sourceKind === 'draft') {
        await api.deleteDraft(sourceFilename)
        toast.success('Draft deleted')
      }
      newBlankWorkflow()
      resetRun()
      setDeleteDialogOpen(false)
      void qc.invalidateQueries({ queryKey: queryKeys.workflows })
      void qc.invalidateQueries({ queryKey: queryKeys.drafts })
      void qc.invalidateQueries({ queryKey: queryKeys.workflowCatalog })
    } catch (err) {
      toast.error(`Delete failed: ${(err as Error).message}`)
    } finally {
      setDeleting(false)
    }
  }

  const handleRunRef = useRef(handleRun)
  const openSaveAsDialogRef = useRef(openSaveAsDialog)
  const handleExportRef = useRef(handleExport)
  const handleDeleteWorkflowRef = useRef(handleDeleteWorkflow)

  useEffect(() => {
    handleRunRef.current = handleRun
    openSaveAsDialogRef.current = openSaveAsDialog
    handleExportRef.current = handleExport
    handleDeleteWorkflowRef.current = handleDeleteWorkflow
  })

  useEffect(() => {
    const onNew = () => handleCreateNewWorkflowRef.current()
    const onSave = () => openSaveAsDialogRef.current()
    const onRun = () => void handleRunRef.current()
    const onStop = () => handleStopRun()
    const onImport = () => importInputRef.current?.click()
    const onExport = () => void handleExportRef.current()
    const onDelete = () => void handleDeleteWorkflowRef.current()

    window.addEventListener('sheep:request-new-workflow', onNew)
    window.addEventListener('sheep:request-save-workflow', onSave)
    window.addEventListener('sheep:request-run-workflow', onRun)
    window.addEventListener('sheep:request-stop-workflow', onStop)
    window.addEventListener('sheep:request-import-workflow', onImport)
    window.addEventListener('sheep:request-export-workflow', onExport)
    window.addEventListener('sheep:request-delete-workflow', onDelete)

    return () => {
      window.removeEventListener('sheep:request-new-workflow', onNew)
      window.removeEventListener('sheep:request-save-workflow', onSave)
      window.removeEventListener('sheep:request-run-workflow', onRun)
      window.removeEventListener('sheep:request-stop-workflow', onStop)
      window.removeEventListener('sheep:request-import-workflow', onImport)
      window.removeEventListener('sheep:request-export-workflow', onExport)
      window.removeEventListener('sheep:request-delete-workflow', onDelete)
    }
  }, [])

  async function handleExport() {
    if (!workflow) return
    setExporting(true)
    try {
      const { content } = await api.workflowToYaml(workflow)
      const blob = new Blob([content], { type: 'application/x-yaml' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${slugify(workflow.name)}.yaml`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Workflow exported')
    } catch (err) {
      toast.error(`Export failed: ${(err as Error).message}`)
    } finally {
      setExporting(false)
    }
  }

  async function handleImportFile(file: File) {
    const text = await file.text()
    const lower = file.name.toLowerCase()
    try {
      const imported =
        lower.endsWith('.json') ? JSON.parse(text) : (await api.workflowFromYaml(text)).workflow
      setWorkflow(imported)
      resetRun()
      toast.success('Workflow imported')
    } catch (e) {
      toast.error(`Could not import workflow: ${(e as Error).message}`)
    }
  }

  async function handleValidate() {
    if (!workflow || !workflowSignature) return
    setValidating(true)
    try {
      const result = await api.validateWorkflow(workflow)
      setValidationIssues(result.errors.length ? result.errors : null)
      useWorkflowStore.setState({
        runWarnings: result.warnings.length ? result.warnings : null,
        runError: result.valid ? null : result.summary,
      })
      setValidatedSignature(workflowSignature)
      setLastValidationValid(result.valid)
      if (!result.valid) setRightPanelMode('runlog')
    } catch (e) {
      setRunError((e as Error).message)
      setLastValidationValid(false)
      setRightPanelMode('runlog')
    } finally {
      setValidating(false)
    }
  }

  const isCurrentValidation = validatedSignature === workflowSignature
  const validateBadge = validationIssues && validationIssues.length > 0
  const validationClean = Boolean(workflow && isCurrentValidation && lastValidationValid)
  const validationTitle = !workflow
    ? 'Load or generate a workflow before validating'
    : validating
      ? 'Validating workflow...'
      : validationClean
        ? 'Workflow validated'
        : validateBadge && isCurrentValidation
          ? `${validationIssues!.length} validation issue(s)`
          : 'Validate workflow'

  const borderHi = 'var(--border-strong)'

  return (
    <>
      <input
        ref={importInputRef}
        type="file"
        accept=".yaml,.yml,.json,application/x-yaml,application/json"
        style={{ display: 'none' }}
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) void handleImportFile(file)
        }}
      />

      {!headless ? (
    <div
      className="panel-glass flex items-center shrink-0 relative z-20"
      style={{
        height: 48,
        padding: '0 14px',
        gap: 8,
        borderBottom: '1px solid var(--border)',
      }}
    >
      {/* Left — View / Workflow name + rename action */}
      <div className="flex items-center shrink min-w-0 flex-1" style={{ gap: 6, maxWidth: 'calc(100vw - 300px)' }}>
        {!templatesOpen && <EnvironmentDropdown />}
        {!templatesOpen && (
          <span className="font-mono" style={{ color: 'var(--text-3)', fontSize: 11, margin: '0 1px' }} aria-hidden>
            /
          </span>
        )}
        <div className="flex items-center min-w-0" style={{ gap: 6, flex: '0 1 auto' }}>
          <span
            className="font-mono"
            style={{
              color: 'var(--text-1)',
              fontSize: 12.5,
              lineHeight: 1.25,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: 'block',
              flex: '0 1 auto',
              minWidth: 0,
              maxWidth: 'clamp(120px, calc(100vw - 560px), 360px)',
            }}
          >
            {title}
          </span>
          {!templatesOpen && isDirty && (
            <span
              title="Unsaved changes"
              aria-label="Unsaved changes"
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: 'var(--warning)',
                flexShrink: 0,
                boxShadow: '0 0 0 2px color-mix(in srgb, var(--warning) 25%, transparent)',
              }}
            />
          )}
          {!templatesOpen && (
            <IconGhost title="Rename and Save As" onClick={() => openSaveAsDialog()}>
              <ArcIcon icon={Pencil} size={11.5} />
            </IconGhost>
          )}
        </div>
      </div>

      <div className="flex-1 min-w-[12px]" />

      {/* Center — studio tabs (now in LeftNav, removed) */}

      <div className="flex-1 min-w-[12px]" />

      {/* Right — icon-only actions */}
      <div className="flex items-center shrink-0" style={{ gap: 4 }}>
        <span className="font-mono whitespace-nowrap hidden xl:inline" style={{ color: 'var(--text-3)', fontSize: 10.5, letterSpacing: '0.02em', marginRight: 6 }}>
          {nodeCount}n · {edgeCount}e
        </span>
        <span className="w-px h-[18px] shrink-0 hidden sm:block" style={{ background: borderHi, marginRight: 2 }} />

        {!templatesOpen && workflow ? (
          <>
            <IconAction
              title="Import workflow"
              onClick={() => importInputRef.current?.click()}
            >
              <ArcIcon icon={Upload} size={14} />
            </IconAction>
            <IconAction
              title="Export workflow"
              onClick={() => void handleExport()}
              disabled={exporting}
            >
              {exporting ? (
                <ArcIcon icon={Loader2} size={14} className="animate-spin" />
              ) : (
                <ArcIcon icon={Download} size={14} />
              )}
            </IconAction>
            <IconAction
              title="Delete workflow"
              onClick={() => void handleDeleteWorkflow()}
              disabled={deleting}
            >
              {deleting ? (
                <ArcIcon icon={Loader2} size={14} className="animate-spin" />
              ) : (
                <ArcIcon icon={Trash2} size={14} />
              )}
            </IconAction>
            <IconAction
              title="Save workflow"
              onClick={() => openSaveAsDialog()}
              disabled={saving}
            >
              {saving ? (
                <ArcIcon icon={Loader2} size={14} className="animate-spin" />
              ) : (
                <ArcIcon icon={Save} size={14} />
              )}
            </IconAction>
            <Button
              variant={isRunning ? 'stop' : 'primary'}
              className="btn--icon"
              onClick={() => (isRunning ? handleStopRun() : void handleRun())}
              data-testid="run-workflow-btn"
              title={isRunning ? 'Stop workflow run' : 'Run workflow'}
              aria-label={isRunning ? 'Stop workflow run' : 'Run workflow'}
              lift={false}
              style={{ width: 28, height: 28, borderRadius: 6 }}
            >
              {isRunning ? (
                <Square size={11} strokeWidth={3.2} />
              ) : (
                <ArcIcon icon={Play} size={13} />
              )}
            </Button>
            <span className="w-px h-[18px] shrink-0" style={{ background: borderHi, margin: '0 2px' }} />
          </>
        ) : null}

        <StatusIconButton
          onClick={() => {
            void handleValidate()
          }}
          disabled={!workflow || validating}
          title={validationTitle}
          status={validationClean ? 'ok' : validateBadge && isCurrentValidation ? 'error' : 'idle'}
          badge={validateBadge && isCurrentValidation ? validationIssues!.length : undefined}
        >
          {validating ? <ArcIcon icon={Loader2} size={14} className="animate-spin" /> : <ArcIcon icon={ShieldCheck} size={14} />}
        </StatusIconButton>

        <span className="w-px h-[18px] shrink-0" style={{ background: borderHi, marginLeft: 2, marginRight: 2 }} />

        <ThemeToggleButton />
      </div>
    </div>
      ) : null}

      {contextModalOpen && workflow && (
        <WorkflowContextRunModal
          value={contextForm}
          running={isRunning}
          onChange={(patch) => setContextForm((prev) => ({ ...prev, ...patch }))}
          onApplyFullContext={(full) => {
            setContextForm(full)
            setWorkflow(workflowWithContext(workflow, full))
          }}
          onCancel={() => setContextModalOpen(false)}
          onRun={() => {
            void submitContextRun()
          }}
        />
      )}

      {saveAsDialogOpen && workflow && !nameConflictOpen && (
        <SaveAsDialog
          value={saveAsName}
          saving={saving}
          onChange={setSaveAsName}
          onCancel={() => setSaveAsDialogOpen(false)}
          onSave={() => {
            void commitSaveAs(saveAsName)
          }}
        />
      )}

      {nameConflictOpen && pendingSave && (
        <WorkflowNameConflictDialog
          displayName={pendingSave.updated.name || saveAsName}
          targetFilename={pendingSave.targetFilename}
          conflicts={nameConflicts}
          saving={saving}
          onCancel={handleNameConflictCancel}
          onReplace={() => {
            void handleNameConflictReplace()
          }}
        />
      )}

      {newWorkflowDialogOpen && (
        <NewWorkflowDialog
          onCancel={() => setNewWorkflowDialogOpen(false)}
          onExitWithoutSaving={() => {
            setNewWorkflowDialogOpen(false)
            newBlankWorkflow()
          }}
          onSaveAndNew={() => {
            setNewWorkflowDialogOpen(false)
            openSaveAsDialog('new')
          }}
        />
      )}

      {runPromptOpen && (
        <SaveBeforeRunDialog
          onCancel={() => setRunPromptOpen(false)}
          onSaveAndRun={() => {
            void handleSaveAndRun()
          }}
          saving={saving}
        />
      )}

      {deleteDialogOpen && workflow && (
        <DeleteWorkflowDialog
          message={deleteConfirmMessage}
          deleting={deleting}
          onCancel={() => {
            if (!deleting) setDeleteDialogOpen(false)
          }}
          onConfirm={() => void confirmDeleteWorkflow()}
        />
      )}

      <style>{`
        @keyframes pulseGlow {
          0% {
            box-shadow: 0 0 4px rgba(245, 158, 11, 0.2);
          }
          50% {
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.7);
            border-color: rgba(245, 158, 11, 0.75);
          }
          100% {
            box-shadow: 0 0 4px rgba(245, 158, 11, 0.2);
          }
        }
      `}</style>

      {/* Title tooltip strip — workflow name (secondary to breadcrumbs) */}
      <span className="sr-only">{title}</span>
    </>
  )
}

export default function Topbar({ headless = false }: { headless?: boolean }) {
  return <TopbarStudio headless={headless} />
}

function IconAction({
  children,
  onClick,
  disabled,
  title,
  glowing,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  title: string
  glowing?: boolean
}) {
  const glowStyle = glowing && !disabled ? {
    background: 'var(--bg-3)',
    color: 'var(--text-0)',
    border: '1px solid var(--border-strong)',
    boxShadow: '0 0 0 1px color-mix(in srgb, var(--text-0) 8%, transparent)',
  } : {}

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className="flex items-center justify-center"
      style={{
        width: 28,
        height: 28,
        borderRadius: 6,
        background: 'transparent',
        color: disabled ? 'var(--text-3)' : 'var(--text-1)',
        border: '1px solid transparent',
        opacity: disabled ? 0.55 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 150ms ease-in-out',
        ...glowStyle
      }}
      onMouseEnter={(e) => {
        if (disabled) return
        if (glowing) {
          ;(e.currentTarget as HTMLElement).style.background = 'rgba(245, 158, 11, 0.25)'
          ;(e.currentTarget as HTMLElement).style.borderColor = 'rgba(245, 158, 11, 0.65)'
        } else {
          ;(e.currentTarget as HTMLElement).style.background = 'var(--bg-2)'
          ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--border-soft)'
          ;(e.currentTarget as HTMLElement).style.color = 'var(--text-0)'
        }
      }}
      onMouseLeave={(e) => {
        if (disabled) return
        if (glowing) {
          ;(e.currentTarget as HTMLElement).style.background = 'rgba(245, 158, 11, 0.15)'
          ;(e.currentTarget as HTMLElement).style.borderColor = 'rgba(245, 158, 11, 0.45)'
        } else {
          ;(e.currentTarget as HTMLElement).style.background = 'transparent'
          ;(e.currentTarget as HTMLElement).style.borderColor = 'transparent'
          ;(e.currentTarget as HTMLElement).style.color = 'var(--text-1)'
        }
      }}
    >
      {children}
    </button>
  )
}

function findMatchingPresetId(v: WorkflowContextForm): string {
  return FXFRO_TEST_ALERT_PRESETS.find((p) => p.alert_id === v.alert_id)?.alert_id ?? ''
}

function WorkflowContextRunModal({
  value,
  running,
  onChange,
  onApplyFullContext,
  onCancel,
  onRun,
}: {
  value: WorkflowContextForm
  running: boolean
  onChange: (patch: Partial<WorkflowContextForm>) => void
  onApplyFullContext: (full: WorkflowContextForm) => void
  onCancel: () => void
  onRun: () => void
}) {
  const [presetChoice, setPresetChoice] = useState(() => findMatchingPresetId(value))

  useEffect(() => {
    setPresetChoice(findMatchingPresetId(value))
  }, [value])

  return (
    <Modal
      ariaLabel="Workflow context"
      onClose={onCancel}
      closeOnBackdrop={!running}
      zIndex={100}
      overlayStyle={{ background: 'rgba(0,0,0,0.48)' }}
      panelStyle={{
        width: 620,
        maxWidth: 'calc(100vw - 32px)',
        borderRadius: 14,
        border: '1px solid var(--border)',
        boxShadow: '0 24px 80px rgba(0,0,0,0.45)',
        overflow: 'hidden',
      }}
    >
        <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--border-soft)' }}>
          <div className="display" style={{ fontSize: 16, fontWeight: 650, color: 'var(--text-0)' }}>
            Run Workflow Context
          </div>
          <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
            Select the scenario and fill alert context. If you enter only `alert_id`, backend hydrates the remaining FXFRO
            fields.
          </div>
        </div>

        <div className="px-5 py-4" style={{ display: 'grid', gap: 14 }}>
          <ContextSection title="Test alerts (SQLite demo)">
            <label style={{ display: 'grid', gap: 4 }}>
              <span className="num" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
                Load preset
              </span>
              <select
                data-testid="workflow-context-test-alert-select"
                value={presetChoice}
                onChange={(e) => {
                  const id = e.target.value
                  setPresetChoice(id)
                  if (!id) return
                  const preset = FXFRO_TEST_ALERT_PRESETS.find((p) => p.alert_id === id)
                  if (preset) onApplyFullContext(preset)
                }}
                style={modalInputStyle}
              >
                <option value="">Custom (manual)</option>
                {FXFRO_TEST_ALERT_PRESETS.map((p) => (
                  <option key={p.alert_id} value={p.alert_id}>
                    {p.alert_id} · {p.trader_name} · {p.currency_pair}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ fontSize: 10.5, color: 'var(--text-3)', lineHeight: 1.4 }}>
              Pick an id to fill participant, trader, keyword, pair, and window times for that alert.
            </div>
          </ContextSection>

          <ContextSection title="Scenario">
            <ContextField label="scenario">
              <select
                value={value.scenario}
                onChange={(e) => onChange({ scenario: e.target.value })}
                style={modalInputStyle}
              >
                <option value="fxfro">fxfro</option>
              </select>
            </ContextField>
          </ContextSection>

          <ContextSection title="Alert">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <ContextField label="alert_id">
                <ContextInput value={value.alert_id} onChange={(alert_id) => onChange({ alert_id })} placeholder="ALERT-FR-001" />
              </ContextField>
              <ContextField label="keyword">
                <ContextInput value={value.keyword} onChange={(keyword) => onChange({ keyword })} placeholder="fixing" />
              </ContextField>
            </div>
          </ContextSection>

          <ContextSection title="Trader">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <ContextField label="participant_id">
                <ContextInput value={value.participant_id} onChange={(participant_id) => onChange({ participant_id })} placeholder="P-T001" />
              </ContextField>
              <ContextField label="trader_id">
                <ContextInput value={value.trader_id} onChange={(trader_id) => onChange({ trader_id })} placeholder="T001" />
              </ContextField>
              <ContextField label="trader_name">
                <ContextInput value={value.trader_name} onChange={(trader_name) => onChange({ trader_name })} placeholder="Avery Shah" />
              </ContextField>
            </div>
          </ContextSection>

          <ContextSection title="Market And Time">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <ContextField label="currency_pair">
                <ContextInput value={value.currency_pair} onChange={(currency_pair) => onChange({ currency_pair })} placeholder="EUR/USD" />
              </ContextField>
              <ContextField label="date">
                <ContextInput value={value.date} onChange={(date) => onChange({ date, alert_date: date })} placeholder="2024-01-01" />
              </ContextField>
              <ContextField label="start_time">
                <ContextInput value={value.start_time} onChange={(start_time) => onChange({ start_time })} placeholder="2024-01-01T11:07:00" />
              </ContextField>
              <ContextField label="end_time">
                <ContextInput value={value.end_time} onChange={(end_time) => onChange({ end_time })} placeholder="2024-01-01T11:52:00" />
              </ContextField>
            </div>
          </ContextSection>
        </div>

        <div
          className="px-5 py-4 flex items-center justify-end gap-2"
          style={{ borderTop: '1px solid var(--border-soft)' }}
        >
          <GhostButton onClick={onCancel} disabled={running}>Cancel</GhostButton>
          <GhostButton onClick={onRun} disabled={running || !value.alert_id.trim()}>
            {running ? 'Running...' : 'Run with context'}
          </GhostButton>
        </div>
    </Modal>
  )
}

const modalInputStyle: React.CSSProperties = {
  width: '100%',
  height: 34,
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg-0)',
  color: 'var(--text-0)',
  padding: '6px 9px',
  fontSize: 12,
  fontFamily: 'inherit',
}

function ContextSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        className="font-mono"
        style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 8 }}
      >
        {title}
      </div>
      {children}
    </div>
  )
}

function ContextField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'grid', gap: 4 }}>
      <span className="num" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>{label}</span>
      {children}
    </label>
  )
}

function ContextInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={modalInputStyle}
    />
  )
}

function BreadcrumbPill({ label, mono }: { label: string; mono?: boolean }) {
  return (
    <button
      type="button"
      className="flex items-center gap-1.5 border-0 rounded-[7px] cursor-pointer bg-transparent shrink-0"
      style={{
        padding: '5px 9px',
        color: 'var(--text-0)',
        fontSize: 13,
        fontWeight: 500,
        fontFamily: 'inherit',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--bg-2)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
      }}
    >
      {label}
      <ArcIcon icon={ChevronDown} size={10} strokeWidth={1.4} style={{ color: 'var(--text-2)', opacity: 0.85 }} />
    </button>
  )
}

/** Beautiful, glassmorphic dev/uat/prod environment selector dropdown. */
export function EnvironmentDropdown() {
  const environment = useWorkflowStore((s) => s.environment)
  const setEnvironment = useWorkflowStore((s) => s.setEnvironment)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const envConfig = {
    dev: { label: 'Development (DEV)', dot: 'var(--accent)', bg: 'rgba(26, 115, 232, 0.08)' },
    uat: { label: 'Staging (UAT)', dot: '#f59e0b', bg: 'rgba(245, 158, 11, 0.08)' },
    prod: { label: 'Production (PROD)', dot: 'var(--success)', bg: 'rgba(16, 185, 129, 0.08)' },
  }

  const current = envConfig[environment] || envConfig.dev

  return (
    <div ref={containerRef} className="relative select-none" style={{ zIndex: 100 }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2"
        style={{
          padding: '5px 10px',
          borderRadius: 8,
          background: 'var(--bg-3)',
          border: '1px solid var(--border-soft)',
          color: 'var(--text-1)',
          cursor: 'pointer',
          fontSize: '12px',
          fontWeight: 500,
          transition: 'background 150ms, border-color 150ms',
          height: 32,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'var(--bg-2)'
          e.currentTarget.style.borderColor = 'var(--border)'
        }}
        onMouseLeave={(e) => {
          if (!open) {
            e.currentTarget.style.background = 'var(--bg-3)'
            e.currentTarget.style.borderColor = 'var(--border-soft)'
          }
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: 999,
            background: current.dot,
            boxShadow: `0 0 0 2px color-mix(in srgb, ${current.dot} 18%, transparent)`,
          }}
        />
        <span className="font-mono text-xs uppercase" style={{ letterSpacing: '0.04em' }}>{environment}</span>
        <ArcIcon icon={ChevronDown} size={11} style={{ opacity: 0.6, marginLeft: 2 }} />
      </button>

      {open && (
        <div
          className="panel-glass absolute left-0 mt-1.5"
          style={{
            width: 170,
            background: 'var(--bg-2)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            boxShadow: '0 8px 30px rgba(0, 0, 0, 0.15)',
            padding: '4px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {(['dev', 'uat', 'prod'] as const).map((env) => {
            const cfg = envConfig[env]
            const isSelected = env === environment
            return (
              <button
                key={env}
                type="button"
                onClick={() => {
                  setEnvironment(env)
                  setOpen(false)
                }}
                className="flex items-center gap-2"
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  borderRadius: 6,
                  border: 'none',
                  background: isSelected ? cfg.bg : 'transparent',
                  color: isSelected ? 'var(--text-0)' : 'var(--text-2)',
                  cursor: 'pointer',
                  fontSize: '11.5px',
                  textAlign: 'left',
                  fontWeight: isSelected ? 550 : 450,
                  transition: 'background 120ms, color 120ms',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'var(--bg-3)'
                    e.currentTarget.style.color = 'var(--text-1)'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--text-2)'
                  }
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 999,
                    background: cfg.dot,
                    boxShadow: `0 0 0 2px color-mix(in srgb, ${cfg.dot} 18%, transparent)`,
                  }}
                />
                <span className="font-mono flex-1">{env.toUpperCase()}</span>
                {isSelected && (
                  <span className="text-[10px]" style={{ color: cfg.dot, fontWeight: 700 }}>
                    ✓
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export function ViewModeToggle({
  value,
  onChange,
}: {
  value: 'canvas' | 'code'
  onChange: (next: 'canvas' | 'code') => void
}) {
  const prefetchCode = () => {
    void import('../../lib/prefetchMonacoEditor').then((m) => m.prefetchMonacoEditor())
  }

  return (
    <div role="group" aria-label="Workspace view" className="studio-segment-track">
      <ViewModeIconBtn
        active={value === 'canvas'}
        onClick={() => onChange('canvas')}
        title="Canvas"
        testId="view-mode-canvas"
      >
        <ArcIcon icon={LayoutGrid} size={13} style={{ marginRight: 5 }} />
        Canvas
      </ViewModeIconBtn>
      <ViewModeIconBtn
        active={value === 'code'}
        onClick={() => onChange('code')}
        onMouseEnter={prefetchCode}
        onFocus={prefetchCode}
        title="Code editor"
        testId="view-mode-code"
      >
        <ArcIcon icon={Code2} size={13} style={{ marginRight: 5 }} />
        Code
      </ViewModeIconBtn>
    </div>
  )
}

function ViewModeIconBtn({
  active,
  onClick,
  onMouseEnter,
  onFocus,
  title,
  testId,
  children,
}: {
  active: boolean
  onClick: () => void
  onMouseEnter?: () => void
  onFocus?: () => void
  title: string
  testId?: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onFocus={onFocus}
      title={title}
      aria-label={title}
      aria-pressed={active}
      data-testid={testId}
      className="studio-segment-btn"
      style={{
        height: 28,
        padding: '0 10px',
        borderRadius: 8,
        fontSize: 11,
        fontWeight: active ? 600 : 500,
      }}
    >
      {children}
    </button>
  )
}

/** View / Edit toggle — Edit opens sherpa in the side panel. */
export function ViewEditToggle({
  value,
  onChange,
}: {
  value: 'view' | 'edit'
  onChange: (next: 'view' | 'edit') => void
}) {
  return (
    <div role="group" aria-label="Workspace mode" className="studio-segment-track font-mono">
      <ViewEditBtn
        active={value === 'view'}
        onClick={() => onChange('view')}
        title="View workflow"
        testId="workspace-mode-view"
      >
        View
      </ViewEditBtn>
      <ViewEditBtn
        active={value === 'edit'}
        onClick={() => onChange('edit')}
        title="Edit workflow with sherpa"
        testId="workspace-mode-edit"
      >
        Edit
      </ViewEditBtn>
    </div>
  )
}

function ViewEditBtn({
  active,
  onClick,
  title,
  testId,
  children,
}: {
  active: boolean
  onClick: () => void
  title: string
  testId?: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      aria-pressed={active}
      data-testid={testId}
      className="studio-segment-btn font-mono"
      style={{
        height: 28,
        padding: '0 10px',
        borderRadius: 8,
        fontSize: 11,
        fontWeight: active ? 600 : 500,
      }}
    >
      {children}
    </button>
  )
}

function DeleteWorkflowDialog({
  message,
  deleting,
  onCancel,
  onConfirm,
}: {
  message: string
  deleting: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <Modal
      ariaLabel="Delete workflow"
      onClose={onCancel}
      closeOnBackdrop={!deleting}
      panelStyle={{
        width: 440,
        maxWidth: 'calc(100vw - 24px)',
        borderRadius: 12,
        border: '1px solid var(--border)',
        boxShadow: '0 24px 70px rgba(0,0,0,0.45)',
        padding: 16,
        display: 'grid',
        gap: 12,
      }}
    >
      <div
        className="display"
        style={{
          fontSize: 16,
          color: 'var(--text-0)',
          fontWeight: 650,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <ArcIcon icon={AlertTriangle} size={18} style={{ color: 'var(--danger)' }} />
        Delete workflow
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>{message}</div>
      <div className="flex items-center justify-end gap-2" style={{ marginTop: 8 }}>
        <GhostButton onClick={onCancel} disabled={deleting}>
          Cancel
        </GhostButton>
        <Button variant="danger" size="md" onClick={onConfirm} disabled={deleting}>
          {deleting ? 'Deleting…' : 'Delete'}
        </Button>
      </div>
    </Modal>
  )
}

function SaveBeforeRunDialog({
  onCancel,
  onSaveAndRun,
  saving,
}: {
  onCancel: () => void
  onSaveAndRun: () => void
  saving: boolean
}) {
  return (
    <Modal
      ariaLabel="Save before running"
      onClose={onCancel}
      closeOnBackdrop={!saving}
      panelStyle={{
        width: 440,
        maxWidth: 'calc(100vw - 24px)',
        borderRadius: 12,
        border: '1px solid var(--border)',
        boxShadow: '0 24px 70px rgba(0,0,0,0.45)',
        padding: 16,
        display: 'grid',
        gap: 12,
      }}
    >
      <div className="display" style={{ fontSize: 16, color: 'var(--text-0)', fontWeight: 650, display: 'flex', alignItems: 'center', gap: 8 }}>
        <ArcIcon icon={Save} size={18} style={{ color: 'var(--text-2)' }} />
        Save Changes Before Running
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-2)', lineHeight: '1.5' }}>
        You have unsaved changes in your workflow. To ensure your execution reflects the correct configuration, you must save your changes before running the workflow.
      </div>
      <div className="flex items-center justify-end gap-2" style={{ marginTop: 8 }}>
        <GhostButton onClick={onCancel} disabled={saving}>
          Cancel
        </GhostButton>
        <Button variant="primary" size="md" onClick={onSaveAndRun} disabled={saving}>
          {saving ? 'Saving...' : 'Save & Run'}
        </Button>
      </div>
    </Modal>
  )
}

function SaveAsDialog({
  value,
  saving,
  onChange,
  onCancel,
  onSave,
}: {
  value: string
  saving: boolean
  onChange: (value: string) => void
  onCancel: () => void
  onSave: () => void
}) {
  return (
    <Modal
      ariaLabel="Save workflow as"
      onClose={onCancel}
      closeOnBackdrop={!saving}
      panelStyle={{
        width: 420,
        maxWidth: 'calc(100vw - 24px)',
        borderRadius: 12,
        border: '1px solid var(--border)',
        boxShadow: '0 24px 70px rgba(0,0,0,0.45)',
        padding: 14,
        display: 'grid',
        gap: 10,
      }}
    >
      <div className="display" style={{ fontSize: 15, color: 'var(--text-0)', fontWeight: 620 }}>
        Save workflow as
      </div>
      <input
        autoFocus
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            onSave()
          }
        }}
        style={modalInputStyle}
        placeholder="Workflow name"
      />
      <div className="flex items-center justify-end gap-2">
        <GhostButton onClick={onCancel} disabled={saving}>Cancel</GhostButton>
        <Button variant="primary" size="md" onClick={onSave} disabled={saving || !value.trim()}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </div>
    </Modal>
  )
}

function NewWorkflowDialog({
  onCancel,
  onExitWithoutSaving,
  onSaveAndNew,
}: {
  onCancel: () => void
  onExitWithoutSaving: () => void
  onSaveAndNew: () => void
}) {
  return (
    <Modal
      ariaLabel="Create new workflow"
      onClose={onCancel}
      zIndex={111}
      panelStyle={{
        width: 460,
        maxWidth: 'calc(100vw - 24px)',
        borderRadius: 12,
        border: '1px solid var(--border)',
        boxShadow: '0 24px 70px rgba(0,0,0,0.45)',
        padding: 14,
        display: 'grid',
        gap: 10,
      }}
    >
      <div className="display" style={{ fontSize: 15, color: 'var(--text-0)', fontWeight: 620 }}>
        Create new workflow
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5 }}>
        You already have a workflow open. Save it first, or exit without saving and start with an empty canvas.
      </div>
      <div className="flex items-center justify-end gap-2">
        <GhostButton onClick={onCancel}>Cancel</GhostButton>
        <GhostButton onClick={onExitWithoutSaving}>Exit Without Saving</GhostButton>
        <Button variant="primary" size="md" onClick={onSaveAndNew}>Save And New</Button>
      </div>
    </Modal>
  )
}

function IconGhost({
  children,
  title,
  onMouseAccent,
  onClick,
}: {
  children: React.ReactNode
  title: string
  onMouseAccent?: 'warning'
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="flex items-center justify-center border-0 rounded-[5px] cursor-pointer bg-transparent"
      style={{ padding: 4, color: 'var(--text-3)' }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--bg-2)'
        e.currentTarget.style.color = 'var(--text-0)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'var(--text-3)'
      }}
    >
      {children}
    </button>
  )
}

function GhostButton({
  children,
  disabled,
  title,
  onClick,
  style,
}: {
  children: React.ReactNode
  disabled?: boolean
  title?: string
  onClick?: () => void
  style?: React.CSSProperties
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className="cursor-pointer bg-transparent"
      style={{
        padding: '7px 14px',
        borderRadius: 8,
        border: `1px solid ${disabled ? 'var(--border-soft)' : 'var(--border)'}`,
        color: disabled ? 'var(--text-3)' : 'var(--text-0)',
        fontSize: 13,
        fontWeight: 500,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit',
        ...style,
      }}
      onMouseEnter={(e) => {
        if (disabled) return
        e.currentTarget.style.background = 'var(--bg-2)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.borderColor = disabled ? 'var(--border-soft)' : 'var(--border)'
      }}
    >
      {children}
    </button>
  )
}

function ThemeIconButton({ children, onClick, title }: { children: React.ReactNode; onClick: () => void; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="flex items-center justify-center border-0 cursor-pointer bg-transparent"
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        border: '1px solid var(--border)',
        color: 'var(--text-0)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--bg-2)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.borderColor = 'var(--border)'
      }}
    >
      {children}
    </button>
  )
}

function StatusIconButton({
  children,
  onClick,
  disabled,
  title,
  status,
  badge,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  title?: string
  status: 'idle' | 'ok' | 'error'
  badge?: number
}) {
  const color =
    status === 'ok'
      ? 'var(--success)'
      : status === 'error'
        ? 'var(--danger)'
        : disabled
          ? 'var(--text-3)'
          : 'var(--text-2)'
  const border =
    status === 'ok'
      ? 'color-mix(in srgb, var(--success) 45%, var(--border))'
      : status === 'error'
        ? 'color-mix(in srgb, var(--danger) 45%, var(--border))'
        : 'var(--border)'
  const background =
    status === 'ok'
      ? 'color-mix(in srgb, var(--success) 10%, transparent)'
      : status === 'error'
        ? 'color-mix(in srgb, var(--danger) 10%, transparent)'
        : 'transparent'

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className="relative flex items-center justify-center border-0"
      style={{
        width: 28,
        height: 28,
        borderRadius: 6,
        background,
        color,
        border: `1px solid ${border}`,
        opacity: disabled ? 0.55 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'background 160ms, color 160ms, border-color 160ms',
      }}
    >
      {children}
      {badge != null && badge > 0 && (
        <span
          className="num"
          style={{
            position: 'absolute',
            top: -4,
            right: -4,
            minWidth: 14,
            height: 14,
            padding: '0 3px',
            borderRadius: 999,
            background: 'var(--danger)',
            color: '#fff',
            fontSize: 8.5,
            lineHeight: '14px',
            border: '1px solid var(--panel-glass-bg)',
          }}
        >
          {badge}
        </span>
      )}
    </button>
  )
}

function BarButton({
  children,
  icon,
  onClick,
  disabled,
  tone,
}: {
  children: React.ReactNode
  icon: React.ReactNode
  onClick: () => void
  disabled?: boolean
  tone?: 'danger'
}) {
  const danger = tone === 'danger'
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 border-0 cursor-pointer bg-transparent"
      style={{
        height: 32,
        padding: '0 12px',
        borderRadius: 8,
        fontSize: 12.5,
        fontWeight: 500,
        color: danger ? 'var(--danger)' : disabled ? 'var(--text-3)' : 'var(--text-0)',
        border: `1px solid ${danger ? 'color-mix(in srgb, var(--danger) 50%, var(--border))' : 'var(--border)'}`,
        opacity: disabled ? 0.55 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
        fontFamily: 'inherit',
      }}
      onMouseEnter={(e) => {
        if (disabled) return
        e.currentTarget.style.background = danger ? 'color-mix(in srgb, var(--danger) 10%, transparent)' : 'var(--bg-2)'
        e.currentTarget.style.borderColor = 'var(--border-strong)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.borderColor = danger ? 'color-mix(in srgb, var(--danger) 50%, var(--border))' : 'var(--border)'
      }}
    >
      {icon}
      <span>{children}</span>
    </button>
  )
}
