import { useRef, useState } from 'react'
import { ArcIcon, FileOutput, Maximize2, Minimize2, X as XIcon, Activity, Zap, Columns, Split } from '../icons/arc'
import ResizeHandle from './ResizeHandle'
import OutputView from './RightPanel/OutputView'
import { useWorkflowStore } from '../store/workflowStore'
import { useStudioSectionStore } from '../store/studioSectionStore'

const OUTPUT_MIN_HEIGHT = 170
const OUTPUT_DEFAULT_HEIGHT = 300

function clampHeight(px: number): number {
  const max = Math.max(OUTPUT_MIN_HEIGHT, window.innerHeight - 110)
  return Math.max(OUTPUT_MIN_HEIGHT, Math.min(max, Math.round(px)))
}

export default function BottomOutputPanel() {
  const setMode = useWorkflowStore((s) => s.setRightPanelMode)
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const runResult = useWorkflowStore((s) => s.runResult)
  const runLog = useWorkflowStore((s) => s.runLog)
  const outputOrientation = useWorkflowStore((s) => s.outputOrientation)
  const toggleOrientation = useWorkflowStore((s) => s.toggleOutputOrientation)
  
  const panelRef = useRef<HTMLDivElement>(null)
  const [height, setHeight] = useState(OUTPUT_DEFAULT_HEIGHT)
  const [maxed, setMaxed] = useState(false)

  const isAuto = (runResult as any)?.workflow?.startsWith('[Auto]') || useWorkflowStore.getState().workflow?.name?.startsWith('[Auto]')

  return (
    <div
      ref={panelRef}
      className="panel-glass relative shrink-0 flex flex-col min-h-0"
      style={{
        height: maxed ? `calc(100vh - 96px)` : height,
        borderTop: '1px solid var(--border)',
        width: '100%',
      }}
    >
      <ResizeHandle
        edge="top"
        ariaLabel="Resize output panel height"
        onResize={(clientY) => {
          const bottom = panelRef.current?.getBoundingClientRect().bottom ?? window.innerHeight
          setMaxed(false)
          setHeight(clampHeight(bottom - clientY))
        }}
      />
      <div
        className="px-4 py-2 shrink-0 flex items-center gap-2"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <ArcIcon icon={FileOutput} size={15} style={{ color: 'var(--success)' }} />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-0)' }}>Output</span>
        <span
          className="font-mono"
          style={{ fontSize: 10, letterSpacing: '0.16em', color: 'var(--text-3)', textTransform: 'uppercase' }}
        >
          {isRunning ? 'STREAMING' : 'RESULTS'}
        </span>
        <div className="flex-1" />
        {!isRunning && (runResult || runLog.length > 0) && (
          <button
            type="button"
            onClick={() => {
              useStudioSectionStore.getState().setSection(isAuto ? 'automations' : 'run-history')
              setMode(null)
            }}
            title={isAuto ? "Open in Automations" : "Open in Run History"}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md lift"
            style={{
              fontSize: 11,
              fontWeight: 500,
              background: 'var(--bg-3)',
              color: 'var(--text-1)',
              border: '1px solid var(--border-soft)',
              cursor: 'pointer',
              marginRight: 6,
            }}
          >
            <ArcIcon icon={isAuto ? Zap : Activity} size={11} />
            <span>Open in {isAuto ? "Automations" : "Run History"}</span>
          </button>
        )}
        <button
          type="button"
          onClick={toggleOrientation}
          title={outputOrientation === 'bottom' ? 'Split side-by-side' : 'Split top-down'}
          aria-label={outputOrientation === 'bottom' ? 'Split side-by-side' : 'Split top-down'}
          className="flex items-center justify-center"
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            background: 'transparent',
            color: 'var(--text-2)',
            border: '1px solid var(--border-soft)',
            cursor: 'pointer',
            marginRight: 4,
          }}
        >
          <ArcIcon icon={outputOrientation === 'bottom' ? Columns : Split} size={12} strokeWidth={2} />
        </button>
        <button
          type="button"
          onClick={() => setMaxed((v) => !v)}
          title={maxed ? 'Restore output panel height' : 'Expand output panel'}
          aria-label={maxed ? 'Restore output panel height' : 'Expand output panel'}
          className="flex items-center justify-center"
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            background: 'transparent',
            color: 'var(--text-2)',
            border: '1px solid var(--border-soft)',
            cursor: 'pointer',
            marginRight: 4,
          }}
        >
          {maxed ? <Minimize2 size={12} strokeWidth={2} /> : <Maximize2 size={12} strokeWidth={2} />}
        </button>
        <button
          type="button"
          onClick={() => setMode(null)}
          title="Close output panel"
          aria-label="Close output panel"
          className="flex items-center justify-center"
          style={{
            width: 24,
            height: 24,
            borderRadius: 6,
            background: 'transparent',
            color: 'var(--text-2)',
            border: '1px solid var(--border-soft)',
            cursor: 'pointer',
          }}
        >
          <ArcIcon icon={XIcon} size={12} />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <OutputView embedded />
      </div>
    </div>
  )
}
