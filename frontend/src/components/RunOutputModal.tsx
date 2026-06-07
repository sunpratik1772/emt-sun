import { useEffect, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { ArcIcon, Download, FileOutput, X as XIcon } from '../icons/arc'
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
  const resolvedDownloadHref = useMemo(() => {
    if (run.download_url) return resolveDownloadHref(run.download_url)
    const artifactUrl = hydrated.artifacts?.[0]?.download_url
    if (artifactUrl) return resolveDownloadHref(artifactUrl)
    
    try {
      const blob = new Blob([JSON.stringify({ run, hydrated }, null, 2)], { type: 'application/json' })
      return URL.createObjectURL(blob)
    } catch (e) {
      return null
    }
  }, [run, hydrated])

  const downloadFileName = useMemo(() => {
    if (run.download_url) return undefined
    const artifactName = hydrated.artifacts?.[0]?.file_name
    if (artifactName) return artifactName
    return `run_artifact_${run.run_id}.json`
  }, [run, hydrated])

  useEffect(() => {
    return () => {
      if (resolvedDownloadHref && resolvedDownloadHref.startsWith('blob:')) {
        URL.revokeObjectURL(resolvedDownloadHref)
      }
    }
  }, [resolvedDownloadHref])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const subtitle = `Generated ${formatTime(run.started_at)} · workflow run summary and step-by-step execution.`

  return createPortal(
    <div
      className="fixed inset-0 z-[150] flex items-center justify-center p-4 select-text"
      style={{
        background: 'rgba(3, 6, 11, 0.55)',
        backdropFilter: 'blur(4px)',
        WebkitBackdropFilter: 'blur(4px)',
      }}
      role="dialog"
      aria-modal="true"
      aria-label={run.workflow ?? run.run_id}
    >
      <button
        type="button"
        className="absolute inset-0 w-full h-full bg-transparent cursor-default border-none outline-none"
        onClick={onClose}
        aria-label="Close"
      />

      <div
        className="panel-glass relative flex flex-col w-full"
        style={{
          width: 580,
          maxWidth: '100%',
          maxHeight: 'min(760px, calc(100vh - 32px))',
          borderRadius: 16,
          border: '1px solid var(--border)',
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.45)',
          background: 'var(--chrome-elevated)',
        }}
      >
        {/* Header */}
        <div
          className="shrink-0 flex items-start justify-between px-6 py-5"
          style={{ borderBottom: '1px solid var(--border-soft)' }}
        >
          <div className="min-w-0 pr-6">
            <div className="eyebrow" style={{ color: 'var(--text-3)', marginBottom: 4 }}>
              Run Output
            </div>
            <h2
              className="display truncate"
              style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-0)', margin: 0 }}
            >
              {run.workflow ?? run.run_id}
            </h2>
            <p className="text-[12px] leading-relaxed mt-1" style={{ color: 'var(--text-3)', margin: 0 }}>
              {subtitle}
            </p>
          </div>
          <button
            type="button"
            className="lift flex items-center justify-center shrink-0"
            onClick={onClose}
            aria-label="Close"
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: 'transparent',
              color: 'var(--text-2)',
              border: '1px solid var(--border-soft)',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-2)'
              e.currentTarget.style.color = 'var(--text-0)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = 'var(--text-2)'
            }}
          >
            <ArcIcon icon={XIcon} size={14} />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 min-h-0">
          <RunDetailBody run={run} hydrated={hydrated} />
        </div>

        {/* Footer */}
        <div
          className="shrink-0 flex items-center justify-between px-6 py-4"
          style={{
            borderTop: '1px solid var(--border-soft)',
            background: 'color-mix(in srgb, var(--chrome-elevated) 96%, black)',
            borderBottomLeftRadius: 15,
            borderBottomRightRadius: 15,
          }}
        >
          {/* Footer Left: Metadata */}
          <div className="flex items-center gap-3" style={{ fontSize: 11.5, color: 'var(--text-2)' }}>
            <span className="rd-mono-chip">{truncateRunId(run.run_id)}</span>
            <span className="ov__kbd">
              <kbd>esc</kbd> to close
            </span>
          </div>

          {/* Footer Right: Buttons */}
          <div className="flex items-center gap-2">
            {resolvedDownloadHref ? (
              <a
                className="ov-bbtn"
                href={resolvedDownloadHref}
                download={downloadFileName}
                target="_blank"
                rel="noreferrer"
              >
                <ArcIcon icon={Download} size={14} strokeWidth={2} />
                Download report
              </a>
            ) : (
              <button type="button" className="ov-bbtn" disabled>
                <ArcIcon icon={Download} size={14} strokeWidth={2} />
                Download report
              </button>
            )}
            <button
              type="button"
              className="ov-bbtn ov-bbtn--primary"
              data-testid="run-output-open-panel-button"
              onClick={() => onOpenInOutputPanel(run)}
            >
              <ArcIcon icon={FileOutput} size={14} strokeWidth={2} />
              View actual run
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
