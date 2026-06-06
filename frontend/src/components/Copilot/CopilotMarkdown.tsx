import { memo } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownCodeProps = {
  className?: string
  children?: React.ReactNode
}

const MARKDOWN_COMPONENTS: Components = {
          p: ({ children }) => <p style={{ margin: '0 0 8px 0' }}>{children}</p>,
          ul: ({ children }) => <ul style={{ margin: '0 0 8px 18px', listStyle: 'disc' }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: '0 0 8px 18px', listStyle: 'decimal' }}>{children}</ol>,
          li: ({ children }) => <li style={{ marginBottom: 2 }}>{children}</li>,
          h1: ({ children }) => <h1 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 8px 0' }}>{children}</h1>,
          h2: ({ children }) => <h2 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 8px 0' }}>{children}</h2>,
          h3: ({ children }) => <h3 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 6px 0' }}>{children}</h3>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              style={{ color: 'var(--accent)', textDecoration: 'underline', textUnderlineOffset: 2 }}
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote
              style={{
                margin: '0 0 8px 0',
                paddingLeft: 10,
                borderLeft: '2px solid var(--border-strong)',
                color: 'var(--text-2)',
              }}
            >
              {children}
            </blockquote>
          ),
          hr: () => <hr style={{ borderColor: 'var(--border-soft)', margin: '10px 0' }} />,
          table: ({ children }) => (
            <div style={{ overflowX: 'auto', marginBottom: 8 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11.5 }}>{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th style={{ textAlign: 'left', padding: '4px 6px', border: '1px solid var(--border-soft)', background: 'var(--bg-3)' }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td style={{ padding: '4px 6px', border: '1px solid var(--border-soft)' }}>{children}</td>
          ),
          strong: ({ children }) => (
            <strong style={{ fontWeight: 600, color: 'inherit' }}>{children}</strong>
          ),
          code: ({ className, children }: MarkdownCodeProps) => {
            const isBlock = !!className?.startsWith('language-')
            if (isBlock) {
              return (
                <code
                  className={className}
                  style={{ display: 'block', whiteSpace: 'pre', overflowX: 'auto', fontSize: 10.5 }}
                >
                  {children}
                </code>
              )
            }
            return (
              <code
                style={{
                  fontSize: 10.5,
                  padding: '1px 4px',
                  borderRadius: 4,
                  background: 'var(--bg-3)',
                  border: '1px solid var(--border-soft)',
                }}
              >
                {children}
              </code>
            )
          },
          pre: ({ children }) => (
            <pre
              className="num"
              style={{
                margin: '0 0 8px 0',
                padding: '8px 10px',
                borderRadius: 6,
                border: '1px solid var(--border-soft)',
                background: 'var(--bg-1)',
                overflowX: 'auto',
              }}
            >
              {children}
            </pre>
          ),
}

export const MarkdownMessage = memo(function MarkdownMessage({
  content,
  variant = 'default',
}: {
  content: string
  variant?: 'default' | 'compact'
}) {
  const isCompact = variant === 'compact'
  return (
    <div
      style={{
        color: isCompact ? 'var(--text-3)' : 'var(--text-0)',
        fontSize: isCompact ? 11 : 12,
        lineHeight: isCompact ? 1.45 : 1.55,
      }}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  )
})
