import { useState } from 'react'
import { ArcIcon, ThumbsDown, ThumbsUp } from '../icons/arc'
import { useVoteWorkflow } from '../hooks/useLibraryQueries'
import { api } from '../services/api'
import { toast } from '../store/toastStore'
import { useWorkflowStore } from '../store/workflowStore'
import type { Workflow } from '../types'

function slugify(name: string | undefined | null): string {
  const s = (name || 'workflow').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
  return s || 'workflow'
}

export default function WorkflowVoteButtons({
  filename,
  upvoteCount = 0,
  downvoteCount = 0,
  compact = false,
  className = '',
  workflow,
  isDraft = false,
}: {
  filename: string
  upvoteCount?: number
  downvoteCount?: number
  compact?: boolean
  className?: string
  workflow?: Workflow | null
  isDraft?: boolean
}) {
  const vote = useVoteWorkflow()
  const [localUp, setLocalUp] = useState(upvoteCount)
  const [localDown, setLocalDown] = useState(downvoteCount)
  const [hasVoted, setHasVoted] = useState<'up' | 'down' | null>(null)
  const [voting, setVoting] = useState(false)

  const handleVote = (next: 'up' | 'down') => async (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    if (voting || hasVoted) return

    setVoting(true)
    try {
      let targetFilename = filename
      if (isDraft && workflow) {
        // Save the workflow first
        const baseStem = workflow.name ? slugify(workflow.name) : 'workflow'
        targetFilename = `${baseStem}.yaml`

        await api.saveWorkflow(targetFilename, workflow, { replace: true })

        const currentWf = useWorkflowStore.getState().workflow
        if (currentWf && currentWf.workflow_id === workflow.workflow_id) {
          useWorkflowStore.getState().markSaved(targetFilename)
        }
      }

      await vote.mutateAsync({ filename: targetFilename, vote: next })

      setHasVoted(next)
      if (next === 'up') setLocalUp((prev) => prev + 1)
      else setLocalDown((prev) => prev + 1)

      toast.success(
        next === 'up'
          ? `Upvoted! Workflow saved as ${targetFilename}`
          : `Downvoted workflow ${targetFilename}`,
      )
    } catch (err) {
      toast.error(`Failed to register vote: ${(err as Error).message}`)
    } finally {
      setVoting(false)
    }
  }

  const isUpSelected = hasVoted === 'up'
  const isDownSelected = hasVoted === 'down'

  return (
    <div
      className={`wf-vote${compact ? ' wf-vote--compact' : ''}${className ? ` ${className}` : ''}`}
      role="group"
      aria-label="Workflow feedback"
    >
      <button
        type="button"
        className="wf-vote__btn"
        title="Upvote — promote to good examples"
        disabled={vote.isPending || voting || hasVoted !== null}
        onClick={handleVote('up')}
        style={isUpSelected ? { color: 'var(--success)', borderColor: 'var(--success)' } : undefined}
      >
        <ArcIcon icon={ThumbsUp} size={compact ? 12 : 14} strokeWidth={2} />
        <span>{localUp}</span>
      </button>
      <button
        type="button"
        className="wf-vote__btn wf-vote__btn--down"
        title="Downvote"
        disabled={vote.isPending || voting || hasVoted !== null}
        onClick={handleVote('down')}
        style={isDownSelected ? { color: 'var(--danger)', borderColor: 'var(--danger)' } : undefined}
      >
        <ArcIcon icon={ThumbsDown} size={compact ? 12 : 14} strokeWidth={2} />
        <span>{localDown}</span>
      </button>
    </div>
  )
}
