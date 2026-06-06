/**
 * DocsPage — theme-aware documentation viewer (uses studio CSS tokens).
 */
import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BookOpen,
  ChevronRight,
  Home,
  Search,
  X,
  FileText,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ErrorBoundary from '../../components/ErrorBoundary'
import { ArcIcon, X as XIcon } from '../../icons/arc'
import {
  extractToc,
  headingOffsetTop,
  parseMarkdownHeadings,
  remarkAssignHeadingIds,
  resolveGuideDocPath,
  type TocEntry,
} from './docsMarkdown'

interface DocSection {
  id: string
  title: string
  icon: string
  items: DocItem[]
}

interface DocItem {
  id: string
  title: string
  content: string
  description?: string
}

/** Prefer same-origin `/api` (Vite proxy); optional absolute backend URL in production. */
function docsApiUrl(): string {
  const base =
    (import.meta as any).env?.VITE_BACKEND_URL ||
    (import.meta as any).env?.REACT_APP_BACKEND_URL ||
    ''
  return base ? `${String(base).replace(/\/$/, '')}/api/docs` : '/api/docs'
}

function parseDocsPath(pathname: string): { section?: string; item?: string } {
  const rest = pathname.replace(/^\/docs\/?/, '')
  const [section, item] = rest.split('/').filter(Boolean)
  return { section, item }
}

export default function DocsPage() {
  const location = useLocation()
  const { section, item } = parseDocsPath(location.pathname)
  const navigate = useNavigate()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [docs, setDocs] = useState<DocSection[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const fetchGen = useRef(0)

  const loadDocs = useCallback(() => {
    const gen = ++fetchGen.current
    setLoading(true)
    setLoadError(null)
    fetch(docsApiUrl(), { cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => {
        if (gen !== fetchGen.current) return
        setDocs(d.sections || [])
        setLoading(false)
      })
      .catch((err) => {
        if (gen !== fetchGen.current) return
        setDocs([])
        setLoadError(err instanceof Error ? err.message : 'Failed to load documentation')
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    loadDocs()
  }, [loadDocs])

  useEffect(() => {
    scrollRef.current?.scrollTo(0, 0)
  }, [section, item])

  const currentSection = docs.find((s) => s.id === section)
  const currentItem = currentSection?.items.find((i) => i.id === item)

  const filteredDocs = useMemo(() => {
    if (!searchQuery.trim()) return docs
    const q = searchQuery.toLowerCase()
    return docs
      .map((s) => ({
        ...s,
        items: s.items.filter(
          (i) => i.title.toLowerCase().includes(q) || i.content.toLowerCase().includes(q),
        ),
      }))
      .filter((s) => s.items.length > 0)
  }, [docs, searchQuery])

  const toc = useMemo(
    () => (currentItem ? extractToc(currentItem.content) : []),
    [currentItem],
  )

  const [activeHeadingId, setActiveHeadingId] = useState<string | null>(null)

  useEffect(() => {
    const container = scrollRef.current
    if (!container || !currentItem || toc.length === 0) return

    const onScroll = () => {
      const maxScroll = container.scrollHeight - container.clientHeight
      if (maxScroll <= 0 || container.scrollTop >= maxScroll - 16) {
        setActiveHeadingId(toc[toc.length - 1].id)
        return
      }

      const marker = container.scrollTop + 96
      let active = toc[0].id
      for (const entry of toc) {
        const el = container.querySelector<HTMLElement>(`#${CSS.escape(entry.id)}`)
        if (!el) continue
        if (headingOffsetTop(el, container) <= marker) active = entry.id
      }
      setActiveHeadingId(active)
    }

    container.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    const raf = requestAnimationFrame(() => onScroll())
    return () => {
      cancelAnimationFrame(raf)
      container.removeEventListener('scroll', onScroll)
    }
  }, [toc, currentItem])

  const scrollToHeading = useCallback((id: string) => {
    const container = scrollRef.current
    if (!container) return
    const el = container.querySelector<HTMLElement>(`#${CSS.escape(id)}`)
    if (!el) return
    container.scrollTo({ top: Math.max(0, headingOffsetTop(el, container) - 24), behavior: 'smooth' })
  }, [])

  const navDocs = searchQuery ? filteredDocs : docs

  return (
    <div className="docs-page ov">
      <div className="ov__head">
        <div className="ov__heading">
          <div className="ov__eyebrow">Guides &amp; reference</div>
          <div className="ov__title">Documentation</div>
          <div className="ov__sub">
            Node catalogue, architecture notes, and onboarding guides for dbSherpa Studio.
          </div>
        </div>
        <div className="ov__tools">
          <button type="button" className="ov__close" aria-label="Back to Studio" onClick={() => navigate('/dashboard')}>
            <ArcIcon icon={XIcon} size={17} strokeWidth={2} />
          </button>
        </div>
      </div>

      <div className="ov__body ov__body--flush">
        <div className={`docs${currentItem && toc.length > 0 ? ' docs--with-onpage' : ''}`}>
          <aside className="docs__toc">
            <label className="docs__search">
              <Search size={13} />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search…"
                aria-label="Search documentation"
              />
            </label>
            <button
              type="button"
              className={`docs__link${!section ? ' docs__link--on' : ''}`}
              onClick={() => navigate('/docs')}
            >
              <Home size={14} />
              Overview
            </button>
            {navDocs.map((sec) => (
              <div key={sec.id}>
                <div className="docs__group">
                  <BookOpen size={13} />
                  {sec.title}
                </div>
                {sec.items.map((itm) => (
                  <button
                    key={itm.id}
                    type="button"
                    className={`docs__link${section === sec.id && item === itm.id ? ' docs__link--on' : ''}`}
                    onClick={() => navigate(`/docs/${sec.id}/${itm.id}`)}
                  >
                    <FileText size={14} />
                    {itm.title}
                  </button>
                ))}
              </div>
            ))}
          </aside>

          <div
            className={`docs__scroll${currentItem && toc.length > 0 ? ' docs__scroll--with-onpage' : ''}`}
            ref={scrollRef}
          >
            <main className="docs__main">
              {loading ? (
                <div className="docs-loading">
                  <span
                    className="animate-spin"
                    style={{
                      width: 18,
                      height: 18,
                      border: '2px solid var(--border-soft)',
                      borderTopColor: 'var(--accent)',
                      borderRadius: '50%',
                      display: 'inline-block',
                    }}
                  />
                  Loading docs…
                </div>
              ) : loadError ? (
                <DocsLoadError message={loadError} onRetry={loadDocs} />
              ) : section && item && !currentItem ? (
                <DocsLoadError message={`Page not found: ${item.replace(/-/g, ' ')}`} onRetry={loadDocs} />
              ) : !currentItem ? (
                <DocsHome docs={docs} navigate={navigate} />
              ) : (
                <>
                  <h1 className="docs__h1">{currentItem.title}</h1>
                  {currentItem.description ? (
                    <p className="docs-article-desc">{currentItem.description}</p>
                  ) : null}
                  <ErrorBoundary region="Documentation">
                    <MarkdownRenderer content={currentItem.content} onGuideLink={(path) => navigate(path)} />
                  </ErrorBoundary>
                  <ArticleNav
                    docs={docs}
                    currentSection={currentSection!}
                    currentItem={currentItem}
                    navigate={navigate}
                  />
                </>
              )}
            </main>

            {currentItem && toc.length > 0 ? (
              <aside className="docs__onpage">
                <div className="docs__onpage-label">On this page</div>
                {toc.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    className={`docs__onpage-link${entry.id === activeHeadingId ? ' docs__onpage-link--on' : ''}`}
                    onClick={() => scrollToHeading(entry.id)}
                  >
                    {entry.text}
                  </button>
                ))}
              </aside>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

function MarkdownRenderer({
  content,
  onGuideLink,
}: {
  content: string
  onGuideLink: (path: string) => void
}) {
  const headings = useMemo(() => parseMarkdownHeadings(content), [content])
  const remarkPlugins = useMemo(
    () => [remarkGfm, remarkAssignHeadingIds(headings)],
    [headings],
  )

  return (
    <div className="docs-markdown">
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        skipHtml
        components={{
          a: ({ href, children, ...props }) => {
            const guidePath = resolveGuideDocPath(href)
            if (guidePath) {
              return (
                <a
                  href={guidePath}
                  onClick={(event) => {
                    event.preventDefault()
                    onGuideLink(guidePath)
                  }}
                >
                  {children}
                </a>
              )
            }
            if (href?.startsWith('http://') || href?.startsWith('https://')) {
              return (
                <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                  {children}
                </a>
              )
            }
            return (
              <a href={href} {...props}>
                {children}
              </a>
            )
          },
          table: ({ children }) => (
            <div className="docs-table-wrap">
              <table>{children}</table>
            </div>
          ),
          pre: ({ children }) => <pre>{children}</pre>,
          code: ({ children, className }) => {
            const isBlock = className?.startsWith('language-')
            if (isBlock) return <code>{children}</code>
            return <code>{children}</code>
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function ArticleNav({
  docs, currentSection, currentItem, navigate,
}: {
  docs: DocSection[]; currentSection: DocSection; currentItem: DocItem; navigate: (p: string) => void
}) {
  const all: { sid: string; item: DocItem }[] = []
  for (const s of docs) for (const i of s.items) all.push({ sid: s.id, item: i })
  const idx = all.findIndex((a) => a.sid === currentSection.id && a.item.id === currentItem.id)
  const prev = idx > 0 ? all[idx - 1] : null
  const next = idx < all.length - 1 ? all[idx + 1] : null
  if (!prev && !next) return null

  return (
    <div className="docs-nav-card-row">
      {prev ? (
        <NavCard dir="prev" label={prev.item.title} onClick={() => navigate(`/docs/${prev.sid}/${prev.item.id}`)} />
      ) : (
        <div style={{ flex: 1 }} />
      )}
      {next && (
        <NavCard dir="next" label={next.item.title} onClick={() => navigate(`/docs/${next.sid}/${next.item.id}`)} />
      )}
    </div>
  )
}

function NavCard({ dir, label, onClick }: { dir: 'prev' | 'next'; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`docs-nav-card${dir === 'next' ? ' docs-nav-card--next' : ''}`}
    >
      <div className="docs-nav-card-kicker">{dir === 'prev' ? '← Previous' : 'Next →'}</div>
      <div className="docs-nav-card-title">{label}</div>
    </button>
  )
}

function DocsLoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="docs-loading" style={{ flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
      <p style={{ margin: 0, color: 'var(--text-1)' }}>{message}</p>
      <p style={{ margin: 0, color: 'var(--text-3)', fontSize: 13 }}>
        The docs API may still be starting. Retry, or refresh the page.
      </p>
      <button type="button" className="docs-studio-btn" onClick={onRetry}>
        Retry
      </button>
    </div>
  )
}

function DocsHome({ docs, navigate }: { docs: DocSection[]; navigate: (p: string) => void }) {
  const allItems = docs.flatMap((s) => s.items.map((i) => ({ ...i, sectionId: s.id })))

  return (
    <div className="docs-home">
      <h1 className="docs__h1">Guides &amp; reference</h1>
      <p className="docs-home-lead">
        Backend restructure (May 2026): data in <code>connectors/</code>, Copilot in{' '}
        <code>generation/</code>, vetted demos in <code>good_examples/</code>.
      </p>

      <div className="docs-home-grid">
        {allItems.map((itm) => (
          <button
            key={itm.id}
            type="button"
            onClick={() => navigate(`/docs/${itm.sectionId}/${itm.id}`)}
            className="docs-card"
          >
            <div className="docs-card-icon">
              <FileText size={16} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="docs-card-title">{itm.title}</div>
              {itm.description && (
                <div className="docs-card-desc">{itm.description}</div>
              )}
            </div>
            <ChevronRight size={14} style={{ marginTop: 4, color: 'var(--text-3)', flexShrink: 0 }} />
          </button>
        ))}
      </div>
    </div>
  )
}
