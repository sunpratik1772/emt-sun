/** Keys we hide from the human-readable output view (internal plumbing). */
const HIDDEN_KEYS = new Set([
  '_type',
  'context',
  'node_output',
  'trace',
])

/** Scalar metrics shown as summary badges (never raw row arrays). */
const BADGE_KEYS = new Set([
  'disposition',
  'flag_count',
  'output_branch',
  'status',
  'row_count',
  'rowCount',
  'total',
  'count',
])

/** Keys rendered as long-form text blocks. */
const TEXT_KEYS = new Set([
  'message',
  'response',
  'agent_response',
  'executive_summary',
  'summary',
  'narrative',
  'error',
])

/** Keys that link to downloads. */
const FILE_KEYS = new Set(['download_url', 'filename', 'report_path'])

/** Shown first in the line-by-line section. */
const PRIORITY_LINE_KEYS = ['query', 'source', 'sql', 'table', 'dataset', '_dataset']

/** Minimum rows before we render a side-scroll table instead of inline lines. */
export const TABLE_ROW_THRESHOLD = 2

export interface OutputSection {
  id: string
  title: string
  rows: { label: string; value: string; tone?: 'default' | 'accent' | 'danger' | 'muted' }[]
}

export interface OutputTable {
  title: string
  rows: unknown[]
}

export interface AnalyzedOutput {
  badges: OutputSection['rows']
  lines: OutputSection['rows']
  tables: OutputTable[]
  textBlocks: { title: string; body: string }[]
  files: OutputSection['rows']
  raw: Record<string, unknown>
}

/** Normalize Confluence-style wiki markup to common Markdown before rendering. */
export function normalizeRichTextForMarkdown(text: string): string {
  return text
    .split('\n')
    .map((line) => {
      const heading = line.match(/^h([1-6])\.\s+(.*)$/i)
      if (heading) return `${'#'.repeat(Number(heading[1]))} ${heading[2]}`
      return line
    })
    .join('\n')
}

export function isRichTextFieldKey(key: string): boolean {
  const k = key.toLowerCase()
  return /markdown|response|summary|narrative|body|message|content|text|description/.test(k)
}

export function humanizeKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function formatScalar(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2)
  if (typeof value === 'string') {
    if (value.length > 280) return `${value.slice(0, 277)}…`
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return 'Empty list'
    if (value.every((v) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')) {
      return value.slice(0, 8).map(String).join(', ') + (value.length > 8 ? ` (+${value.length - 8} more)` : '')
    }
    return `${value.length} item${value.length === 1 ? '' : 's'}`
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value as object)
    return keys.length ? `{${keys.slice(0, 4).join(', ')}${keys.length > 4 ? ', …' : ''}}` : 'Empty object'
  }
  return String(value)
}

export function isTabularRows(value: unknown): value is Record<string, unknown>[] {
  if (!Array.isArray(value) || value.length === 0) return false
  const objects = value.filter((v) => v && typeof v === 'object' && !Array.isArray(v))
  return objects.length >= Math.min(value.length, TABLE_ROW_THRESHOLD)
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

/** Discover tabular datasets inside a node output object. */
export function extractTables(data: Record<string, unknown>): OutputTable[] {
  const tables: OutputTable[] = []
  const usedKeys = new Set<string>()

  const push = (title: string, rows: unknown[], key?: string) => {
    if (!rows.length) return
    tables.push({ title, rows })
    if (key) usedKeys.add(key)
  }

  if (isTabularRows(data.rows)) {
    push('Rows', data.rows as unknown[], 'rows')
  } else if (Array.isArray(data.rows) && data.rows.length > 0) {
    push('Rows', data.rows, 'rows')
  }

  if (typeof data.csv === 'string' && data.csv.trim()) {
    const parsed = parseCsvText(data.csv)
    if (parsed.length) push('CSV', parsed, 'csv')
  }

  if (data._type === 'condition') {
    const t = (data.rows_true as unknown[]) ?? []
    const f = (data.rows_false as unknown[]) ?? []
    if (t.length) push('True branch', t, 'rows_true')
    else if (f.length) push('False branch', f, 'rows_false')
  }

  if (data._type === 'router' && data.buckets && typeof data.buckets === 'object') {
    for (const [bucket, rows] of Object.entries(data.buckets as Record<string, unknown[]>)) {
      if (Array.isArray(rows) && rows.length) push(humanizeKey(bucket), rows, `bucket:${bucket}`)
    }
  }

  const datasets = data.datasets as Record<string, { sample?: unknown[]; rows?: number }> | undefined
  if (datasets) {
    for (const [name, ds] of Object.entries(datasets)) {
      if (ds?.sample && Array.isArray(ds.sample) && ds.sample.length) {
        push(humanizeKey(name), ds.sample, `dataset:${name}`)
      }
    }
  }

  for (const [key, value] of Object.entries(data)) {
    if (usedKeys.has(key) || HIDDEN_KEYS.has(key) || key.startsWith('_')) continue
    if (key === 'csv' || key === 'rows') continue
    if (isTabularRows(value)) {
      push(humanizeKey(key), value as unknown[], key)
    }
  }

  return tables
}

export function sanitizeOutput(data: Record<string, unknown>): Record<string, unknown> {
  const flat = { ...data }
  const nested = flat.node_output
  if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
    Object.assign(flat, nested as Record<string, unknown>)
    delete flat.node_output
  }
  for (const key of Object.keys(flat)) {
    if (HIDDEN_KEYS.has(key) || key.startsWith('_')) delete flat[key]
  }
  return flat
}

/** Classify output into badges, line items, tables, and text blocks. */
export function analyzeStructuredOutput(data: Record<string, unknown>): AnalyzedOutput {
  const cleaned = sanitizeOutput(data)
  const tables = extractTables(cleaned)
  const tableKeys = new Set(
    tables.flatMap((t) => {
      const match = Object.entries(cleaned).find(([, v]) => v === t.rows)
      return match ? [match[0]] : []
    }),
  )
  if (Array.isArray(cleaned.rows)) tableKeys.add('rows')
  if (typeof cleaned.csv === 'string') tableKeys.add('csv')

  const badges: OutputSection['rows'] = []
  const lines: OutputSection['rows'] = []
  const textBlocks: { title: string; body: string }[] = []
  const files: OutputSection['rows'] = []
  const deferred: OutputSection['rows'] = []

  for (const [key, value] of Object.entries(cleaned)) {
    if (value === null || value === undefined || value === '') continue
    if (tableKeys.has(key)) continue

    if (FILE_KEYS.has(key)) {
      files.push({ label: humanizeKey(key), value: formatScalar(value), tone: 'accent' })
      continue
    }

    if (TEXT_KEYS.has(key) && typeof value === 'string' && value.trim()) {
      textBlocks.push({ title: humanizeKey(key), body: value.trim() })
      continue
    }

    if (BADGE_KEYS.has(key)) {
      const tone = key === 'disposition' ? 'accent' : key === 'error' ? 'danger' : 'default'
      badges.push({ label: humanizeKey(key), value: formatScalar(value), tone })
      continue
    }

    if (Array.isArray(value)) {
      if (value.length === 0) continue
      if (value.every((v) => typeof v !== 'object' || v === null)) {
        lines.push({ label: humanizeKey(key), value: formatScalar(value) })
      }
      continue
    }

    if (typeof value === 'object') {
      const entries = Object.entries(value as Record<string, unknown>).filter(
        ([, v]) => v !== null && v !== undefined && v !== '',
      )
      if (entries.length === 0) continue
      if (entries.length <= 6 && entries.every(([, v]) => typeof v !== 'object')) {
        for (const [k, v] of entries) {
          deferred.push({ label: `${humanizeKey(key)} · ${humanizeKey(k)}`, value: formatScalar(v) })
        }
      }
      continue
    }

    deferred.push({ label: humanizeKey(key), value: formatScalar(value) })
  }

  const priority = new Map(PRIORITY_LINE_KEYS.map((k, i) => [k, i]))
  deferred.sort((a, b) => {
    const ak = a.label.toLowerCase().replace(/\s+/g, '_')
    const bk = b.label.toLowerCase().replace(/\s+/g, '_')
    const pa = priority.get(ak) ?? 99
    const pb = priority.get(bk) ?? 99
    if (pa !== pb) return pa - pb
    return a.label.localeCompare(b.label)
  })
  lines.push(...deferred)

  if (tables.length > 0) {
    const totalRows = tables.reduce((n, t) => n + t.rows.length, 0)
    const existing = badges.find((b) => b.label === 'Row Count' || b.label === 'Rows')
    if (!existing) {
      badges.push({ label: 'Rows', value: String(totalRows), tone: 'default' })
    }
  }

  return { badges, lines, tables, textBlocks, files, raw: cleaned }
}

/** @deprecated Use analyzeStructuredOutput — kept for existing tests. */
export function buildOutputSections(data: Record<string, unknown>): {
  summary: OutputSection['rows']
  textBlocks: { title: string; body: string }[]
  files: OutputSection['rows']
  fields: OutputSection['rows']
  collections: { title: string; preview: string; count: number }[]
} {
  const analyzed = analyzeStructuredOutput(data)
  const collections = analyzed.tables.map((t) => ({
    title: t.title,
    preview: `${t.rows.length} rows`,
    count: t.rows.length,
  }))
  return {
    summary: analyzed.badges,
    textBlocks: analyzed.textBlocks,
    files: analyzed.files,
    fields: analyzed.lines,
    collections,
  }
}
