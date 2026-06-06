import { ArcIcon, ChevronRight, Zap } from '../../icons/arc'
import { automationDeepLink, openAutomation } from '../../lib/studioNavigation'

export function CopilotAutomationLink({
  id,
  name,
  scheduleSummary,
}: {
  id: string
  name: string
  scheduleSummary?: string
}) {
  const href = automationDeepLink(id)

  return (
    <a
      href={href}
      onClick={(e) => {
        e.preventDefault()
        openAutomation(id)
      }}
      className="group block no-underline mt-3"
      style={{ color: 'inherit' }}
    >
      <div
        className="rounded-lg transition-colors duration-150"
        style={{
          padding: '10px 12px',
          background: 'var(--bg-1)',
          border: '1px solid var(--border-soft)',
          boxShadow: '0 1px 0 color-mix(in srgb, var(--border) 40%, transparent)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'color-mix(in srgb, var(--accent) 28%, var(--border))'
          e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 4%, var(--bg-1))'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'var(--border-soft)'
          e.currentTarget.style.background = 'var(--bg-1)'
        }}
      >
        <div
          className="font-mono mb-1.5"
          style={{
            fontSize: 9,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--text-3)',
            fontWeight: 600,
          }}
        >
          Automation created
        </div>
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="flex items-center justify-center shrink-0 rounded-md"
            style={{
              width: 22,
              height: 22,
              background: 'color-mix(in srgb, var(--accent) 10%, transparent)',
              color: 'var(--accent)',
            }}
          >
            <ArcIcon icon={Zap} size={12} strokeWidth={2} />
          </span>
          <div className="flex-1 min-w-0">
            <div
              className="truncate"
              style={{
                fontSize: 12.5,
                fontWeight: 560,
                color: 'var(--text-0)',
                letterSpacing: '-0.01em',
              }}
            >
              Automation: {name}
            </div>
            {scheduleSummary ? (
              <div className="truncate" style={{ fontSize: 10.5, color: 'var(--text-2)', marginTop: 2 }}>
                {scheduleSummary}
              </div>
            ) : null}
          </div>
          <ArcIcon
            icon={ChevronRight}
            size={14}
            className="shrink-0 transition-transform duration-150 group-hover:translate-x-0.5"
            style={{ color: 'var(--text-3)' }}
          />
        </div>
      </div>
    </a>
  )
}
