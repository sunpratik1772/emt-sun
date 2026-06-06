import { useEffect, useState, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Trash2 as TrashIcon, Edit2, Check, Undo2, Redo2, Sparkles, ThumbsUp, ThumbsDown, Copy } from 'lucide-react'
import { toast } from '../../store/toastStore'
import { ArcIcon } from '../../icons/arc'
import { SherpaMark } from '../SherpaMark'
import ThinkingBlock from './ThinkingBlock'
import type { AgentFinalSummary, ThinkingStep } from './thinkingTypes'
import type { CopilotGuardrailsPayload } from '../../services/api'
import type { CopilotMessage } from '../../types'
import { Button } from '../ui/Button'
import { MarkdownMessage } from './CopilotMarkdown'
import { CopilotAutomationLink } from './CopilotAutomationLink'
import { AgentIdleWave } from './AgentChrome'
import { useWorkflowStore } from '../../store/workflowStore'
import WorkflowVoteButtons from '../WorkflowVoteButtons'

export function SherpaAvatar({ size = 24 }: { size?: number }) {
  return <SherpaMark size={size} />
}

export function AiGlyph({ size = 14 }: { size?: number }) {
  return <SherpaMark size={size} />
}

export const MessageBubble = memo(function MessageBubble({
  msg,
  index,
  onRevert,
  onRedo,
}: {
  msg: CopilotMessage
  index: number
  onRevert?: (idx: number) => void
  onRedo?: (idx: number) => void
}) {
  const isUser = msg.role === 'user'
  const isJson = !isUser && msg.content.trim().startsWith('{')
  const time = msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const [thinkingOpen, setThinkingOpen] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [dontAsk, setDontAsk] = useState(false)

  const runLog = useWorkflowStore((s) => s.runLog)
  const runResult = useWorkflowStore((s) => s.runResult)
  const runError = useWorkflowStore((s) => s.runError)
  const hasRun = runLog.length > 0 || runResult !== null || runError !== null

  const handleRevertClick = () => {
    const skipConfirm = window.localStorage.getItem('dbsherpa:skip-revert-confirm') === 'true'
    if (skipConfirm) {
      onRevert?.(index)
    } else {
      setConfirmOpen(true)
    }
  }

  const handleConfirmRevert = () => {
    if (dontAsk) {
      window.localStorage.setItem('dbsherpa:skip-revert-confirm', 'true')
    }
    onRevert?.(index)
    setConfirmOpen(false)
  }

  useEffect(() => {
    if (!confirmOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        setConfirmOpen(false)
      } else if (e.key === 'Enter') {
        e.preventDefault()
        handleConfirmRevert()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [confirmOpen, dontAsk, index])

  return (
    <div
      className={`mb-4 flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isUser ? (
        <div className="msg-user whitespace-pre-wrap select-text">
          {msg.content}
        </div>
      ) : (
        <div className="msg-asst select-text w-full relative">
          <span className="msg-asst__avatar shrink-0">
            <Sparkles size={12} />
          </span>
          <div
            className="msg-asst__body flex-1 min-w-0"
            style={{
              paddingRight: msg.previousWorkflow !== undefined ? '32px' : '0',
            }}
          >
            {msg.steps && msg.steps.length > 0 && (
              <div className="mb-2.5">
                <ThinkingBlock
                  steps={msg.steps}
                  summary={msg.summary}
                  open={thinkingOpen}
                  isStreaming={false}
                  outputPhase={false}
                  onToggle={() => setThinkingOpen(!thinkingOpen)}
                />
              </div>
            )}
            {isJson ? (
              <pre
                className="num overflow-x-auto whitespace-pre-wrap break-all"
                style={{ fontSize: 10.5, color: 'var(--success)', maxHeight: 260, overflowY: 'auto' }}
              >
                {msg.content}
              </pre>
            ) : (
              <>
                <MarkdownMessage content={msg.content} />
                {msg.automationLink ? (
                  <CopilotAutomationLink
                    id={msg.automationLink.id}
                    name={msg.automationLink.name}
                    scheduleSummary={msg.automationLink.schedule_summary}
                  />
                ) : null}
                {msg.newWorkflow && hasRun && (
                  <div className="mt-2.5">
                    <WorkflowVoteButtons
                      filename=""
                      workflow={msg.newWorkflow}
                      isDraft={true}
                    />
                  </div>
                )}
                <div className="flex items-center gap-1 mt-2 text-[var(--text-3)] opacity-60 hover:opacity-100 transition-opacity">
                  <button
                    type="button"
                    title="Helpful"
                    className="p-1 hover:text-[var(--text-1)] rounded hover:bg-[var(--bg-2)] transition-colors cursor-pointer"
                    style={{ background: 'transparent', border: 'none' }}
                  >
                    <ThumbsUp size={12} />
                  </button>
                  <button
                    type="button"
                    title="Not helpful"
                    className="p-1 hover:text-[var(--text-1)] rounded hover:bg-[var(--bg-2)] transition-colors cursor-pointer"
                    style={{ background: 'transparent', border: 'none' }}
                  >
                    <ThumbsDown size={12} />
                  </button>
                  <button
                    type="button"
                    title="Copy message"
                    className="p-1 hover:text-[var(--text-1)] rounded hover:bg-[var(--bg-2)] transition-colors cursor-pointer"
                    style={{ background: 'transparent', border: 'none' }}
                    onClick={() => {
                      navigator.clipboard.writeText(msg.content)
                      toast.success('Copied to clipboard')
                    }}
                  >
                    <Copy size={12} />
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Undo/Redo Checkpoint Button on Bubble Hover */}
          {msg.previousWorkflow !== undefined && (
            <div
              className="absolute bottom-1.5 right-1.5 flex items-center justify-center"
              style={{ zIndex: 10 }}
            >
              {!msg.reverted ? (
                <button
                  type="button"
                  onClick={handleRevertClick}
                  title="Undo changes"
                  className="flex items-center justify-center rounded-full border cursor-pointer lift"
                  style={{
                    width: 22,
                    height: 22,
                    background: 'var(--bg-1)',
                    borderColor: 'var(--border)',
                    color: 'var(--text-2)',
                    opacity: isHovered ? 1 : 0,
                    transform: isHovered ? 'scale(1)' : 'scale(0.9)',
                    transition: 'background 120ms, color 120ms, border-color 120ms, opacity 150ms var(--ease-out), transform 150ms var(--ease-out)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = 'var(--accent)'
                    e.currentTarget.style.borderColor = 'var(--accent)'
                    e.currentTarget.style.background = 'var(--bg-2)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = 'var(--text-2)'
                    e.currentTarget.style.borderColor = 'var(--border)'
                    e.currentTarget.style.background = 'var(--bg-1)'
                  }}
                >
                  <Undo2 size={11} strokeWidth={2} />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => onRedo?.(index)}
                  title="Redo changes"
                  className="flex items-center justify-center rounded-full border cursor-pointer lift"
                  style={{
                    width: 22,
                    height: 22,
                    background: 'var(--bg-1)',
                    borderColor: 'var(--border)',
                    color: 'var(--text-2)',
                    opacity: isHovered ? 1 : 0,
                    transform: isHovered ? 'scale(1)' : 'scale(0.9)',
                    transition: 'background 120ms, color 120ms, border-color 120ms, opacity 150ms var(--ease-out), transform 150ms var(--ease-out)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = 'var(--success)'
                    e.currentTarget.style.borderColor = 'var(--success)'
                    e.currentTarget.style.background = 'var(--bg-2)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = 'var(--text-2)'
                    e.currentTarget.style.borderColor = 'var(--border)'
                    e.currentTarget.style.background = 'var(--bg-1)'
                  }}
                >
                  <Redo2 size={11} strokeWidth={2} />
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Revert/Reverted Status Strip */}
      {!isUser && msg.previousWorkflow !== undefined && msg.reverted && (
        <div
          className="mt-1 px-1 flex items-center gap-1.5 text-[10.5px] italic text-[var(--text-3)] font-medium"
          style={{ opacity: 0.85 }}
        >
          <span>ℹ️ Changes reverted to last stable version.</span>
          <button
            type="button"
            onClick={() => onRedo?.(index)}
            className="text-[var(--success)] hover:underline border-0 bg-transparent p-0 cursor-pointer font-semibold"
            style={{ fontSize: 10.5 }}
          >
            Redo changes
          </button>
        </div>
      )}

      {/* Discard confirmation dialog */}
      {confirmOpen && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center"
          style={{
            background: 'rgba(3, 6, 11, 0.45)',
            backdropFilter: 'blur(3px)',
            WebkitBackdropFilter: 'blur(3px)',
          }}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="panel-glass"
            style={{
              width: 380,
              maxWidth: 'calc(100vw - 32px)',
              borderRadius: 12,
              border: '1px solid var(--border)',
              boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ fontSize: 15, fontWeight: 650, color: 'var(--text-0)', lineHeight: 1.35 }}>
                Discard all changes up to this checkpoint?
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-3)' }}>
                You can always undo this later.
              </div>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={dontAsk}
                onChange={(e) => setDontAsk(e.target.checked)}
                style={{
                  width: 14,
                  height: 14,
                  accentColor: 'var(--accent)',
                  cursor: 'pointer',
                }}
              />
              <span style={{ fontSize: 12, color: 'var(--text-1)' }}>Don't ask again</span>
            </label>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10 }}>
              <Button
                variant="ghost"
                onClick={() => setConfirmOpen(false)}
                style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12.5, fontWeight: 500 }}
              >
                Cancel (esc)
              </Button>
              <Button
                variant="primary"
                onClick={handleConfirmRevert}
                style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12.5 }}
              >
                Continue
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
})
export function TypingDots() {
  return (
    <div
      className="flex items-center gap-2 px-3 py-2 rounded-xl"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--border-soft)' }}
      role="status"
      aria-label="sherpa is typing"
    >
      <AgentIdleWave />
    </div>
  )
}
export function PromptStatusRow({ status }: { status: 'loading' | 'ready' | 'error' }) {
  return (
    <div
      className="w-full text-left flex items-center"
      style={{
        fontSize: 12,
        padding: '8px 10px',
        borderRadius: 6,
        background: 'transparent',
        color: 'var(--text-3)',
        border: '1px solid var(--border-soft)',
        lineHeight: 1.45,
      }}
    >
      {status === 'error' ? 'Could not load live AI suggestions.' : 'Generating live AI suggestions...'}
    </div>
  )
}
export function GuardrailsCard({ guardrails, error }: { guardrails: CopilotGuardrailsPayload | null; error: string | null }) {
  const caps = guardrails?.capabilities
  const skillNames = guardrails?.skills.map((s) => s.name).slice(0, 4).join(', ')
  return (
    <div
      style={{
        padding: '12px 14px',
        borderRadius: 10,
        background: 'var(--bg-2)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="font-mono mb-2" style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
        ACTIVE GUARDRAILS
      </div>
      {guardrails ? (
        <div style={{ fontSize: 12.5, color: 'var(--text-1)', lineHeight: 1.55 }}>
          <p>
            sherpa is constrained to{' '}
            <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>{guardrails.nodes.length} live nodes</span>,{' '}
            <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>{guardrails.data_sources.length} data catalogs</span>, and{' '}
            <span style={{ color: 'var(--text-0)', fontWeight: 600 }}>{guardrails.skills.length} skills</span>.
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="num px-2 py-1 rounded" style={{ background: 'var(--bg-3)', color: caps?.upload_script_enabled ? 'var(--warning)' : 'var(--success)', border: '1px solid var(--border-soft)', fontSize: 10.5 }}>
              upload_script {caps?.upload_script_enabled ? 'on' : 'off'}
            </span>
            <span className="num px-2 py-1 rounded" style={{ background: 'var(--bg-3)', color: 'var(--text-2)', border: '1px solid var(--border-soft)', fontSize: 10.5 }}>
              signal modes: {caps?.allowed_signal_modes.join(', ')}
            </span>
          </div>
          {skillNames && (
            <p className="mt-2" style={{ color: 'var(--text-2)' }}>
              Skills in prompt: {skillNames}{guardrails.skills.length > 4 ? '...' : ''}
            </p>
          )}
        </div>
      ) : (
        <p style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.55 }}>
          {error ?? 'Loading node, source, skill, and host capability guardrails...'}
        </p>
      )}
    </div>
  )
}
export function SegTab({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5"
      style={{
        height: 30,
        padding: '0 12px',
        borderRadius: 7,
        fontSize: 12,
        fontWeight: 500,
        background: active ? 'var(--text-0)' : 'transparent',
        color: active ? 'var(--bg-0)' : 'var(--text-2)',
        border: active ? 'none' : '1px solid var(--border)',
        cursor: 'pointer',
      }}
    >
      {icon}
      <span>{children}</span>
    </button>
  )
}

export function IconModePill({
  active,
  onClick,
  icon,
  title,
  testId,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  title: string
  testId?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      title={title}
      aria-label={title}
      className="flex items-center justify-center"
      style={{
        width: 26,
        height: 26,
        borderRadius: 5,
        background: active ? 'var(--bg-0)' : 'transparent',
        color: active ? 'var(--text-0)' : 'var(--text-3)',
        border: active ? '1px solid var(--border-strong)' : '1px solid transparent',
        cursor: 'pointer',
        transition: 'background 120ms, color 120ms, border-color 120ms',
      }}
    >
      {icon}
    </button>
  )
}
