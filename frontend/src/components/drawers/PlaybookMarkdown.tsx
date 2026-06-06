import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export const PlaybookMarkdown = memo(function PlaybookMarkdown({ content }: { content: string }) {
  if (!content.trim()) {
    return (
      <p className="skills-playbook-markdown__empty" style={{ fontSize: 12, color: 'var(--text-3)' }}>
        No playbook content.
      </p>
    )
  }

  return (
    <div className="skills-playbook-markdown studio-surface">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          table: ({ children }) => (
            <div className="skills-playbook-markdown__table-wrap">
              <table>{children}</table>
            </div>
          ),
          pre: ({ children }) => <pre className="skills-playbook-markdown__pre">{children}</pre>,
          code: ({ children, className }) => {
            const isBlock = className?.startsWith('language-')
            if (isBlock) {
              return <code className={`skills-playbook-markdown__code-block ${className ?? ''}`}>{children}</code>
            }
            return <code className="skills-playbook-markdown__code-inline">{children}</code>
          },
          a: ({ href, children }) => {
            const external = href?.startsWith('http://') || href?.startsWith('https://')
            return (
              <a
                href={href}
                target={external ? '_blank' : undefined}
                rel={external ? 'noopener noreferrer' : undefined}
              >
                {children}
              </a>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
})
