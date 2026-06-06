import { useMemo } from 'react'
import { ArcIcon, Plus } from '../../icons/arc'
import { Button } from '../ui/Button'
import { useWorkflowStore } from '../../store/workflowStore'

/** Shared top-left chrome offset — palette header row + canvas overlay align here. */
export const WORKFLOW_ADD_OFFSET = { top: 10, left: 10 } as const

type Props = {
  /** `icon` = square + only (default). `labeled` kept for rare call sites. */
  variant?: 'icon' | 'labeled'
  className?: string
  style?: React.CSSProperties
}

export default function NewWorkflowButton({ variant = 'icon', className, style }: Props) {
  const workflow = useWorkflowStore((s) => s.workflow)
  const lastSavedSignature = useWorkflowStore((s) => s.lastSavedSignature)

  const isDirty = useMemo(() => {
    if (!workflow) return false
    if (!lastSavedSignature) {
      return workflow.nodes.length > 0
    }
    return lastSavedSignature !== JSON.stringify(workflow)
  }, [workflow, lastSavedSignature])

  const onNew = () => {
    if (isDirty) {
      window.dispatchEvent(new CustomEvent('sheep:request-new-workflow'))
    } else {
      useWorkflowStore.getState().newBlankWorkflow()
    }
  }

  if (variant === 'icon') {
    return (
      <Button
        type="button"
        variant="primary"
        onClick={onNew}
        title="New workflow"
        aria-label="New workflow"
        className={`btn--icon ${className ?? ''}`}
        lift={false}
        style={{ width: 30, height: 30, borderRadius: 8, ...style }}
      >
        <ArcIcon icon={Plus} size={15} />
      </Button>
    )
  }

  return (
    <button
      type="button"
      onClick={onNew}
      title="New workflow"
      aria-label="New workflow"
      className={`panel-glass flex items-center justify-center ${className ?? ''}`}
      style={{
        position: 'absolute',
        zIndex: 20,
        top: WORKFLOW_ADD_OFFSET.top,
        left: WORKFLOW_ADD_OFFSET.left,
        width: 30,
        height: 30,
        padding: 0,
        border: '1px solid var(--border-soft)',
        borderRadius: 8,
        cursor: 'pointer',
        background: 'var(--panel-glass-bg)',
        ...style,
      }}
    >
      <Plus size={15} strokeWidth={2} />
    </button>
  )
}
