import BrandMark from '../BrandMark'
import { ArcIcon, Plus } from '../../icons/arc'
import { PREVIEW_NAV } from './mockData'
import type { DashboardNavItem } from './types'

export default function DashboardSidebar({
  activeNavId,
  onNavClick,
  onNewWorkflow,
}: {
  activeNavId: string
  onNavClick?: (id: string) => void
  onNewWorkflow?: () => void
}) {
  return (
    <aside className="dash-sidebar">
      <div className="dash-sidebar__brand">
        <BrandMark size={22} />
        <div className="dash-sidebar__brand-text">
          <span className="dash-sidebar__brand-name">dbSherpa Studio</span>
        </div>
      </div>
      <button type="button" className="dash-sidebar__cta" onClick={onNewWorkflow}>
        <ArcIcon icon={Plus} size={13} />
        New workflow
      </button>
      <nav className="dash-sidebar__nav" aria-label="Dashboard">
        {PREVIEW_NAV.map((item: DashboardNavItem) => {
          const active = item.id === activeNavId
          return (
            <button
              key={item.id}
              type="button"
              className={`dash-nav-item${active ? ' dash-nav-item--active' : ''}`}
              onClick={() => onNavClick?.(item.id)}
            >
              <ArcIcon icon={item.icon} size={14} />
              {item.label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
