/**
 * Narrow icon rail — Config, Run Logs, Agent, Output.
 * Uniform Arc icons (17px); panel titles match via Shell.
 */
import { ArcIcon, Activity, Bot, FileOutput, Settings2 } from '../icons/arc'
import { useWorkflowStore } from '../store/workflowStore'

const RAIL_ICON_SIZE = 17

const ITEMS = [
  { mode: 'config' as const, title: 'Config', icon: Settings2 },
  { mode: 'runlog' as const, title: 'Run Logs', icon: Activity },
  { mode: 'copilot' as const, title: 'Agent', icon: Bot },
  { mode: 'output' as const, title: 'Output', icon: FileOutput },
]

export default function ActivityRail() {
  const mode = useWorkflowStore((s) => s.rightPanelMode)
  const toggle = useWorkflowStore((s) => s.toggleRightPanelMode)

  return (
    <div
      className="activity-rail panel-glass flex flex-col items-center py-3 gap-1 shrink-0"
      style={{
        width: 44,
        borderLeft: '1px solid var(--border)',
      }}
    >
      {ITEMS.map((item) => (
        <RailButton
          key={item.mode}
          active={mode === item.mode}
          onClick={() => toggle(item.mode)}
          title={item.title}
          icon={<ArcIcon icon={item.icon} size={RAIL_ICON_SIZE} />}
        />
      ))}
    </div>
  )
}

function RailButton({
  icon,
  active,
  backgroundStreaming,
  onClick,
  title,
}: {
  icon: React.ReactNode
  active: boolean
  backgroundStreaming?: boolean
  onClick: () => void
  title: string
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      aria-pressed={active}
      className="activity-rail__btn relative flex items-center justify-center"
      style={{
        width: 34,
        height: 34,
        borderRadius: 8,
        background: active ? 'var(--bg-0)' : 'transparent',
        color: active ? 'var(--text-0)' : 'var(--text-3)',
        border: active ? '1px solid var(--border-strong)' : '1px solid transparent',
        cursor: 'pointer',
        transition:
          'background 140ms var(--ease-out), color 140ms var(--ease-out), border-color 140ms var(--ease-out)',
      }}
      onMouseEnter={(e) => {
        if (!active) (e.currentTarget as HTMLElement).style.color = 'var(--text-1)'
      }}
      onMouseLeave={(e) => {
        if (!active) (e.currentTarget as HTMLElement).style.color = 'var(--text-3)'
      }}
    >
      {icon}
      {backgroundStreaming && (
        <span
          aria-hidden
          className="copilot-rail-pulse"
          style={{
            position: 'absolute',
            top: 4,
            right: 4,
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'var(--accent)',
          }}
        />
      )}
      {active && (
        <span
          aria-hidden
          style={{
            position: 'absolute',
            left: -8,
            top: 6,
            bottom: 6,
            width: 2,
            borderRadius: 2,
            background: 'var(--accent)',
          }}
        />
      )}
    </button>
  )
}
