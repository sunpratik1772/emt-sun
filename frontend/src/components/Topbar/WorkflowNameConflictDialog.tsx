import Modal from '../Modal'
import { Button } from '../ui/Button'
import type { WorkflowNameConflict } from '../../lib/workflowNameConflict'

type WorkflowNameConflictDialogProps = {
  displayName: string
  targetFilename: string
  conflicts: WorkflowNameConflict[]
  saving: boolean
  onCancel: () => void
  onReplace: () => void
}

export default function WorkflowNameConflictDialog({
  displayName,
  targetFilename,
  conflicts,
  saving,
  onCancel,
  onReplace,
}: WorkflowNameConflictDialogProps) {
  return (
    <Modal
      ariaLabel="Workflow name conflict"
      onClose={onCancel}
      closeOnBackdrop={!saving}
      panelStyle={{
        width: 460,
        maxWidth: 'calc(100vw - 24px)',
        borderRadius: 12,
        border: '1px solid var(--border)',
        boxShadow: '0 24px 70px rgba(0,0,0,0.45)',
        padding: 16,
        display: 'grid',
        gap: 12,
      }}
    >
      <div className="display" style={{ fontSize: 16, color: 'var(--text-0)', fontWeight: 650 }}>
        Name already in use
      </div>
      <p style={{ margin: 0, fontSize: 13, color: 'var(--text-2)', lineHeight: 1.5 }}>
        A saved workflow named <strong style={{ color: 'var(--text-0)' }}>{displayName}</strong> already
        exists. Choose a different name, or replace the existing{' '}
        {conflicts.length === 1 ? 'file' : 'files'} with this canvas.
      </p>
      <ul
        className="font-mono"
        style={{
          margin: 0,
          padding: '10px 12px',
          listStyle: 'none',
          display: 'grid',
          gap: 6,
          fontSize: 11,
          color: 'var(--text-1)',
          background: 'var(--bg-2)',
          border: '1px solid var(--border-soft)',
          borderRadius: 8,
        }}
      >
        {conflicts.map((c) => (
          <li key={c.filename}>
            <span style={{ color: 'var(--text-0)' }}>{c.filename}</span>
            {c.node_count != null ? (
              <span style={{ color: 'var(--text-3)' }}> · {c.node_count} nodes</span>
            ) : null}
          </li>
        ))}
      </ul>
      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--text-3)', lineHeight: 1.45 }}>
        Replace saves to <span style={{ color: 'var(--text-2)' }}>{targetFilename}</span> and removes the
        conflicting {conflicts.length === 1 ? 'copy' : 'copies'} above.
      </p>
      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={saving}>
          Choose different name
        </Button>
        <Button type="button" variant="primary" onClick={onReplace} disabled={saving}>
          {saving ? 'Replacing…' : 'Replace existing'}
        </Button>
      </div>
    </Modal>
  )
}
