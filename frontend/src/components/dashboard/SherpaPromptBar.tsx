import { useRef, useState } from 'react'
import { ArcIcon, ArrowUpRight, Sparkles } from '../../icons/arc'
import { launchSherpaPrompt } from '../../lib/launchSherpaPrompt'
import { useDashboardSherpaFeed } from './DashboardSherpaContext'
import SherpaPromptSuggestions from '../SherpaPromptSuggestions'

export default function SherpaPromptBar({ onSubmit }: { onSubmit?: (message: string) => void }) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const sherpa = useDashboardSherpaFeed()

  function selectSuggestion(text: string) {
    setValue(text)
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  function submitMessage(message: string) {
    const trimmed = message.trim()
    if (!trimmed) return
    if (onSubmit) onSubmit(trimmed)
    else launchSherpaPrompt(trimmed, true)
    setValue('')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    submitMessage(value)
  }

  return (
    <section className="dash-ai-card">
      <form className="dash-sherpa" onSubmit={handleSubmit}>
        <div className="dash-sherpa__icon" aria-hidden>
          <ArcIcon icon={Sparkles} size={16} />
        </div>
        <input
          ref={inputRef}
          type="text"
          className="dash-sherpa__input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask Sherpa anything…"
          aria-label="Ask Sherpa"
        />
        <button type="submit" className="dash-sherpa__submit" disabled={!value.trim()} aria-label="Send to Sherpa">
          <ArcIcon icon={ArrowUpRight} size={16} strokeWidth={2.2} />
        </button>
      </form>
      <SherpaPromptSuggestions
        variant="home"
        limit={3}
        onSelect={selectSuggestion}
        prompts={sherpa.suggestions}
        loading={sherpa.loading}
        aiReady={sherpa.aiReady}
        status={sherpa.status}
      />
    </section>
  )
}
