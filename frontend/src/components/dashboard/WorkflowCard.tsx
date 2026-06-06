import { ArcIcon, ArrowUpRight } from '../../icons/arc'
import WorkflowVoteButtons from '../WorkflowVoteButtons'
import type { DashboardWorkflow } from './types'
import { formatNodeType } from './utils'

function statusGlassClass(workflow: DashboardWorkflow): string {
  if (workflow.lastRun?.status === 'success') return 'dash-wf-card--status-success'
  if (workflow.lastRun?.status === 'error') return 'dash-wf-card--status-error'
  if (workflow.lastRun?.status === 'running') return 'dash-wf-card--status-running'
  if (workflow.lastRun?.status === 'warning') return 'dash-wf-card--status-warn'
  if (workflow.kind === 'draft') return 'dash-wf-card--status-draft'
  return 'dash-wf-card--status-idle'
}

export default function WorkflowCard({
  workflow,
  tintIndex,
  onOpen,
}: {
  workflow: DashboardWorkflow
  tintIndex: number
  onOpen?: () => void
}) {
  const statusClass =
    workflow.lastRun?.status === 'success'
      ? 'dash-wf-card__status--success'
      : workflow.lastRun?.status === 'error'
        ? 'dash-wf-card__status--error'
        : workflow.lastRun?.status === 'running'
          ? 'dash-wf-card__status--running'
          : ''

  return (
    <article
      className={`dash-wf-card dash-wf-card--glass dash-wf-card--${tintIndex % 6} ${statusGlassClass(workflow)}`}
    >
      <div className="dash-wf-card__head">
        <h3 className="dash-wf-card__title">{workflow.name}</h3>
        <div className="dash-wf-card__head-end">
          {workflow.kind === 'saved' && workflow.filename ? (
            <WorkflowVoteButtons
              filename={workflow.filename}
              upvoteCount={workflow.upvoteCount ?? 0}
              downvoteCount={workflow.downvoteCount ?? 0}
              compact
            />
          ) : null}
          <span className="dash-wf-card__time">{workflow.updatedLabel}</span>
        </div>
      </div>

      <div className="dash-wf-card__meta">
        {workflow.kind === 'draft' && <span className="dash-pill dash-pill--draft">Draft</span>}
        <span className={`dash-wf-card__status ${statusClass}`}>
          {workflow.lastRun?.label ?? 'Not run yet'}
        </span>
      </div>

      <p className="dash-wf-card__nodes">
        {workflow.nodeCount} {workflow.nodeCount === 1 ? 'node' : 'nodes'}
      </p>

      {workflow.nodeTypes.length > 0 ? (
        <div className="dash-wf-card__chips">
          {workflow.nodeTypes.slice(0, 3).map((type) => (
            <span key={type} className="dash-pill dash-pill--chip">
              {formatNodeType(type)}
            </span>
          ))}
        </div>
      ) : null}

      <button type="button" className="dash-wf-card__action" onClick={onOpen}>
        Open Studio
        <ArcIcon icon={ArrowUpRight} size={14} strokeWidth={2} />
      </button>
    </article>
  )
}
