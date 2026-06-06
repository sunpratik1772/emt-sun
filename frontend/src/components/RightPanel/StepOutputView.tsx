/**
 * Per-node output viewer — smart field lines, inline tables, logs, raw JSON fallback.
 */
import { useMemo } from 'react'
import { ArcIcon, AlertTriangle, Download } from '../../icons/arc'
import type { RunLogEntry } from '../../types'
import HumanReadableOutput from './HumanReadableOutput'
import { analyzeStructuredOutput } from './outputFormatUtils'

function resolveDownloadHref(url: string): string {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/')) return url
  if (url.startsWith('/')) return `/api${url}`
  return `/api/${url}`
}

interface Props {
  output: RunLogEntry['output']
  error?: string | null
  nodeId?: string
}

function parseCsvText(text: string): Record<string, unknown>[] {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length < 2) return []
  const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''))
  const rows: Record<string, unknown>[] = []
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue
    const cells = line.match(/("([^"]|"")*"|[^,]*)/g) ?? line.split(',')
    const obj: Record<string, unknown> = {}
    headers.forEach((h, i) => {
      let v = (cells[i] ?? '').trim()
      if (v.startsWith('"') && v.endsWith('"')) v = v.slice(1, -1).replace(/""/g, '"')
      obj[h] = v
    })
    rows.push(obj)
  }
  return rows
}

export function pickRows(output: Record<string, unknown> | undefined): unknown[] | null {
  if (!output) return null
  const analyzed = analyzeStructuredOutput(output)
  if (analyzed.tables.length > 0) return analyzed.tables[0].rows
  if (Array.isArray(output.rows) && output.rows.length > 0) return output.rows
  if (typeof output.csv === 'string' && output.csv.trim()) {
    const parsed = parseCsvText(output.csv)
    if (parsed.length) return parsed
  }
  return null
}

export function pickLogs(output: Record<string, unknown> | undefined): string[] | null {
  if (!output) return null
  if (Array.isArray(output.logs)) return output.logs.map(String)
  if (typeof output.message === 'string') return [output.message]
  if (typeof output.response === 'string') return [output.response]
  if (typeof output.agent_response === 'string') return [output.agent_response]
  return null
}

/** Flatten RunLogEntry.output into a single object for StepOutputView. */
export function flattenRunOutput(
  out: RunLogEntry['output'] | undefined,
  nodeId?: string,
): Record<string, unknown> | undefined {
  if (!out) return undefined
  const ctx = out.context
  if (ctx && nodeId) {
    const key = `${nodeId}_output`
    const raw = ctx[key]
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      return raw as Record<string, unknown>
    }
  }
  if (out.node_output && typeof out.node_output === 'object') {
    return out.node_output as Record<string, unknown>
  }
  const payload: Record<string, unknown> = { ...out }
  if (out.datasets) {
    const entries = Object.entries(out.datasets)
    if (entries.length > 0) {
      const [name, ds] = entries[0]
      payload.rows = ds.sample
      payload.rowCount = ds.rows
      payload._dataset = name
    }
  }
  return payload
}

export default function StepOutputView({ output, error, nodeId }: Props) {
  const flat = useMemo(() => flattenRunOutput(output, nodeId), [output, nodeId])
  const logs = useMemo(() => pickLogs(flat), [flat])
  const downloadUrl =
    typeof flat?.download_url === 'string' ? resolveDownloadHref(flat.download_url) : null
  const downloadName =
    typeof flat?.filename === 'string'
      ? flat.filename
      : downloadUrl
        ? decodeURIComponent(downloadUrl.split('/').pop() || 'download')
        : 'download'

  if (!flat && !error) {
    return <div style={{ fontSize: 11, color: 'var(--text-3)' }}>No output recorded.</div>
  }

  return (
    <div
      className="rounded-md overflow-hidden"
      style={{ border: '1px solid var(--border)', background: 'var(--bg-0)' }}
    >
      {downloadUrl ? (
        <a
          href={downloadUrl}
          download={downloadName}
          target="_blank"
          rel="noopener"
          className="flex items-center justify-center gap-2 mx-2 mt-2 rounded-md"
          style={{
            padding: '8px 12px',
            fontSize: 12,
            fontWeight: 600,
            background: 'linear-gradient(180deg, var(--info) 0%, color-mix(in srgb, var(--info) 70%, black) 100%)',
            color: '#fff',
            border: '1px solid color-mix(in srgb, var(--info) 50%, transparent)',
          }}
        >
          <ArcIcon icon={Download} size={14} strokeWidth={2.2} />
          <span>Download {downloadName}</span>
        </a>
      ) : null}

      {error && (
        <div
          className="flex items-start gap-2 px-3 py-2 font-mono"
          style={{
            fontSize: 10,
            background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
            color: 'var(--danger)',
            borderBottom: '1px solid var(--border-soft)',
          }}
        >
          <ArcIcon icon={AlertTriangle} size={12} className="shrink-0 mt-0.5" />
          <span className="break-words">{error}</span>
        </div>
      )}

      <div className="overflow-auto" style={{ maxHeight: 'min(420px, 50vh)' }}>
        {flat && <HumanReadableOutput data={flat} />}
        {!flat && error && (
          <div className="p-3" style={{ fontSize: 11.5, color: 'var(--danger)' }}>
            {error}
          </div>
        )}
        {logs && logs.length > 0 && (
          <div className="px-3 pb-3">
            <div
              className="font-mono mb-1"
              style={{ fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-3)' }}
            >
              Logs
            </div>
            <pre
              className="font-mono rounded-md p-2.5 whitespace-pre-wrap break-words"
              style={{
                fontSize: 10.5,
                color: 'var(--text-0)',
                background: 'var(--bg-1)',
                border: '1px solid var(--border-soft)',
                lineHeight: 1.55,
                maxHeight: 180,
                overflow: 'auto',
              }}
            >
              {logs.join('\n')}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
