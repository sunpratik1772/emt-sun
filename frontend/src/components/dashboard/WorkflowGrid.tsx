import { useMemo, useState } from 'react'
import { ArcIcon, Plus } from '../../icons/arc'
import type { DashboardWorkflow } from './types'
import WorkflowCard from './WorkflowCard'

type Filter = 'all' | 'drafts'

export default function WorkflowGrid({
  workflows,
  displayLimit = 4,
  minimal = false,
  onOpenWorkflow,
  onNewFromScratch,
  onNewFromTemplate,
  onViewAll,
}: {
  workflows: DashboardWorkflow[]
  displayLimit?: number
  minimal?: boolean
  onOpenWorkflow?: (workflow: DashboardWorkflow) => void
  onNewFromScratch?: () => void
  onNewFromTemplate?: () => void
  onViewAll?: () => void
}) {
  const [filter, setFilter] = useState<Filter>('all')

  const filtered = useMemo(() => {
    if (filter === 'drafts') return workflows.filter((w) => w.kind === 'draft')
    return workflows
  }, [workflows, filter])

  const visible = filtered.slice(0, displayLimit)
  const hasMore = filtered.length > displayLimit

  return (
    <section className={`dash-wf-section${minimal ? ' dash-wf-section--minimal' : ''}`}>
      <div className="dash-wf-section__head">
        <h2 className="dash-section-title">Recent workflows</h2>
        <div className="dash-wf-section__actions">
          {!minimal ? (
            <div className="dash-segment" role="tablist" aria-label="Workflow filter">
              <button
                type="button"
                role="tab"
                aria-selected={filter === 'all'}
                className={`dash-segment__btn${filter === 'all' ? ' dash-segment__btn--active' : ''}`}
                onClick={() => setFilter('all')}
              >
                All
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={filter === 'drafts'}
                className={`dash-segment__btn${filter === 'drafts' ? ' dash-segment__btn--active' : ''}`}
                onClick={() => setFilter('drafts')}
              >
                Drafts
              </button>
            </div>
          ) : null}
          {hasMore ? (
            <button type="button" className="dash-link-btn dash-link-btn--sm" onClick={onViewAll}>
              View all →
            </button>
          ) : null}
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="dash-empty">
          <p className="dash-empty__title">No workflows yet</p>
          <p className="dash-empty__body">Start from a blank canvas or browse templates.</p>
          <div className="dash-empty__actions">
            <button type="button" className="dash-btn dash-btn--primary" onClick={onNewFromScratch}>
              New workflow
            </button>
            <button type="button" className="dash-btn dash-btn--ghost" onClick={onNewFromTemplate}>
              Browse templates
            </button>
          </div>
        </div>
      ) : (
        <div className="dash-wf-grid">
          {visible.map((workflow, idx) => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              tintIndex={idx}
              onOpen={() => onOpenWorkflow?.(workflow)}
            />
          ))}
          {!minimal ? (
            <article className="dash-wf-card dash-wf-card--new">
              <div className="dash-wf-card--new__icon" aria-hidden>
                <ArcIcon icon={Plus} size={20} />
              </div>
              <p className="dash-wf-card--new__hint">Start a new workflow from scratch or a template.</p>
              <div className="dash-wf-card--new__links">
                <button type="button" className="dash-link-btn" onClick={onNewFromScratch}>
                  Blank canvas
                </button>
                <button type="button" className="dash-link-btn" onClick={onNewFromTemplate}>
                  Templates
                </button>
              </div>
            </article>
          ) : null}
        </div>
      )}
    </section>
  )
}
