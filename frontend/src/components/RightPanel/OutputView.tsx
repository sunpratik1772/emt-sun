/**
 * Post-run output view in the right panel (side layout) or embedded in the bottom dock.
 *
 * Shows a refreshed canvas node list after save / Sherpa edits, plus per-stage run
 * payloads when a workflow has executed.
 */
import { ArcIcon, Columns, FileOutput, Split } from '../../icons/arc'
import { useWorkflowStore } from '../../store/workflowStore'
import Shell from './Shell'
import CanvasNodesSummaryFromStore from './CanvasNodesSummary'
import { RunOutputContent } from './RunOutputContent'

export default function OutputView({ embedded = false }: { embedded?: boolean }) {
  const isRunning = useWorkflowStore((s) => s.isRunning)
  const runLog = useWorkflowStore((s) => s.runLog)
  const runResult = useWorkflowStore((s) => s.runResult)
  const runError = useWorkflowStore((s) => s.runError)
  const runTotalMs = useWorkflowStore((s) => s.runTotalMs)
  const outputSummarySource = useWorkflowStore((s) => s.outputSummarySource)
  const outputOrientation = useWorkflowStore((s) => s.outputOrientation)
  const toggleOutputOrientation = useWorkflowStore((s) => s.toggleOutputOrientation)

  const hasRunOutput =
    isRunning || runLog.length > 0 || !!runResult || !!runError

  const orientationToggle = !embedded ? (
    <button
      type="button"
      onClick={toggleOutputOrientation}
      title={outputOrientation === 'bottom' ? 'Dock output on the right' : 'Dock output at the bottom'}
      aria-label={outputOrientation === 'bottom' ? 'Dock output on the right' : 'Dock output at the bottom'}
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
      <ArcIcon icon={outputOrientation === 'bottom' ? Columns : Split} size={12} strokeWidth={2} />
    </button>
  ) : null

  const body = (
    <>
      <CanvasNodesSummaryFromStore />
      {hasRunOutput && (
        <div style={{ borderTop: '1px solid var(--border-soft)' }}>
          <RunOutputContent
            runLog={runLog}
            runResult={runResult}
            runError={runError}
            runTotalMs={runTotalMs}
          />
        </div>
      )}
    </>
  )

  if (embedded) return body

  const eyebrow = isRunning ? 'STREAMING' : outputSummarySource === 'save' ? 'SAVED' : outputSummarySource === 'copilot' ? 'SHERPA' : hasRunOutput ? 'RESULT' : 'CANVAS'

  return (
    <Shell
      icon={FileOutput}
      title="Output"
      eyebrow={eyebrow}
      accent="var(--success)"
      rightSlot={orientationToggle}
      subtitle="Canvas nodes after save or Sherpa, plus per-stage results when you run."
    >
      {body}
    </Shell>
  )
}
