import { createPortal } from 'react-dom'
import StudioOverlay from './StudioOverlay'
import { ArcIcon, Download, FileOutput } from '../icons/arc'
import type { RunLogSummary as RunLog } from '../services/api'
import type { HydratedRunOutput } from '../lib/runHistoryOutput'
import { formatTime } from './drawers/shared'
import RunDetailBody, { truncateRunId } from './RunDetailBody'
import { resolveDownloadHref } from './RightPanel/RunOutputContent'

interface RunOutputModalProps {
  run: RunLog
  hydrated: HydratedRunOutput
  onClose: () => void
  onOpenInOutputPanel: (run: RunLog) => void
}

/** Opaque full-surface run detail — matches Design System-8 run-detail overlay. */
export default function RunOutputModal({
  run,
  hydrated,
  onClose,
  onOpenInOutputPanel,
}: RunOutputModalProps) {
  const downloadHref = run.download_url
    ? resolveDownloadHref(run.download_url)
    : hydrated.artifacts?.[0]?.download_url
      ? resolveDownloadHref(hydrated.artifacts[0].download_url)
      : null

  const subtitle = `Generated ${formatTime(run.started_at)} · workflow run summary and step-by-step execution.`

  return createPortal(
    <StudioOverlay
      open
      onClose={onClose}
      host="viewport"
      eyebrow="Run output"
      title={run.workflow ?? run.run_id}
      subtitle={subtitle}
      ariaLabel="Run output"
      footLeft={
        <>
          {downloadHref ? (
            <a className="ov-bbtn ov-bbtn--primary" href={downloadHref} download target="_blank" rel="noreferrer">
              <ArcIcon icon={Download} size={14} strokeWidth={2} />
              Download report
            </a>
          ) : (
            <button type="button" className="ov-bbtn ov-bbtn--primary" disabled>
              <ArcIcon icon={Download} size={14} strokeWidth={2} />
              Download report
            </button>
          )}
          <button
            type="button"
            className="ov-bbtn"
            data-testid="run-output-open-panel-button"
            onClick={() => onOpenInOutputPanel(run)}
          >
            <ArcIcon icon={FileOutput} size={14} strokeWidth={2} />
            View output
          </button>
        </>
      }
      footRight={
        <span className="ov__foot-meta">
          <span className="rd-mono-chip">{truncateRunId(run.run_id)}</span>
          <span className="ov__kbd">
            <kbd>esc</kbd> to close
          </span>
        </span>
      }
    >
      <RunDetailBody run={run} hydrated={hydrated} />
    </StudioOverlay>,
    document.body,
  )
}
