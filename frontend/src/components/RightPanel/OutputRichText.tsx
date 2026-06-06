import { MarkdownMessage } from '../Copilot/CopilotMarkdown'
import { normalizeRichTextForMarkdown } from './outputFormatUtils'

export default function OutputRichText({
  content,
  compact = false,
}: {
  content: string
  compact?: boolean
}) {
  return (
    <div
      className="output-rich-text"
      style={{
        fontSize: compact ? 11 : 12,
        lineHeight: 1.55,
        color: 'var(--text-0)',
      }}
    >
      <MarkdownMessage content={normalizeRichTextForMarkdown(content)} />
    </div>
  )
}
