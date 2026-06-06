import { describe, expect, it } from 'vitest'
import {
  analyzeStructuredOutput,
  buildOutputSections,
  extractTables,
  humanizeKey,
  isRichTextFieldKey,
  isTabularRows,
  normalizeRichTextForMarkdown,
  sanitizeOutput,
} from './outputFormatUtils'

describe('outputFormatUtils', () => {
  it('humanizes snake_case keys', () => {
    expect(humanizeKey('flag_count')).toBe('Flag Count')
  })

  it('normalizes Confluence-style headings for markdown renderers', () => {
    expect(normalizeRichTextForMarkdown('h2. Alert summary\n* **Trader:** Avery')).toBe(
      '## Alert summary\n* **Trader:** Avery',
    )
  })

  it('detects rich text field keys', () => {
    expect(isRichTextFieldKey('body_markdown')).toBe(true)
    expect(isRichTextFieldKey('source_row_count')).toBe(false)
  })

  it('flattens node_output and strips internal keys', () => {
    const cleaned = sanitizeOutput({
      _type: 'report',
      context: { hidden: true },
      node_output: {
        disposition: 'REVIEW',
        flag_count: 2,
      },
    })
    expect(cleaned).toEqual({ disposition: 'REVIEW', flag_count: 2 })
  })

  it('builds summary and text sections', () => {
    const sections = buildOutputSections({
      disposition: 'ESCALATE',
      flag_count: 3,
      message: 'Trader exceeded threshold.',
      download_url: '/report/foo.xlsx',
    })
    expect(sections.summary.some((r) => r.label === 'Disposition')).toBe(true)
    expect(sections.textBlocks[0]?.body).toContain('threshold')
    expect(sections.files[0]?.value).toContain('foo.xlsx')
  })

  it('detects tabular row arrays', () => {
    const rows = [
      { alert_id: 1, venue: 'A' },
      { alert_id: 2, venue: 'B' },
    ]
    expect(isTabularRows(rows)).toBe(true)
  })

  it('extracts query/source as lines and rows as a table', () => {
    const data = {
      query: 'SELECT alert_id FROM market_ticks',
      source: 'market_ticks',
      rowCount: 500,
      rows: Array.from({ length: 5 }, (_, i) => ({
        alert_id: i,
        currency_pair: 'EUR/USD',
        spread_pips: 1.2,
      })),
    }
    const analyzed = analyzeStructuredOutput(data)
    expect(analyzed.lines.some((l) => l.label === 'Query')).toBe(true)
    expect(analyzed.lines.some((l) => l.label === 'Source')).toBe(true)
    expect(analyzed.tables).toHaveLength(1)
    expect(analyzed.tables[0].rows).toHaveLength(5)
    expect(analyzed.badges.some((b) => b.label === 'Row Count')).toBe(true)
  })

  it('extractTables finds rows from csv', () => {
    const tables = extractTables({
      csv: 'a,b\n1,2\n3,4',
    })
    expect(tables[0]?.rows).toHaveLength(2)
  })
})
