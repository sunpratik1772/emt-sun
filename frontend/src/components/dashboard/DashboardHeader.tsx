import { ArcIcon, Plus, Search } from '../../icons/arc'
import SherpaWelcomeMessage from '../SherpaWelcomeMessage'
import { commandPaletteShortcutLabel } from '../../store/commandPaletteStore'
import ThemeToggleButton from '../ThemeToggleButton'

export function DashboardWelcome() {
  return <SherpaWelcomeMessage variant="dashboard" />
}

export function DashboardSearchTrigger({ onClick }: { onClick?: () => void }) {
  const shortcut = commandPaletteShortcutLabel()
  return (
    <button
      type="button"
      className="dash-search-trigger"
      onClick={onClick}
      aria-label={`Search Studio commands (${shortcut})`}
    >
      <ArcIcon icon={Search} size={15} strokeWidth={2} className="dash-search-trigger__icon" />
      <span className="dash-search-trigger__label">Search Studio…</span>
      <kbd className="dash-search-trigger__kbd">{shortcut}</kbd>
    </button>
  )
}

export function DashboardHeaderTools({
  onSearchClick,
  onNewWorkflow,
}: {
  onSearchClick?: () => void
  onNewWorkflow?: () => void
}) {
  return (
    <div className="dash-header__tools">
      <DashboardSearchTrigger onClick={onSearchClick} />
      <ThemeToggleButton variant="dashboard" />
      <button type="button" className="dash-btn dash-btn--ghost dash-btn--sm" onClick={onNewWorkflow}>
        <ArcIcon icon={Plus} size={15} strokeWidth={2.2} />
        New workflow
      </button>
    </div>
  )
}
