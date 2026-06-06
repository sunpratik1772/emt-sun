import { ArcIcon, ThumbsDown, ThumbsUp } from '../icons/arc'
import { useVoteWorkflow } from '../hooks/useLibraryQueries'

export default function WorkflowVoteButtons({
  filename,
  upvoteCount = 0,
  downvoteCount = 0,
  compact = false,
  className = '',
}: {
  filename: string
  upvoteCount?: number
  downvoteCount?: number
  compact?: boolean
  className?: string
}) {
  const vote = useVoteWorkflow()

  const handleVote = (next: 'up' | 'down') => (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    if (vote.isPending) return
    void vote.mutateAsync({ filename, vote: next })
  }

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
        disabled={vote.isPending}
        onClick={handleVote('up')}
      >
        <ArcIcon icon={ThumbsUp} size={compact ? 12 : 14} strokeWidth={2} />
        <span>{upvoteCount}</span>
      </button>
      <button
        type="button"
        className="wf-vote__btn wf-vote__btn--down"
        title="Downvote"
        disabled={vote.isPending}
        onClick={handleVote('down')}
      >
        <ArcIcon icon={ThumbsDown} size={compact ? 12 : 14} strokeWidth={2} />
        <span>{downvoteCount}</span>
      </button>
    </div>
  )
}
