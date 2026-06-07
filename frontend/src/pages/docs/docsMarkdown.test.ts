import { readFileSync, readdirSync } from 'fs'
import { join } from 'path'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { describe, expect, it } from 'vitest'
import {
  buildHeadingIdQueue,
  cleanHeadingSource,
  extractToc,
  makeHeadingId,
  parseMarkdownHeadings,
  resolveGuideDocPath,
} from './docsMarkdown'

const DOCS_DIR = join(__dirname, '../../../../docs')

const DOC_GUIDES = [
  'engineering-onboarding.md',
  'backend-structure.md',
  'architecture.md',
  'architecture-principles.md',
  'frontend-architecture.md',
  'node-catalogue.md',
  'creating-nodes.md',
  'data-source-onboarding.md',
  'generation-harness.md',
  'mcp-integrations.md',
  'database.md',
  'sherpa-agent-harness-onboarding.md',
]

/** Mirror backend/app/routers/docs.py _load_md preprocessing. */
function loadMd(text: string): string {
  let out = text.replace(/^#\s+[^\n]+\n*/, '', 1)
  out = out.replace(/^(>\s*[^\n]+\n)+\n*/, '', out.trimStart())
  out = out.replace(/^---\s*\n+/, '', out.trimStart())
  return out.trim()
}

describe('resolveGuideDocPath', () => {
  it('maps guide markdown links to in-app routes', () => {
    expect(resolveGuideDocPath('./architecture.md')).toBe('/docs/guides/architecture')
    expect(resolveGuideDocPath('database.md')).toBe('/docs/guides/database')
    expect(resolveGuideDocPath('../backend/README.md')).toBeNull()
  })
})

describe('cleanHeadingSource', () => {
  it('strips custom anchors and markdown links', () => {
    expect(cleanHeadingSource('MCP integrations (Atlassian + GitHub) {#mcp-integrations-atlassian--github}')).toBe(
      'MCP integrations (Atlassian + GitHub)',
    )
    expect(cleanHeadingSource('[Architecture](./architecture.md)')).toBe('Architecture')
  })
})

describe('parseMarkdownHeadings', () => {
  it('dedupes duplicate heading titles with numeric suffixes', () => {
    const toc = extractToc('## Key directories\n### A\n## Key directories\n')
    expect(toc.map((e) => e.id)).toEqual(['key-directories', 'a', 'key-directories-2'])
  })

  it('ignores hash lines inside fenced code blocks', () => {
    const md = [
      '## Real section',
      '```bash',
      '# not a heading',
      '## also not a heading',
      '```',
      '### Another section',
    ].join('\n')

    const headings = parseMarkdownHeadings(md)
    expect(headings.map((h) => h.id)).toEqual(['real-section', 'another-section'])
    expect(extractToc(md).map((e) => e.id)).toEqual(['real-section', 'another-section'])
    expect(buildHeadingIdQueue(md)).toEqual(['real-section', 'another-section'])
  })

  it('ignores indented code blocks with hash comments', () => {
    const md = [
      '## YAML spec',
      '',
      '    # not a heading',
      '    type_id: foo',
      '',
      '### Handler',
    ].join('\n')

    expect(parseMarkdownHeadings(md).map((h) => h.id)).toEqual(['yaml-spec', 'handler'])
  })
})

describe('makeHeadingId', () => {
  it('suffixes repeated slugs', () => {
    const used = new Map<string, number>()
    expect(makeHeadingId('Foo', used)).toBe('foo')
    expect(makeHeadingId('Foo', used)).toBe('foo-2')
  })
})

function countRenderedHeadings(content: string): number {
  const html = renderToStaticMarkup(
    createElement(ReactMarkdown, {
      remarkPlugins: [remarkGfm],
      skipHtml: true,
      children: content,
    }),
  )
  const matches = html.match(/<h[123][^>]*>/g)
  return matches?.length ?? 0
}

describe('all guide documents', () => {
  it('have unique toc ids and no code-fence false positives', () => {
    for (const filename of DOC_GUIDES) {
      const raw = readFileSync(join(DOCS_DIR, filename), 'utf8')
      const content = loadMd(raw)
      const headings = parseMarkdownHeadings(content)
      const toc = extractToc(content)
      const queue = buildHeadingIdQueue(content)

      expect(queue).toEqual(headings.map((h) => h.id))
      expect(new Set(toc.map((e) => e.id)).size).toBe(toc.length)

      // Every rendered markdown heading (h1–h3) must have a queue id.
      expect(queue.length).toBe(headings.length)
      expect(toc.length).toBe(headings.filter((h) => h.level >= 2).length)
    }
  }, 30_000)

  it('match ReactMarkdown heading count for representative guides', () => {
    for (const filename of ['architecture.md', 'creating-nodes.md', 'node-catalogue.md']) {
      const raw = readFileSync(join(DOCS_DIR, filename), 'utf8')
      const content = loadMd(raw)
      const parsed = parseMarkdownHeadings(content).length
      const rendered = countRenderedHeadings(content)
      expect(rendered, filename).toBe(parsed)
    }
  }, 30_000)

  it('keeps node catalogue toc ids in document order', () => {
    const raw = readFileSync(join(DOCS_DIR, 'node-catalogue.md'), 'utf8')
    const content = loadMd(raw)
    const headings = parseMarkdownHeadings(content)
    const toc = extractToc(content)

    expect(headings.filter((heading) => heading.level >= 2).map((heading) => heading.id)).toEqual(
      toc.map((entry) => entry.id),
    )

    const filter = toc.find((entry) => entry.id === 'filter')
    const condition = toc.find((entry) => entry.id === 'condition')
    expect(filter?.text).toBe('Filter')
    expect(condition?.text).toBe('Condition')
    expect(toc.findIndex((entry) => entry.id === 'filter')).toBeLessThan(
      toc.findIndex((entry) => entry.id === 'condition'),
    )
  })

  it('covers every markdown guide file in docs/', () => {
    const onDisk = readdirSync(DOCS_DIR)
      .filter((name) => name.endsWith('.md') && name !== 'README.md')
      .sort()
    expect(DOC_GUIDES.map((name) => name.replace(/\.md$/, '')).sort()).toEqual(
      onDisk.map((name) => name.replace(/\.md$/, '')).filter((id) => id !== 'gemini-migration').sort(),
    )
  })
})
