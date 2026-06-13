/**
 * Persistent workspace chrome — canvas/code toggle and mode-specific actions
 * live in one fixed bar so switching views never remounts or shifts the toolbar.
 */
import { useState, useRef, useEffect, useMemo } from 'react'
import { Upload, Download, Trash2, Save, Play, ArcIcon, Copy, Check, MoreHorizontal, Pencil } from '../../icons/arc'
import { X, Square } from 'lucide-react'
import { ViewModeToggle, ViewEditToggle, EnvironmentDropdown } from '../Topbar'
import NewWorkflowButton from '../shared/NewWorkflowButton'
import { Button } from '../ui/Button'
import { useWorkflowStore } from '../../store/workflowStore'
import { useCodeEditorToolbar } from './context'

const BAR_HEIGHT = 46

function filenameStem(filename: string | null | undefined): string {
  if (!filename) return ''
  return filename.replace(/\.(yaml|yml|json)$/i, '').trim()
}

export default function WorkspaceToolbar() {
  const workspaceView = useWorkflowStore((s) => s.workspaceView)
  const setWorkspaceView = useWorkflowStore((s) => s.setWorkspaceView)
  const workspaceEditMode = useWorkflowStore((s) => s.workspaceEditMode)
  const setWorkspaceEditMode = useWorkflowStore((s) => s.setWorkspaceEditMode)
  const workflow = useWorkflowStore((s) => s.workflow)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const lastSavedSignature = useWorkflowStore((s) => s.lastSavedSignature)
  const [nameHovered, setNameHovered] = useState(false)

  const isCanvas = workspaceView === 'canvas'

  const isDirty = useMemo(() => {
    if (!workflow) return false
    if (!lastSavedSignature) {
      return workflow.nodes.length > 0
    }
    return lastSavedSignature !== JSON.stringify(workflow)
  }, [workflow, lastSavedSignature])

  const displayWorkflowName = workflow
    ? (workflow.name || '').trim() || filenameStem(sourceFilename) || 'Untitled workflow'
    : 'No active workflow'

  let statusClass = 'saved'
  let statusLabel = 'Saved'

  if (isRunning) {
    statusClass = 'running'
    statusLabel = 'Running'
  } else if (isDirty) {
    statusClass = 'unsaved'
    statusLabel = 'Unsaved'
  }

  return (
    <div className="shrink-0 px-3 pt-3 z-30">
      <div className="wt panel-glass workspace-toolbar-inner shrink-0">
        
        {/* Left Side: Environment and Name / Status */}
        <div className="workspace-toolbar-left flex items-center min-w-0" style={{ gap: 6 }}>
          <EnvironmentDropdown />
          <span className="font-mono text-[var(--text-3)] text-[11px] studio-toolbar-slash" aria-hidden>
            /
          </span>
          <div
            className="flex items-center min-w-0"
            style={{ gap: 6, cursor: workflow ? 'pointer' : 'default' }}
            onMouseEnter={() => setNameHovered(true)}
            onMouseLeave={() => setNameHovered(false)}
            onClick={() => {
              if (workflow) {
                window.dispatchEvent(new CustomEvent('sheep:request-save-workflow'))
              }
            }}
            title={workflow ? 'Rename and Save As' : undefined}
          >
            {workflow && (
              <span className={`studio-status-dot ${statusClass}`} />
            )}
            <span
              className="font-mono truncate"
              style={{
                color: 'var(--text-1)',
                fontSize: 12.5,
                lineHeight: 1.25,
                fontWeight: 500,
                maxWidth: 'clamp(120px, calc(30vw - 100px), 280px)',
              }}
            >
              {displayWorkflowName}
            </span>
            {workflow && nameHovered && (
              <span style={{ display: 'inline-flex', alignItems: 'center', color: 'var(--text-3)' }}>
                <ArcIcon icon={Pencil} size={10} style={{ marginLeft: 2 }} />
              </span>
            )}
          </div>
        </div>

        {/* Center: Canvas/Code and View/Edit Toggles */}
        <div className="workspace-toolbar-center flex items-center gap-3 min-w-0">
          <ViewModeToggle value={workspaceView} onChange={setWorkspaceView} />

          <span className="font-mono text-[var(--text-3)] text-[11px] studio-toolbar-slash" aria-hidden>
            /
          </span>

          <ViewEditToggle value={workspaceEditMode} onChange={setWorkspaceEditMode} />
        </div>

        <div className="workspace-toolbar-right shrink-0 min-w-0">
          {isCanvas ? (
            <>
              {workflow ? (
                <>
                  {/* Expanded group: visible when wide */}
                  <div className="toolbar-expanded-actions">
                    <ToolbarIconButton
                      onClick={() => window.dispatchEvent(new CustomEvent('sheep:request-import-workflow'))}
                      title="Import workflow"
                    >
                      <ArcIcon icon={Upload} size={13} />
                    </ToolbarIconButton>
                    <ToolbarIconButton
                      onClick={() => window.dispatchEvent(new CustomEvent('sheep:request-export-workflow'))}
                      title="Export workflow"
                    >
                      <ArcIcon icon={Download} size={13} />
                    </ToolbarIconButton>
                    <ToolbarIconButton
                      onClick={() => window.dispatchEvent(new CustomEvent('sheep:request-delete-workflow'))}
                      title="Delete workflow"
                    >
                      <ArcIcon icon={Trash2} size={13} />
                    </ToolbarIconButton>
                  </div>

                  {/* Collapsed group: visible when narrow */}
                  <div className="toolbar-collapsed-actions">
                    <CanvasActionsDropdown
                      onImport={() => window.dispatchEvent(new CustomEvent('sheep:request-import-workflow'))}
                      onExport={() => window.dispatchEvent(new CustomEvent('sheep:request-export-workflow'))}
                      onDelete={() => window.dispatchEvent(new CustomEvent('sheep:request-delete-workflow'))}
                    />
                  </div>

                  {/* Always visible action buttons */}
                  <ToolbarIconButton
                    onClick={() => window.dispatchEvent(new CustomEvent('sheep:request-save-workflow'))}
                    title="Save workflow"
                  >
                    <ArcIcon icon={Save} size={13} />
                  </ToolbarIconButton>
                  <Button
                    variant={isRunning ? 'stop' : 'primary'}
                    className="btn--icon workspace-run-btn"
                    onClick={() =>
                      window.dispatchEvent(
                        new CustomEvent(
                          isRunning ? 'sheep:request-stop-workflow' : 'sheep:request-run-workflow',
                        ),
                      )
                    }
                    data-testid="workspace-run-workflow-btn"
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
                  <span className="w-px h-4 shrink-0 bg-[var(--border-soft)]" />
                </>
              ) : null}
              <NewWorkflowButton
                variant="icon"
                className="workspace-new-btn"
                style={{ position: 'relative', top: 0, left: 0 }}
              />
            </>
          ) : (
            <CodeToolbarActions />
          )}
        </div>
      </div>
    </div>
  )
}

function CodeToolbarActions() {
  const { api } = useCodeEditorToolbar()
  const workspaceEditMode = useWorkflowStore((s) => s.workspaceEditMode)
  const format = api?.format ?? 'json'
  const saving = api?.saving ?? false
  const loading = api?.loading ?? false
  const editing = workspaceEditMode === 'edit'
  const disabled = !api?.hasWorkflow || loading

  return (
    <>
      <FormatPill active={format === 'json'} onClick={() => api?.setFormat('json')} disabled={!api}>
        JSON
      </FormatPill>
      <FormatPill active={format === 'yaml'} onClick={() => api?.setFormat('yaml')} disabled={!api}>
        YAML
      </FormatPill>
      <ToolbarIconButton title="Copy code" onClick={() => api?.onCopy()} disabled={!api?.hasContent}>
        <ArcIcon icon={Copy} size={13} />
      </ToolbarIconButton>
      {editing && (
        <>
          <ToolbarIconButton title="Save code changes" onClick={() => api?.onSave()} disabled={saving || disabled}>
            <ArcIcon icon={Check} size={13} />
          </ToolbarIconButton>
          <ToolbarIconButton title="Cancel editing" onClick={() => api?.onCancel()} disabled={saving}>
            <X size={13} />
          </ToolbarIconButton>
        </>
      )}
    </>
  )
}

function FormatPill({
  children,
  active,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  active: boolean
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="font-mono"
      style={{
        height: 24,
        padding: '0 8px',
        borderRadius: 6,
        border: `1px solid ${active ? 'var(--border-strong)' : 'var(--border-soft)'}`,
        background: active ? 'var(--bg-2)' : 'transparent',
        color: active ? 'var(--text-0)' : 'var(--text-2)',
        fontSize: 10.5,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
      }}
    >
      {children}
    </button>
  )
}

function ToolbarIconButton({
  children,
  onClick,
  title,
  disabled,
}: {
  children: React.ReactNode
  onClick: () => void
  title: string
  disabled?: boolean
}) {
  return (
    <Button
      variant="icon"
      onClick={onClick}
      title={title}
      aria-label={title}
      disabled={disabled}
      lift={false}
      className="toolbar-icon-btn"
      style={{ width: 28, height: 28, borderRadius: 6 }}
    >
      {children}
    </Button>
  )
}

function CanvasActionsDropdown({
  onImport,
  onExport,
  onDelete,
}: {
  onImport: () => void
  onExport: () => void
  onDelete: () => void
}) {
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

  return (
    <div ref={containerRef} className="relative inline-block text-left" style={{ display: 'inline-flex' }}>
      <Button
        variant="icon"
        onClick={() => setOpen(!open)}
        title="More actions"
        aria-label="More actions"
        lift={false}
        className="toolbar-icon-btn"
        style={{ width: 28, height: 28, borderRadius: 6 }}
      >
        <ArcIcon icon={MoreHorizontal} size={13} />
      </Button>

      {open && (
        <div
          className="panel-glass absolute right-0 mt-1.5"
          style={{
            width: 140,
            background: 'var(--bg-2)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            boxShadow: '0 8px 30px rgba(0, 0, 0, 0.25)',
            padding: '4px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            zIndex: 100,
          }}
        >
          <DropdownItem
            onClick={() => {
              onImport()
              setOpen(false)
            }}
            icon={Upload}
            label="Import"
          />
          <DropdownItem
            onClick={() => {
              onExport()
              setOpen(false)
            }}
            icon={Download}
            label="Export"
          />
          <DropdownItem
            onClick={() => {
              onDelete()
              setOpen(false)
            }}
            icon={Trash2}
            label="Delete"
            danger
          />
        </div>
      )}
    </div>
  )
}

function DropdownItem({
  onClick,
  icon,
  label,
  danger,
}: {
  onClick: () => void
  icon: any
  label: string
  danger?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2"
      style={{
        width: '100%',
        padding: '6px 8px',
        borderRadius: 6,
        border: 'none',
        background: 'transparent',
        color: danger ? 'var(--danger)' : 'var(--text-1)',
        cursor: 'pointer',
        fontSize: '11px',
        textAlign: 'left',
        fontWeight: 500,
        transition: 'background 120ms, color 120ms',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'var(--bg-3)'
        e.currentTarget.style.color = danger ? 'var(--danger)' : 'var(--text-0)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = danger ? 'var(--danger)' : 'var(--text-1)'
      }}
    >
      <ArcIcon icon={icon} size={11} />
      <span>{label}</span>
    </button>
  )
}
