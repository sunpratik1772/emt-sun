import { useMemo } from 'react'
import OutputRichText from './OutputRichText'
import { humanizeKey, isRichTextFieldKey } from './outputFormatUtils'

const PREVIEW_ROWS = 50

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  return String(v)
}

function shouldRenderRichText(col: string, value: string): boolean {
  if (value === '—' || !value.trim()) return false
  return isRichTextFieldKey(col) || value.length > 120
}

function SingleRowCard({ row, columns }: { row: Record<string, unknown>; columns: string[] }) {
  return (
    <div className="divide-y" style={{ borderColor: 'var(--border-soft)' }}>
      {columns.map((col) => {
        const value = formatCell(row[col])
        const rich = shouldRenderRichText(col, value)
        return (
          <div key={col} className="px-3 py-3" style={{ borderBottom: '1px solid var(--border-soft)' }}>
            <div
              className="font-mono mb-2"
              style={{
                fontSize: 9,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--text-3)',
                fontWeight: 600,
              }}
            >
              {humanizeKey(col)}
            </div>
            {rich ? (
              <OutputRichText content={value} compact />
            ) : (
              <div
                className="break-words whitespace-pre-wrap"
                style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--text-0)' }}
              >
                {value}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function OutputDataTable({
  rows,
  title,
}: {
  rows: unknown[]
  title?: string
}) {
  const preview = rows.slice(0, PREVIEW_ROWS)
  const columns = useMemo(() => {
    const seen = new Set<string>()
    for (const r of preview) {
      if (r && typeof r === 'object' && !Array.isArray(r)) {
        for (const k of Object.keys(r as object)) seen.add(k)
      }
    }
    return Array.from(seen).slice(0, 20)
  }, [preview])

  const useCardLayout = preview.length === 1 && columns.length > 0

  return (
    <div
      className="rounded-md overflow-hidden"
      style={{ border: '1px solid var(--border-soft)', background: 'var(--bg-1)' }}
    >
      {title ? (
        <div
          className="flex items-center justify-between gap-2 px-2.5 py-1.5"
          style={{ borderBottom: '1px solid var(--border-soft)', background: 'var(--bg-2)' }}
        >
          <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-1)' }}>{title}</span>
          <span
            className="num rounded px-1.5 py-0.5"
            style={{
              fontSize: 9.5,
              color: 'var(--info)',
              background: 'color-mix(in srgb, var(--info) 10%, transparent)',
            }}
          >
            {rows.length} rows
          </span>
        </div>
      ) : null}
      <div className="overflow-x-auto">
        {useCardLayout ? (
          <SingleRowCard row={preview[0] as Record<string, unknown>} columns={columns} />
        ) : columns.length === 0 ? (
          <table className="w-full" style={{ fontSize: 11 }}>
            <tbody>
              {preview.map((v, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-soft)' }}>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums align-top"
                    style={{ color: 'var(--text-3)', width: 32 }}
                  >
                    {i + 1}
                  </td>
                  <td
                    className="px-3 py-2.5 break-words whitespace-pre-wrap align-top"
                    style={{ color: 'var(--text-0)', lineHeight: 1.55 }}
                  >
                    {formatCell(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="w-full border-separate border-spacing-0" style={{ fontSize: 11 }}>
            <thead>
              <tr>
                <th
                  className="sticky top-0 z-10 px-3 py-2 text-right tabular-nums"
                  style={{
                    width: 32,
                    color: 'var(--text-3)',
                    background: 'var(--bg-2)',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  #
                </th>
                {columns.map((col) => (
                  <th
                    key={col}
                    className="sticky top-0 z-10 px-3 py-2 text-left"
                    style={{
                      color: 'var(--text-2)',
                      fontWeight: 600,
                      background: 'var(--bg-2)',
                      borderBottom: '1px solid var(--border)',
                      minWidth: isRichTextFieldKey(col) ? 160 : 72,
                    }}
                  >
                    {humanizeKey(col)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map((row, i) => (
                <tr key={i}>
                  <td
                    className="px-3 py-2.5 text-right tabular-nums align-top"
                    style={{ color: 'var(--text-3)', borderBottom: '1px solid var(--border-soft)' }}
                  >
                    {i + 1}
                  </td>
                  {columns.map((col) => {
                    const cell = formatCell((row as Record<string, unknown>)?.[col])
                    const rich = shouldRenderRichText(col, cell)
                    return (
                      <td
                        key={col}
                        className="px-3 py-2.5 align-top"
                        style={{
                          color: 'var(--text-0)',
                          minWidth: rich ? 200 : 72,
                          maxWidth: rich ? 480 : 280,
                          borderBottom: '1px solid var(--border-soft)',
                          verticalAlign: 'top',
                        }}
                      >
                        {rich ? (
                          <OutputRichText content={cell} compact />
                        ) : (
                          <span className="break-words whitespace-pre-wrap" style={{ lineHeight: 1.55 }}>
                            {cell}
                          </span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {rows.length > PREVIEW_ROWS && (
        <div
          className="px-2.5 py-1.5 text-center"
          style={{
            fontSize: 9,
            color: 'var(--text-3)',
            borderTop: '1px solid var(--border-soft)',
          }}
        >
          Showing {PREVIEW_ROWS} of {rows.length} rows
        </div>
      )}
    </div>
  )
}
