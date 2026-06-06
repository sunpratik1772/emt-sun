import { useState } from 'react'
import { ArcIcon, ChevronDown, ChevronRight } from '../../icons/arc'
import OutputDataTable from './OutputDataTable'
import OutputRichText from './OutputRichText'
import { analyzeStructuredOutput, isRichTextFieldKey } from './outputFormatUtils'

const TONE_COLOR = {
  default: 'var(--text-0)',
  accent: 'var(--accent)',
  danger: 'var(--danger)',
  muted: 'var(--text-2)',
} as const

function LineRow({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: string
  tone?: keyof typeof TONE_COLOR
}) {
  return (
    <div
      className="flex items-start gap-3 py-1.5 font-mono"
      style={{ borderBottom: '1px solid var(--border-soft)', fontSize: 10.5 }}
    >
      <span
        className="shrink-0"
        style={{ color: 'var(--text-3)', minWidth: 72, letterSpacing: '0.02em' }}
      >
        {label}
      </span>
      <span
        className="flex-1 break-words whitespace-pre-wrap"
        style={{
          color: TONE_COLOR[tone],
          fontWeight: tone === 'accent' ? 600 : 400,
          lineHeight: 1.45,
        }}
      >
        {value}
      </span>
    </div>
  )
}

export default function HumanReadableOutput({ data }: { data: Record<string, unknown> }) {
  const [rawOpen, setRawOpen] = useState(false)
  const { badges, lines, tables, textBlocks, files, raw } = analyzeStructuredOutput(data)
  const hasContent =
    badges.length > 0 ||
    lines.length > 0 ||
    tables.length > 0 ||
    textBlocks.length > 0 ||
    files.length > 0

  if (!hasContent) {
    return (
      <div className="p-3" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
        No structured output to display.
      </div>
    )
  }

  return (
    <div className="p-3 space-y-3">
      {badges.length > 0 && (
        <div
          className="rounded-md px-3 py-2 flex flex-wrap gap-x-4 gap-y-1"
          style={{
            background: 'color-mix(in srgb, var(--accent) 8%, var(--bg-1))',
            border: '1px solid color-mix(in srgb, var(--accent) 22%, var(--border-soft))',
          }}
        >
          {badges.map((row) => (
            <span key={row.label} style={{ fontSize: 11.5 }}>
              <span style={{ color: 'var(--text-3)' }}>{row.label}: </span>
              <span style={{ color: TONE_COLOR[row.tone ?? 'default'], fontWeight: 600 }}>{row.value}</span>
            </span>
          ))}
        </div>
      )}

      {lines.length > 0 && (
        <div>
          <SectionLabel>Fields</SectionLabel>
          <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--border-soft)' }}>
            {lines.map((row) => (
              <LineRow key={row.label} {...row} />
            ))}
          </div>
        </div>
      )}

      {tables.map((table) => (
        <div key={table.title}>
          <SectionLabel>{tables.length > 1 ? table.title : 'Data'}</SectionLabel>
          <OutputDataTable rows={table.rows} title={tables.length > 1 ? undefined : table.title} />
        </div>
      ))}

      {files.length > 0 && (
        <div>
          <SectionLabel>Files</SectionLabel>
          <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--border-soft)' }}>
            {files.map((row) => (
              <LineRow key={row.label} {...row} tone="accent" />
            ))}
          </div>
        </div>
      )}

      {textBlocks.map((block) => (
        <div key={block.title}>
          <SectionLabel>{block.title}</SectionLabel>
          <div
            className="rounded-md px-3 py-3 overflow-y-auto"
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--border-soft)',
              maxHeight: 'min(520px, 55vh)',
            }}
          >
            {isRichTextFieldKey(block.title) || block.body.length > 80 ? (
              <OutputRichText content={block.body} />
            ) : (
              <div
                className="break-words whitespace-pre-wrap"
                style={{ fontSize: 11.5, lineHeight: 1.55, color: 'var(--text-1)' }}
              >
                {block.body}
              </div>
            )}
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={() => setRawOpen((v) => !v)}
        className="flex items-center gap-1.5 w-full text-left"
        style={{ fontSize: 10.5, color: 'var(--text-3)', paddingTop: 4 }}
      >
        <ArcIcon icon={rawOpen ? ChevronDown : ChevronRight} size={11} />
        Raw JSON
      </button>
      {rawOpen && (
        <pre
          className="font-mono rounded-md p-2.5 whitespace-pre-wrap break-words"
          style={{
            fontSize: 10,
            color: 'var(--text-1)',
            background: 'var(--bg-1)',
            border: '1px solid var(--border-soft)',
            maxHeight: 240,
            overflow: 'auto',
          }}
        >
          {JSON.stringify(raw, null, 2)}
        </pre>
      )}
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="font-mono mb-1"
      style={{ fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-3)' }}
    >
      {children}
    </div>
  )
}
