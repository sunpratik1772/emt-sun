import { useMemo, useState } from 'react'
import {
  ArcIcon,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  FileSpreadsheet,
  XCircle,
} from '../icons/arc'
import type { RunLogSummary as RunLog } from '../services/api'
import type { HydratedRunOutput } from '../lib/runHistoryOutput'
import { generateStepsForRun } from './drawers/runHistoryUtils'
import { formatDur, formatTime, statusColor } from './drawers/shared'
import { resolveDownloadHref } from './RightPanel/RunOutputContent'

function truncateRunId(id: string): string {
  if (id.length <= 16) return id
  return `${id.slice(0, 7)}…${id.slice(-5)}`
}

function statusLabel(status: string): string {
  if (status === 'success') return 'success'
  if (status === 'error') return 'failed'
  if (status === 'running') return 'running'
  return status
}

export default function RunDetailBody({
  run,
  hydrated,
}: {
  run: RunLog
  hydrated: HydratedRunOutput
}) {
  const [expandedStep, setExpandedStep] = useState<string | null>(() => {
    const steps = generateStepsForRun(run)
    return steps[0]?.id ?? null
  })

  const steps = useMemo(() => generateStepsForRun(run), [run])
  const tone = statusColor(run.status)

  const downloadHref = useMemo(() => {
    if (run.download_url) return resolveDownloadHref(run.download_url)
    const artifact = hydrated.artifacts?.[0]
    if (artifact?.download_url) return resolveDownloadHref(artifact.download_url)
    return null
  }, [run.download_url, hydrated.artifacts])

  const fileMeta = useMemo(() => {
    const artifact = hydrated.artifacts?.[0]
    if (!artifact) return null
    const type = (artifact.artifact_type || 'file').toLowerCase()
    const name = artifact.file_name || artifact.download_url?.split('/').pop() || 'report'
    return { name, type, href: artifact.download_url ? resolveDownloadHref(artifact.download_url) : null }
  }, [hydrated.artifacts])

  const dispositionChip = run.disposition
    ? `${run.disposition}${hydrated.artifacts?.length ? ` · ${hydrated.artifacts.length} file` : ''}`
    : hydrated.artifacts?.length
      ? `${hydrated.artifacts[0]?.artifact_type || 'file'} · ${hydrated.artifacts.length} file`
      : null

  const kv: [string, string, boolean?][] = [
    ['Run ID', run.run_id, true],
    ['Duration', formatDur(run.duration_ms)],
    ['Started', formatTime(run.started_at)],
    ['Finished', run.finished_at ? formatTime(run.finished_at) : '—'],
    ['Nodes Count', String(run.node_count ?? '—')],
    ['Edges Count', String(run.edge_count ?? '—')],
  ]

  return (
    <>
      <div className="rd-statusrow">
        <span className="rd-statusbadge" style={{ color: tone }}>
          <span className="rd-statusicon" style={{ background: tone }}>
            <ArcIcon icon={run.status === 'error' ? XCircle : Check} size={13} strokeWidth={2.5} />
          </span>
          {statusLabel(run.status)}
        </span>
        {dispositionChip ? <span className="rd-mono-chip">{dispositionChip}</span> : null}
      </div>

      <div className="rd-kv-grid">
        {kv.map(([k, v, mono]) => (
          <div key={k}>
            <div className="rd-kv__k">{k}</div>
            <div className="rd-kv__v">{mono ? <code>{v}</code> : v}</div>
          </div>
        ))}
      </div>

      {(fileMeta || downloadHref) && (
        <>
          <div className="rd-seclabel">Generated files</div>
          <div className="rd-file">
            <span className="rd-file__ico">
              <ArcIcon icon={FileSpreadsheet} size={17} strokeWidth={2} />
            </span>
            <div style={{ minWidth: 0 }}>
              <div className="rd-file__name">{fileMeta?.name ?? 'Download report'}</div>
              <div className="rd-file__meta">{fileMeta?.type ?? 'output'}</div>
            </div>
            {(fileMeta?.href || downloadHref) && (
              <a className="rd-file__dl" href={fileMeta?.href || downloadHref || '#'} download target="_blank" rel="noreferrer">
                <ArcIcon icon={Download} size={13} strokeWidth={2} />
                Download
              </a>
            )}
          </div>
        </>
      )}

      {run.run_error && (
        <div
          style={{
            padding: '12px 14px',
            borderRadius: 9,
            marginBottom: 20,
            background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
            border: '1px solid color-mix(in srgb, var(--danger) 28%, transparent)',
            color: 'var(--danger)',
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          {run.run_error}
        </div>
      )}

      <div className="rd-seclabel">Step-by-step node execution</div>
      <div className="rd-steps">
        <div className="rd-track" aria-hidden />
        {steps.map((step) => {
          const isOpen = expandedStep === step.id
          const stepTone = step.status === 'error' ? 'var(--danger)' : 'var(--success)'
          return (
            <div key={step.id} style={{ position: 'relative', zIndex: 1 }}>
              <div
                className="rd-step"
                onClick={() => setExpandedStep(isOpen ? null : step.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setExpandedStep(isOpen ? null : step.id)
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <span className="rd-step__dot" style={{ background: stepTone }}>
                  <ArcIcon icon={step.status === 'error' ? XCircle : Check} size={11} strokeWidth={2.5} />
                </span>
                <span className="rd-step__name">{step.label}</span>
                <span className="rd-step__type">{step.type}</span>
                <span className="rd-step__ms">{step.duration_ms}ms</span>
                <span className="rd-step__chev">
                  <ArcIcon icon={isOpen ? ChevronDown : ChevronRight} size={13} strokeWidth={2} />
                </span>
              </div>
              {isOpen && (
                <div className="rd-step-detail">
                  <div style={{ marginBottom: 4 }}>
                    Step status:{' '}
                    <b style={{ color: stepTone }}>{step.status === 'error' ? 'Error' : 'Success'}</b>
                  </div>
                  {step.output_preview}
                  {step.error ? (
                    <div style={{ marginTop: 8, color: 'var(--danger)' }}>{step.error}</div>
                  ) : null}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {hydrated.runError && !run.run_error && (
        <div className="rd-step-detail" style={{ marginTop: 12 }}>
          {hydrated.runError}
        </div>
      )}
    </>
  )
}

export { truncateRunId }
