import DashboardSidebar from './DashboardSidebar'
import DashboardBody from './DashboardBody'
import type { DashboardShellProps } from './types'
import '../../styles/dashboard.css'

export default function DashboardShell({
  variant = 'full',
  preview = false,
  stats,
  workflows,
  runHealth,
  activeNavId = 'dashboard',
  onNavClick,
  onNewWorkflow,
  onOpenWorkflow,
  onNewFromScratch,
  onNewFromTemplate,
  onViewAllRuns,
  onViewAllWorkflows,
  onSearchClick,
  onSherpaPrompt,
}: DashboardShellProps) {
  const rootClass = [
    'dash',
    preview ? 'dash--preview' : '',
    variant === 'content' ? 'dash--content-only' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const body = (
    <DashboardBody
      stats={stats}
      workflows={workflows}
      runHealth={runHealth}
      onOpenWorkflow={preview ? undefined : onOpenWorkflow}
      onNewFromScratch={preview ? undefined : onNewFromScratch}
      onNewFromTemplate={preview ? undefined : onNewFromTemplate}
      onViewAllRuns={preview ? undefined : onViewAllRuns}
      onViewAllWorkflows={preview ? undefined : onViewAllWorkflows}
      onSherpaPrompt={preview ? undefined : onSherpaPrompt}
      onSearchClick={preview ? undefined : onSearchClick}
      onNewWorkflow={preview ? undefined : onNewWorkflow}
    />
  )

  if (variant === 'content') {
    return (
      <div className={rootClass}>
        <div className="dash-main">{body}</div>
      </div>
    )
  }

  return (
    <div className={rootClass}>
      <DashboardSidebar
        activeNavId={activeNavId}
        onNavClick={onNavClick}
        onNewWorkflow={onNewWorkflow}
      />
      <div className="dash-main">{body}</div>
    </div>
  )
}

export {
  LayoutGrid,
  LayoutTemplate,
  Boxes,
  Database,
  UserRound,
  Settings,
} from '../../icons/arc'
