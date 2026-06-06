/**
 * Shared helpers for the in-app docs viewer (TOC ids, internal links).
 */
import type { Root } from 'mdast'
import { toString } from 'mdast-util-to-string'
import type { ReactNode } from 'react'
import remarkGfm from 'remark-gfm'
import remarkParse from 'remark-parse'
import { unified } from 'unified'
import type { Plugin } from 'unified'
import { visit } from 'unist-util-visit'

export interface TocEntry {
  id: string
  text: string
  level: number
}

export interface ParsedHeading {
  level: number
  text: string
  id: string
}

const DOC_LINK_RE = /^(?:\.\/)?([a-z0-9][a-z0-9-]*)\.md$/i

export function slugify(text: string): string {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

export function makeHeadingId(text: string, used: Map<string, number>): string {
  const base = slugify(text) || 'section'
  const count = used.get(base) ?? 0
  used.set(base, count + 1)
  return count === 0 ? base : `${base}-${count + 1}`
}

/** Normalize heading plain text for stable ids and TOC labels. */
export function cleanHeadingSource(raw: string): string {
  let text = raw.trim()
  text = text.replace(/\s*\{#[^}]+\}\s*$/, '')
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  text = text.replace(/[`*_~]/g, '')
  return text.trim()
}

/** Parse markdown with the same remark pipeline ReactMarkdown uses. */
export function parseMarkdownHeadings(markdown: string): ParsedHeading[] {
  const tree = unified().use(remarkParse).use(remarkGfm).parse(markdown)
  const used = new Map<string, number>()
  const headings: ParsedHeading[] = []

  visit(tree, 'heading', (node) => {
    if (node.depth > 3) return
    const text = cleanHeadingSource(toString(node))
    const id = makeHeadingId(text, used)
    headings.push({ level: node.depth, text, id })
  })

  return headings
}

/** Heading ids in source order (h1–h3) for ReactMarkdown custom components. */
export function buildHeadingIdQueue(markdown: string): string[] {
  return parseMarkdownHeadings(markdown).map((heading) => heading.id)
}

export function extractToc(markdown: string): TocEntry[] {
  return parseMarkdownHeadings(markdown)
    .filter((heading) => heading.level >= 2 && heading.level <= 3)
    .map(({ id, text, level }) => ({ id, text, level }))
}

/** Inject stable ids into the mdast tree ReactMarkdown renders. */
export function remarkAssignHeadingIds(headings: ParsedHeading[]): Plugin<[], Root> {
  return () => (tree) => {
    let index = 0
    visit(tree, 'heading', (node) => {
      if (node.depth > 3) return
      const entry = headings[index++]
      if (!entry) return
      const data = node.data ?? (node.data = {})
      const hProperties = (data.hProperties ??= {})
      hProperties.id = entry.id
    })
  }
}

export function headingText(children: ReactNode): string {
  if (typeof children === 'string') return children
  if (typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(headingText).join('')
  if (children && typeof children === 'object' && 'props' in children) {
    const props = (children as { props?: { children?: ReactNode } }).props
    return headingText(props?.children ?? '')
  }
  return String(children ?? '')
}

/** Scroll offset of an element inside a scroll container. */
export function headingOffsetTop(el: HTMLElement, container: HTMLElement): number {
  return el.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop
}

/** Map `./architecture.md` → in-app docs route, or null if not a guide link. */
export function resolveGuideDocPath(href: string | undefined): string | null {
  if (!href) return null
  const m = href.match(DOC_LINK_RE)
  if (!m) return null
  return `/docs/guides/${m[1]}`
}
