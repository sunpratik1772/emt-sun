import StatRow from './StatRow'
import WorkflowGrid from './WorkflowGrid'
import RunHealthCard from './RunHealthCard'
import RunActivityCard from './RunActivityCard'
import SherpaPromptBar from './SherpaPromptBar'
import { DashboardSherpaProvider } from './DashboardSherpaContext'
import { DashboardWelcome, DashboardHeaderTools } from './DashboardHeader'
import type { DashboardShellProps } from './types'

export default function DashboardBody({
  stats,
  workflows,
  runHealth,
  onOpenWorkflow,
  onNewFromScratch,
  onNewFromTemplate,
  onViewAllRuns,
  onViewAllWorkflows,
  onSherpaPrompt,
  onSearchClick,
  onNewWorkflow,
}: Pick<
  DashboardShellProps,
  | 'stats'
  | 'workflows'
  | 'runHealth'
  | 'onOpenWorkflow'
  | 'onNewFromScratch'
  | 'onNewFromTemplate'
  | 'onViewAllRuns'
  | 'onViewAllWorkflows'
  | 'onSherpaPrompt'
  | 'onSearchClick'
  | 'onNewWorkflow'
>) {
  return (
    <DashboardSherpaProvider>
      <div className="dash-body">
        <div className="dash-body__inner">
          <header className="dash-header">
            <DashboardWelcome />
            <DashboardHeaderTools onSearchClick={onSearchClick} onNewWorkflow={onNewWorkflow} />
          </header>

          <SherpaPromptBar onSubmit={onSherpaPrompt} />

          <div className="dash-content">
            <StatRow stats={stats} />

            <div className="dash-insight-row">
              <RunHealthCard health={runHealth} />
              <RunActivityCard calendar={runHealth.calendar} onViewRuns={onViewAllRuns} />
            </div>

            {workflows.length > 0 ? (
              <WorkflowGrid
                workflows={workflows}
                displayLimit={3}
                minimal
                onOpenWorkflow={onOpenWorkflow}
                onNewFromScratch={onNewFromScratch}
                onNewFromTemplate={onNewFromTemplate}
                onViewAll={onViewAllWorkflows}
              />
            ) : null}
          </div>
        </div>
      </div>
    </DashboardSherpaProvider>
  )
}
