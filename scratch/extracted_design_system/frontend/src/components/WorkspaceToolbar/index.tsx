/**
 * Persistent workspace chrome — canvas/code toggle and mode-specific actions
 * live in one fixed bar so switching views never remounts or shifts the toolbar.
 */
import { Upload, Download, Trash2, Save, Play, ArcIcon, Copy, Check } from '../../icons/arc'
import { X, Square } from 'lucide-react'
import { ViewModeToggle, ViewEditToggle } from '../Topbar'
import NewWorkflowButton from '../shared/NewWorkflowButton'
import { Button } from '../ui/Button'
import { useWorkflowStore } from '../../store/workflowStore'
import { useCodeEditorToolbar } from './context'

const BAR_HEIGHT = 46

export default function WorkspaceToolbar() {
  const workspaceView = useWorkflowStore((s) => s.workspaceView)
  const setWorkspaceView = useWorkflowStore((s) => s.setWorkspaceView)
  const workspaceEditMode = useWorkflowStore((s) => s.workspaceEditMode)
  const setWorkspaceEditMode = useWorkflowStore((s) => s.setWorkspaceEditMode)
  const workflow = useWorkflowStore((s) => s.workflow)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const resetRun = useWorkflowStore((s) => s.resetRun)

  const isCanvas = workspaceView === 'canvas'

  return (
    <div className="shrink-0 px-3 pt-3 z-30 pointer-events-none">
      <div
        className="panel-glass flex items-center justify-between shrink-0 pointer-events-none"
        style={{
          height: BAR_HEIGHT,
          padding: '0 10px',
          borderRadius: 10,
          border: '1px solid var(--border-soft)',
          boxShadow: 'var(--linear-elev-raised, none)',
          background: 'var(--chrome-elevated)',
        }}
      >
        <div className="flex items-center gap-3 min-w-0 pointer-events-auto">
          <ViewModeToggle value={workspaceView} onChange={setWorkspaceView} />

          <span className="font-mono text-[var(--text-3)] text-[11px]" aria-hidden>
            /
          </span>

          <ViewEditToggle value={workspaceEditMode} onChange={setWorkspaceEditMode} />
        </div>

        <div className="relative pointer-events-auto shrink-0" style={{ width: 240, height: 30 }}>
          <div
            className="absolute inset-0 flex items-center justify-end gap-2 transition-opacity duration-150"
            style={{
              opacity: isCanvas ? 1 : 0,
              pointerEvents: isCanvas ? 'auto' : 'none',
            }}
            aria-hidden={!isCanvas}
          >
            {workflow && (
              <>
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
                <ToolbarIconButton onClick={() => resetRun()} title="Clear canvas / run state">
                  <ArcIcon icon={Trash2} size={13} />
                </ToolbarIconButton>
                <ToolbarIconButton
                  onClick={() => window.dispatchEvent(new CustomEvent('sheep:request-save-workflow'))}
                  title="Save workflow"
                >
                  <ArcIcon icon={Save} size={13} />
                </ToolbarIconButton>
                <Button
                  variant={isRunning ? 'stop' : 'primary'}
                  className="btn--icon"
                  onClick={() =>
                    window.dispatchEvent(
                      new CustomEvent(
                        isRunning ? 'sheep:request-stop-workflow' : 'sheep:request-run-workflow',
                      ),
                    )
                  }
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
                <span className="w-px h-4 shrink-0 bg-[var(--border-soft)]" />
              </>
            )}
            <NewWorkflowButton variant="icon" style={{ position: 'relative', top: 0, left: 0 }} />
          </div>

          <div
            className="absolute inset-0 flex items-center justify-end gap-1 transition-opacity duration-150"
            style={{
              opacity: isCanvas ? 0 : 1,
              pointerEvents: isCanvas ? 'none' : 'auto',
            }}
            aria-hidden={isCanvas}
          >
            <CodeToolbarActions />
          </div>
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
      style={{ width: 28, height: 28, borderRadius: 6 }}
    >
      {children}
    </Button>
  )
}
