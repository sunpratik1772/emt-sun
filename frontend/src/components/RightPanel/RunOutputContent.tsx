import { useMemo, useState } from 'react'
import { useStudioSectionStore } from '../../store/studioSectionStore'
import type { RunArtifact, RunLogEntry, RunResult } from '../../types'
import { ArcIcon, FileOutput, ChevronDown, ChevronRight, Download, FileText, Activity, Zap } from '../../icons/arc'
import { useWorkflowStore } from '../../store/workflowStore'
import { useNodeRegistryStore, UNKNOWN_NODE_UI, type NodeType } from '../../nodes'
import { Empty, SectionHeader } from './Shell'
import StepOutputView, { flattenRunOutput } from './StepOutputView'

function formatDuration(ms?: number): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

export function resolveDownloadHref(url: string): string {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/')) return url
  if (url.startsWith('/')) return `/api${url}`
  return `/api/${url}`
}

function KV({ k, v, vColor, bold, mono }: { k: string; v: string; vColor?: string; bold?: boolean; mono?: boolean }) {
  return (
    <span>
      <span style={{ color: 'var(--text-3)' }}>{k}: </span>
      <span className={mono ? 'num' : ''} style={{ color: vColor ?? 'var(--text-0)', fontWeight: bold ? 600 : 400 }}>
        {v}
      </span>
    </span>
  )
}

function StageOutput({ entry }: { entry: RunLogEntry }) {
  const out = entry.output
  return (
    <div className="space-y-2">
      {out?.disposition != null && (
        <div className="flex flex-wrap gap-x-3 gap-y-1" style={{ fontSize: 11 }}>
          <KV k="disposition" v={out.disposition || '—'} vColor="var(--accent)" bold />
          <KV k="flags" v={String(out.flag_count ?? 0)} vColor="var(--text-0)" bold />
          {out.output_branch && <KV k="branch" v={out.output_branch} mono />}
        </div>
      )}
      <StepOutputView output={entry.output} error={entry.error} nodeId={entry.node_id} />
      {entry.trace && entry.error && (
        <pre
          className="num p-2 rounded overflow-x-auto"
          style={{
            fontSize: 10,
            color: 'var(--text-2)',
            background: 'var(--bg-0)',
            border: '1px solid var(--border-soft)',
            maxHeight: 120,
          }}
        >
          {entry.trace}
        </pre>
      )}
    </div>
  )
}

function OutputCard({ entry, defaultOpen }: { entry: RunLogEntry; defaultOpen: boolean }) {
  const meta = useNodeRegistryStore((s) => s.nodeUI[entry.node_type as NodeType] ?? UNKNOWN_NODE_UI)
  const [open, setOpen] = useState(defaultOpen)
  const IconComp = meta.Icon
  const tone =
    entry.status === 'error' ? 'var(--danger)' :
    entry.status === 'running' ? 'var(--running)' :
    'var(--success)'

  return (
    <div
      className="rounded overflow-hidden"
      style={{
        background: 'var(--bg-1)',
        border: `1px solid color-mix(in srgb, ${tone} 22%, var(--border-soft))`,
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left"
        style={{ background: 'var(--bg-2)' }}
      >
        <span className="num" style={{ fontSize: 9.5, color: 'var(--text-3)', width: 16, textAlign: 'right' }}>
          {entry.index}
        </span>
        {IconComp && meta && (
          <span
            className="shrink-0 flex items-center justify-center rounded"
            style={{ width: 18, height: 18, background: `${meta.color}14`, color: meta.color }}
          >
            <IconComp size={11} strokeWidth={2} />
          </span>
        )}
        <div className="flex-1 min-w-0">
          <div className="truncate" style={{ fontSize: 11.5, color: 'var(--text-0)', fontWeight: 500 }}>
            {entry.label}
          </div>
        </div>
        <span className="num shrink-0" style={{ fontSize: 10.5, color: tone, fontWeight: 600 }}>
          {entry.status === 'running' ? 'running…' : formatDuration(entry.duration_ms)}
        </span>
        {open
          ? <ArcIcon icon={ChevronDown} size={12} style={{ color: 'var(--text-3)' }} />
          : <ArcIcon icon={ChevronRight} size={12} style={{ color: 'var(--text-3)' }} />}
      </button>
      {open && (
        <div className="px-2.5 py-2">
          <StageOutput entry={entry} />
        </div>
      )}
    </div>
  )
}

function pickDownloadUrl(
  result: { download_url?: string; report_path?: string } | null,
  runLog: RunLogEntry[],
): string | null {
  if (result?.download_url) return result.download_url
  if (result?.report_path) {
    const name = result.report_path.split('/').pop()
    if (name) return `/report/${name}`
  }
  for (let i = runLog.length - 1; i >= 0; i--) {
    const flat = flattenRunOutput(runLog[i]?.output)
    if (typeof flat?.download_url === 'string') return flat.download_url
  }
  return null
}

type ArtifactFilter = 'all' | 'csv' | 'excel' | 'file'

function classifyArtifactType(artifact: RunArtifact): Exclude<ArtifactFilter, 'all'> {
  const t = String(artifact.artifact_type || '').toLowerCase()
  const name = String(artifact.file_name || artifact.download_url || '').toLowerCase()
  if (t.includes('excel') || name.endsWith('.xlsx') || name.endsWith('.xls')) return 'excel'
  if (t.includes('csv') || name.endsWith('.csv')) return 'csv'
  return 'file'
}

function ArtifactSection({ artifacts }: { artifacts: RunArtifact[] }) {
  const [filter, setFilter] = useState<ArtifactFilter>('all')
  const filtered = useMemo(() => {
    if (filter === 'all') return artifacts
    return artifacts.filter((a) => classifyArtifactType(a) === filter)
  }, [artifacts, filter])

  if (!artifacts.length) return null

  return (
    <div className="px-4 pt-3 pb-2">
      <SectionHeader>Generated files</SectionHeader>
      <div className="flex flex-wrap gap-1.5 mt-2 mb-2">
        {(['all', 'csv', 'excel', 'file'] as const).map((flt) => (
          <button
            key={flt}
            type="button"
            onClick={() => setFilter(flt)}
            className="studio-chip"
            style={{
              cursor: 'pointer',
              opacity: filter === flt ? 1 : 0.65,
              borderColor: filter === flt ? 'var(--accent)' : undefined,
            }}
          >
            {flt.toUpperCase()}
          </button>
        ))}
      </div>
      <div className="space-y-1.5">
        {filtered.length === 0 ? (
          <div style={{ fontSize: 11.5, color: 'var(--text-2)' }}>No artifacts for this filter.</div>
        ) : filtered.map((artifact, idx) => {
          const href = artifact.download_url ? resolveDownloadHref(artifact.download_url) : null
          return (
            <div
              key={`${artifact.file_name || 'artifact'}-${idx}`}
              className="flex items-center justify-between gap-2 rounded"
              style={{
                border: '1px solid var(--border-soft)',
                padding: '8px 10px',
                background: 'var(--bg-0)',
              }}
            >
              <div className="min-w-0">
                <div className="font-mono truncate" style={{ fontSize: 11.5, color: 'var(--text-0)' }}>
                  {artifact.file_name || artifact.download_url || 'artifact'}
                </div>
                <div style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 2 }}>
                  {artifact.artifact_type || 'file'}
                  {artifact.source_node_id ? ` · ${artifact.source_node_id}` : ''}
                </div>
              </div>
              {href ? (
                <a href={href} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--accent)', whiteSpace: 'nowrap' }}>
                  Download
                </a>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function FinalResult({
  result,
  runLog,
  totalMs,
  showFooterNav = true,
}: {
  result: RunResult
  runLog: RunLogEntry[]
  totalMs: number | null
  showFooterNav?: boolean
}) {
  const currentWorkflow = useWorkflowStore((s) => s.workflow)
  const isAuto = result.workflow?.startsWith('[Auto]') || currentWorkflow?.name?.startsWith('[Auto]')
  const disp = result.disposition || 'COMPLETED'
  const tone =
    disp === 'ESCALATE' ? 'var(--danger)' :
    disp === 'REVIEW' ? 'var(--accent)' :
    'var(--success)'
  const downloadUrl = pickDownloadUrl(result, runLog)
  const downloadHref = downloadUrl ? resolveDownloadHref(downloadUrl) : null
  const sections = Object.entries(result.sections || {})

  return (
    <div className="px-4 py-4 space-y-3" style={{ borderTop: '1px solid var(--border)' }}>
      <SectionHeader>Final Output</SectionHeader>

      <div
        className="rounded-lg text-center"
        style={{
          padding: '12px 12px',
          background: `color-mix(in srgb, ${tone} 12%, var(--bg-1))`,
          border: `1px solid color-mix(in srgb, ${tone} 45%, transparent)`,
        }}
      >
        <div className="font-mono" style={{ fontSize: 18, fontWeight: 600, letterSpacing: '0.06em', color: tone }}>
          {disp}
        </div>
        <div className="font-mono mt-1" style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
          <span className="num" style={{ color: 'var(--text-1)' }}>{result.flag_count}</span> signal flags
          {totalMs != null && <> · <span className="num" style={{ color: 'var(--text-1)' }}>{formatDuration(totalMs)}</span></>}
        </div>
      </div>

      {downloadHref && (
        <a
          href={downloadHref}
          download={decodeURIComponent(downloadHref.split('/').pop() || 'report.xlsx')}
          target="_blank"
          rel="noopener"
          className="flex items-center justify-center gap-2 w-full rounded-lg"
          style={{
            padding: '9px 12px',
            fontSize: 12,
            fontWeight: 600,
            background: 'linear-gradient(180deg, var(--success) 0%, var(--success-lo) 100%)',
            color: '#FFFFFF',
            border: '1px solid color-mix(in srgb, var(--success-lo) 60%, black)',
            letterSpacing: '0.02em',
          }}
        >
          <ArcIcon icon={Download} size={13} strokeWidth={2.2} />
          <span>
            Download {downloadHref.toLowerCase().includes('.csv') ? 'CSV' : 'Excel'} Report
          </span>
        </a>
      )}

      {result.executive_summary && (
        <div>
          <div className="font-mono mb-1" style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            <FileText size={10} strokeWidth={2} style={{ display: 'inline', marginRight: 4, verticalAlign: '-1px' }} />
            Executive summary
          </div>
          <div
            className="rounded p-2.5 whitespace-pre-wrap"
            style={{
              fontSize: 11.5, color: 'var(--text-1)', lineHeight: 1.6,
              background: 'var(--bg-0)', border: '1px solid var(--border-soft)',
              maxHeight: 200, overflowY: 'auto',
            }}
          >
            {result.executive_summary}
          </div>
        </div>
      )}

      {result.datasets && result.datasets.length > 0 && (
        <div>
          <div className="font-mono mb-1" style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            Datasets · {result.datasets.length}
          </div>
          <div className="flex flex-wrap gap-1">
            {result.datasets.map((ds) => (
              <span
                key={ds}
                className="num rounded px-2 py-0.5"
                style={{
                  fontSize: 10.5, color: 'var(--info)',
                  background: 'color-mix(in srgb, var(--info) 10%, transparent)',
                  border: '1px solid color-mix(in srgb, var(--info) 25%, transparent)',
                }}
              >
                {ds}
              </span>
            ))}
          </div>
        </div>
      )}

      {sections.length > 0 && (
        <div className="space-y-1.5">
          <div className="font-mono" style={{ fontSize: 9.5, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
            Sections · {sections.length}
          </div>
          {sections.map(([name, sec]) => (
            <details
              key={name}
              className="rounded"
              style={{ background: 'var(--bg-0)', border: '1px solid var(--border-soft)' }}
            >
              <summary
                className="cursor-pointer px-2 py-1.5 num"
                style={{ fontSize: 11, color: 'var(--text-1)', fontWeight: 500 }}
              >
                {name.replace(/_/g, ' ')}
              </summary>
              <div className="px-2 pb-2">
                {Object.keys(sec.stats).length > 0 && (
                  <div className="mb-1.5" style={{ fontSize: 10, color: 'var(--text-3)' }}>
                    {Object.entries(sec.stats).map(([k, v]) => (
                      <span key={k} className="mr-3">
                        {k}: <span className="num" style={{ color: 'var(--text-1)' }}>{String(v)}</span>
                      </span>
                    ))}
                  </div>
                )}
                <p style={{ fontSize: 11, color: 'var(--text-1)', lineHeight: 1.55 }}>
                  {sec.narrative}
                </p>
              </div>
            </details>
          ))}
        </div>
      )}

      {showFooterNav && (
        <div className="pt-2 flex gap-2">
          <button
            type="button"
            onClick={() => {
              useStudioSectionStore.getState().setSection(isAuto ? 'automations' : 'run-history')
              useWorkflowStore.getState().setRightPanelMode(null)
            }}
            className="flex items-center justify-center gap-1.5 w-full rounded-lg lift"
            style={{
              padding: '8px 12px',
              fontSize: 11.5,
              fontWeight: 500,
              background: 'var(--bg-2)',
              color: 'var(--text-1)',
              border: '1px solid var(--border-soft)',
              cursor: 'pointer',
            }}
          >
            <ArcIcon icon={isAuto ? Zap : Activity} size={11} />
            <span>Open in {isAuto ? 'Automations' : 'Run History'}</span>
          </button>
        </div>
      )}
    </div>
  )
}

export interface RunOutputContentProps {
  runLog: RunLogEntry[]
  runResult: RunResult | null
  runError?: string | null
  runTotalMs?: number | null
  artifacts?: RunArtifact[]
  showFooterNav?: boolean
}

/** Shared output footer panel body — used live and in run-history modal. */
export function RunOutputContent({
  runLog,
  runResult,
  runError = null,
  runTotalMs = null,
  artifacts = [],
  showFooterNav = true,
}: RunOutputContentProps) {
  const finished = runLog.filter((e) => e.status !== 'running')
  const hasAnything = finished.length > 0 || !!runResult

  if (runError && !hasAnything) {
    return (
      <div className="flex flex-col items-center justify-center p-6 text-center">
        <div
          className="panel-glass max-w-md w-full"
          style={{
            padding: '24px',
            border: '1px solid var(--danger)',
            borderRadius: 12,
            background: 'color-mix(in srgb, var(--danger) 8%, var(--bg-1))',
          }}
        >
          <h3 className="display text-base font-semibold text-[var(--text-0)] mb-2">Execution Failed</h3>
          <p
            className="font-mono text-xs text-[var(--text-1)] whitespace-pre-wrap text-left p-3 rounded"
            style={{
              background: 'var(--bg-0)',
              border: '1px solid color-mix(in srgb, var(--danger) 20%, var(--border-soft))',
              maxHeight: 200,
              overflowY: 'auto',
              lineHeight: 1.5,
            }}
          >
            {runError}
          </p>
        </div>
      </div>
    )
  }

  if (!hasAnything) {
    return (
      <Empty>
        <ArcIcon icon={FileOutput} size={20} strokeWidth={1.6} style={{ color: 'var(--text-3)', marginBottom: 8 }} />
        <div style={{ color: 'var(--text-1)', fontWeight: 500, marginBottom: 4 }}>No stored output</div>
        <div>Run this workflow again to capture per-node payloads, or open a newer run.</div>
      </Empty>
    )
  }

  return (
    <>
      {runError && (
        <div
          className="px-4 py-3 flex items-center gap-3 shrink-0"
          style={{
            background: 'color-mix(in srgb, var(--danger) 10%, var(--bg-2))',
            borderBottom: '1px solid color-mix(in srgb, var(--danger) 30%, var(--border-soft))',
          }}
        >
          <span
            className="flex items-center justify-center rounded-full shrink-0"
            style={{
              width: 18,
              height: 18,
              background: 'var(--danger)',
              color: '#fff',
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            !
          </span>
          <div className="flex-1 min-w-0">
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--danger)' }}>Run execution terminated with errors</div>
            <div className="truncate font-mono text-[10.5px] text-[var(--text-1)] mt-0.5">{runError}</div>
          </div>
        </div>
      )}
      <ArtifactSection artifacts={artifacts} />
      <div className="px-4 pt-3 pb-2">
        <SectionHeader>Stage outputs</SectionHeader>
      </div>
      <div className="px-3 pb-3 space-y-2">
        {finished.map((e) => (
          <OutputCard
            key={`out:${e.node_id}:${e.index}`}
            entry={e}
            defaultOpen={e.status === 'error' || finished.length === 1}
          />
        ))}
      </div>
      {runResult && (
        <FinalResult
          result={runResult}
          runLog={runLog}
          totalMs={runTotalMs}
          showFooterNav={showFooterNav}
        />
      )}
    </>
  )
}
