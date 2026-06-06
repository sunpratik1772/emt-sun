/**
 * Copilot panel — intent-routed workflow author and advisor.
 *
 * Sherpa classifies each message:
 *   • Build — workflow generation/editing via the agent harness
 *   • Ask   — Q&A, troubleshooting, and platform guidance
 *
 * Streaming: generate/chat SSE events render progressively in the panel.
 */
import { useState, useRef, useEffect } from 'react'
import ResizeHandle from '../ResizeHandle'
import {
  ArcIcon,
  MessageSquare,
  X as XIcon,
  Clock,
  Plus,
  GitMerge,
} from '../../icons/arc'
import { Trash2 as TrashIcon, Edit2, Check, Search } from 'lucide-react'
import ThinkingBlock from './ThinkingBlock'
import { finalizeStuckRunLog, flushRunEventQueue, useWorkflowStore } from '../../store/workflowStore'
import { toast } from '../../store/toastStore'
import { api } from '../../services/api'
import type {
  CopilotMessage,
  Workflow,
  RunResult,
  RunWorkflowStreamEvent,
} from '../../types'

import { MarkdownMessage } from './CopilotMarkdown'
import {
  MessageBubble,
  SherpaAvatar,
  AiGlyph,
} from './CopilotUi'
import { CopilotAutomationLink } from './CopilotAutomationLink'
import { SAMPLE_RUN_PAYLOAD, buildThreadMessages, collectErrorHints } from './copilotUtils'
import { CopilotChatInput, type CopilotChatInputHandle } from './CopilotChatInput'
import SherpaPromptSuggestions from '../SherpaPromptSuggestions'
import SherpaRouteChips from './SherpaRouteChips'
import { applyRunActivity } from './thinkingHelpers'
import {
  explainLastRunInCopilot,
  resolveSherpaClarification,
  runCopilotSend,
  stopCopilotStream,
} from '../../services/copilotStreamService'
import { SherpaClarificationPanel } from './SherpaClarificationPanel'
import { useCopilotChats, useCopilotGuardrails } from '../../hooks/useLibraryQueries'

export default function Copilot() {
  const copilotMessages = useWorkflowStore((s) => s.copilotMessages)
  const addCopilotMessage = useWorkflowStore((s) => s.addCopilotMessage)
  const clearCopilotMessages = useWorkflowStore((s) => s.clearCopilotMessages)
  const copilotSessionId = useWorkflowStore((s) => s.copilotSessionId)
  const resetCopilotSession = useWorkflowStore((s) => s.resetCopilotSession)
  const setCopilotSessionMessages = useWorkflowStore((s) => s.setCopilotSessionMessages)
  const revertWorkflow = useWorkflowStore((s) => s.revertWorkflow)
  const redoWorkflow = useWorkflowStore((s) => s.redoWorkflow)
  const copilotWidth = useWorkflowStore((s) => s.copilotWidth)
  const setCopilotWidth = useWorkflowStore((s) => s.setCopilotWidth)
  const currentWorkflow = useWorkflowStore((s) => s.workflow)
  const runLog = useWorkflowStore((s) => s.runLog)
  const applyRunEvent = useWorkflowStore((s) => s.applyRunEvent)
  const resetRun = useWorkflowStore((s) => s.resetRun)
  const setRunning = useWorkflowStore((s) => s.setRunning)
  const validationIssues = useWorkflowStore((s) => s.validationIssues)
  const runError = useWorkflowStore((s) => s.runError)
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId)
  const copilotDraft = useWorkflowStore((s) => s.copilotDraft)
  const setCopilotDraft = useWorkflowStore((s) => s.setCopilotDraft)
  const [showHistoryList, setShowHistoryList] = useState(false)
  const { data: historySessions = [], refetch: loadHistorySessions } = useCopilotChats(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editingTitleText, setEditingTitleText] = useState('')
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editedTitle, setEditedTitle] = useState('')

  const activeSession = historySessions.find(s => s.session_id === copilotSessionId)
  const filteredSessions = historySessions.filter(s =>
    (s.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  )

  async function handleRenameSession(sessionId: string, newTitle: string) {
    if (!newTitle.trim()) return
    try {
      const chatData = await api.getChat(sessionId)
      const messagesToSend = (chatData.messages || []).map((m: any) => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
        ...(m.steps ? { steps: m.steps } : {}),
        ...(m.summary ? { summary: m.summary } : {}),
      }))
      await api.saveChat(sessionId, messagesToSend, newTitle.trim())
      setEditingSessionId(null)
      await loadHistorySessions()
    } catch (err) {
      toast.error(`Could not rename chat: ${(err as Error).message}`)
    }
  }

  async function saveRenamedTitle() {
    if (!editedTitle.trim()) return
    try {
      const messagesToSend = copilotMessages.map((m) => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp.toISOString(),
        ...(m.steps ? { steps: m.steps } : {}),
        ...(m.summary ? { summary: m.summary } : {}),
      }))
      await api.saveChat(copilotSessionId, messagesToSend, editedTitle.trim())
      setIsEditingTitle(false)
      await loadHistorySessions()
    } catch (err) {
      toast.error(`Could not rename chat: ${(err as Error).message}`)
    }
  }
  const isLoading = useWorkflowStore((s) => s.copilotStreamActive)
  const copilotPendingClarification = useWorkflowStore((s) => s.copilotPendingClarification)
  const setCopilotPendingClarification = useWorkflowStore((s) => s.setCopilotPendingClarification)
  const activeRoute = useWorkflowStore((s) => s.copilotActiveRoute)
  const thinkingSteps = useWorkflowStore((s) => s.copilotThinkingSteps)
  const thinkingOpen = useWorkflowStore((s) => s.copilotThinkingOpen)
  const streamText = useWorkflowStore((s) => s.copilotStreamText)
  const workflowCreated = useWorkflowStore((s) => s.copilotWorkflowCreated)
  const streamError = useWorkflowStore((s) => s.copilotStreamError)
  const finalSummary = useWorkflowStore((s) => s.copilotFinalSummary)
  const pendingAutomationLink = useWorkflowStore((s) => s.copilotPendingAutomationLink)
  const patchCopilotStream = useWorkflowStore((s) => s.patchCopilotStream)
  const [criticIter, setCriticIter] = useState(3)
  const { data: guardrails = null, error: guardrailsQueryError } = useCopilotGuardrails(true)
  const guardrailError = guardrailsQueryError ? (guardrailsQueryError as Error).message : null
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatInputRef = useRef<CopilotChatInputHandle>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const setThinkingSteps = useWorkflowStore((s) => s.setCopilotThinkingSteps)
  const [monologueDone, setMonologueDone] = useState(true)

  const hasThinkingMonologue = thinkingSteps.some(
    (s) => s.kind === 'thinking' || s.subagentType === 'thinking',
  )

  useEffect(() => {
    if (isLoading) {
      setMonologueDone(!hasThinkingMonologue)
    }
  }, [isLoading, hasThinkingMonologue])

  useEffect(() => {
    if (hasThinkingMonologue && isLoading) {
      setMonologueDone(false)
    }
  }, [hasThinkingMonologue, thinkingSteps.find((s) => s.kind === 'thinking')?.detail])

  const showStreamReply = Boolean(streamText)
  const sherpaPanelPopAt = useWorkflowStore((s) => s.sherpaPanelPopAt)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [copilotMessages, isLoading, thinkingSteps, streamText])

  async function autoRunAndExplain(workflow: Workflow) {
    addCopilotMessage({
      role: 'assistant',
      content:
        'Run started. I will analyze full output logs and return one final data-focused explanation when execution finishes.',
      timestamp: new Date(),
    })

    useWorkflowStore.getState().resetCopilotStreamUi()
    patchCopilotStream({ copilotThinkingOpen: true })
    setRunning(true)
    resetRun()
    let runResult: RunResult | null = null
    try {
      await api.runWorkflowStream(workflow, SAMPLE_RUN_PAYLOAD, (ev: RunWorkflowStreamEvent) => {
        applyRunEvent(ev)
        if (ev.type === 'workflow_start') {
          setThinkingSteps((prev) => applyRunActivity(prev, 'workflow_start'))
        } else if (ev.type === 'node_start') {
          setThinkingSteps((prev) => applyRunActivity(prev, 'node_start', ev.label))
        } else if (ev.type === 'node_complete') {
          setThinkingSteps((prev) => applyRunActivity(prev, 'node_complete', ev.label))
        } else if (ev.type === 'node_error') {
          setThinkingSteps((prev) => applyRunActivity(prev, 'node_error', ev.label))
        } else if (ev.type === 'workflow_complete') {
          runResult = ev.result ?? null
          setThinkingSteps((prev) => applyRunActivity(prev, 'workflow_complete'))
        } else if (ev.type === 'workflow_error') {
          setThinkingSteps((prev) => applyRunActivity(prev, 'workflow_error', ev.error))
        }
      })
    } catch (e) {
      addCopilotMessage({
        role: 'assistant',
        content: `Run failed: ${(e as Error).message}`,
        timestamp: new Date(),
      })
      return
    } finally {
      finalizeStuckRunLog()
      setRunning(false)
      await flushRunEventQueue()
    }

    await explainLastRunInCopilot()
  }

  function stopProcessing() {
    stopCopilotStream()
  }

  async function send(msg: string) {
    if (!msg.trim()) return
    if (isLoading) {
      toast.warning('Sherpa is still working on your last message.')
      return
    }
    if (copilotPendingClarification) {
      setCopilotPendingClarification(null)
    }
    await runCopilotSend(msg.trim(), criticIter)
  }

  async function onClarificationContinue(selectionId: string, otherText: string) {
    await resolveSherpaClarification(selectionId, otherText, criticIter)
  }

  function onClarificationSkip() {
    setCopilotPendingClarification(null)
    addCopilotMessage({
      role: 'assistant',
      content: 'Skipped clarification — tell me what you want Sherpa to do next.',
      timestamp: new Date(),
    })
  }

  function fillChatPrompt(text: string) {
    const trimmed = text.trim()
    if (!trimmed) return
    setCopilotDraft(trimmed)
    chatInputRef.current?.setText(trimmed)
  }

  return (
    <div
      key={sherpaPanelPopAt || 'sherpa-idle'}
      ref={rootRef}
      className="panel-glass flex flex-col relative shrink-0 sherpa-side-panel"
      style={{
        width: copilotWidth,
        borderLeft: '1px solid var(--border)',
        height: '100%',
      }}
    >
      {/* Drag the left edge to resize the copilot (VSCode-style). */}
      <ResizeHandle
        edge="left"
        ariaLabel="Resize copilot panel"
        onResize={(clientX) => {
          const right = rootRef.current?.getBoundingClientRect().right ?? window.innerWidth
          setCopilotWidth(right - clientX)
        }}
      />
      {/* Header — icon, title, history, close. */}
      <div className="px-4 py-2.5 shrink-0" style={{ borderBottom: '1px solid var(--border-soft)' }}>
        <div className="flex items-center gap-2">
          <div
            className="flex items-center justify-center shrink-0"
            aria-hidden
            style={{ width: 20, height: 20 }}
          >
            <SherpaAvatar size={18} />
          </div>
          <span
            className="display truncate"
            style={{
              fontSize: 13.5,
              fontWeight: 530,
              color: 'var(--text-0)',
              letterSpacing: '-0.02em',
            }}
          >
            sherpa
          </span>
          <div className="flex-1" />
          {/* History control */}
          <button
            onClick={() => {
              setShowHistoryList(!showHistoryList)
              if (!showHistoryList) void loadHistorySessions()
            }}
            title="Chat history"
            aria-label="Chat history"
            className="flex items-center justify-center lift"
            style={{
              width: 26, height: 26, borderRadius: 5,
              background: showHistoryList ? 'var(--bg-3)' : 'transparent',
              color: showHistoryList ? 'var(--accent)' : 'var(--text-3)',
              border: showHistoryList ? '1px solid var(--border-strong)' : '1px solid transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!showHistoryList) {
                const el = e.currentTarget as HTMLElement
                el.style.borderColor = 'var(--border)'
                el.style.color = 'var(--text-0)'
              }
            }}
            onMouseLeave={(e) => {
              if (!showHistoryList) {
                const el = e.currentTarget as HTMLElement
                el.style.borderColor = 'transparent'
                el.style.color = 'var(--text-3)'
              }
            }}
          >
            <ArcIcon icon={Clock} size={13} />
          </button>
          {/* New chat control */}
          <button
            onClick={() => {
              if (isLoading) {
                toast.warning('Wait for sherpa to finish, or stop the current run first.')
                return
              }
              resetCopilotSession()
              setShowHistoryList(false)
              useWorkflowStore.getState().resetCopilotStreamUi()
            }}
            title="New chat"
            aria-label="New chat"
            className="flex items-center justify-center lift"
            style={{
              width: 26, height: 26, borderRadius: 5,
              background: 'transparent', color: 'var(--text-3)',
              border: '1px solid transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'; (e.currentTarget as HTMLElement).style.color = 'var(--text-0)' }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--text-3)' }}
          >
            <ArcIcon icon={Plus} size={13} />
          </button>
          <button
            onClick={() => useWorkflowStore.getState().setRightPanelMode(null)}
            aria-label="Close panel"
            data-testid="copilot-close-btn"
            className="flex items-center justify-center"
            style={{
              width: 22, height: 22, borderRadius: 5,
              background: 'transparent', color: 'var(--text-3)',
              border: '1px solid transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'; (e.currentTarget as HTMLElement).style.color = 'var(--text-0)' }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--text-3)' }}
          >
            <ArcIcon icon={XIcon} size={11} />
          </button>
        </div>
      </div>

      {/* Messages */}
      {showHistoryList ? (
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-2">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-[9px] text-[var(--text-3)] tracking-wider uppercase">Past chats</span>
            <button
              onClick={() => setShowHistoryList(false)}
              className="text-[11px] text-[var(--accent)] hover:underline"
              style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
            >
              Back to chat
            </button>
          </div>
          {/* Search bar to filter past chats */}
          <div className="relative mb-3 flex items-center">
            <input
              type="text"
              placeholder="Search chat history..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-[12px] bg-[var(--bg-2)] text-[var(--text-0)] pl-8 pr-3 py-1.5 rounded-md border border-[var(--border-soft)] focus:outline-none focus:border-[var(--accent)]"
            />
            <div className="absolute left-2.5 top-2.5 text-[var(--text-3)]">
              <Search size={13} />
            </div>
          </div>
          {filteredSessions.length === 0 ? (
            <div className="text-center text-[var(--text-3)] py-8 text-[12px]">No past chats found</div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {filteredSessions.map((sess) => {
                const isActive = sess.session_id === copilotSessionId
                const isEditing = editingSessionId === sess.session_id
                return (
                  <div
                    key={sess.session_id}
                    className="group flex items-center justify-between rounded-lg p-2.5 transition-all lift"
                    style={{
                      background: isActive ? 'var(--bg-3)' : 'var(--bg-2)',
                      border: `1px solid ${isActive ? 'var(--border-strong)' : 'var(--border-soft)'}`,
                      cursor: 'pointer',
                    }}
                    onClick={async () => {
                      if (isEditing) return
                      try {
                        const chatData = await api.getChat(sess.session_id)
                        const formattedMsgs = (chatData.messages || []).map((m: any) => ({
                          role: m.role,
                          content: m.content,
                          timestamp: new Date(m.timestamp),
                          ...(m.steps ? { steps: m.steps } : {}),
                          ...(m.summary ? { summary: m.summary } : {}),
                        }))
                        setCopilotSessionMessages(formattedMsgs)
                        useWorkflowStore.setState({ copilotSessionId: sess.session_id })
                        setShowHistoryList(false)
                      } catch (err) {
                        toast.error(`Could not load chat: ${(err as Error).message}`)
                      }
                    }}
                  >
                    <div className="flex-1 min-w-0 pr-2 flex items-center gap-2">
                      <ArcIcon icon={MessageSquare} size={12} style={{ color: isActive ? 'var(--accent)' : 'var(--text-3)' }} />
                      {isEditing ? (
                        <input
                          type="text"
                          value={editingTitleText}
                          onChange={(e) => setEditingTitleText(e.target.value)}
                          onKeyDown={async (e) => {
                            if (e.key === 'Enter') {
                              e.stopPropagation()
                              await handleRenameSession(sess.session_id, editingTitleText)
                            } else if (e.key === 'Escape') {
                              e.stopPropagation()
                              setEditingSessionId(null)
                            }
                          }}
                          onClick={(e) => e.stopPropagation()}
                          autoFocus
                          className="bg-[var(--bg-3)] text-[12px] text-[var(--text-0)] px-2 py-0.5 rounded border border-[var(--border)] focus:outline-none focus:border-[var(--accent)] w-full"
                        />
                      ) : (
                        <div className="min-w-0 flex-1">
                          <div
                            className="truncate text-[12px] font-medium"
                            style={{ color: isActive ? 'var(--text-0)' : 'var(--text-1)' }}
                          >
                            {sess.title}
                          </div>
                          <div className="text-[10px] text-[var(--text-3)] mt-0.5">
                            {new Date(sess.updated_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                          </div>
                        </div>
                      )}
                    </div>
                    {!isEditing && (
                      <div className="flex items-center">
                        <button
                          type="button"
                          title="Rename chat"
                          className="opacity-0 group-hover:opacity-100 flex items-center justify-center p-1 rounded hover:bg-[var(--bg-3)] text-[var(--text-3)] hover:text-[var(--accent)] transition-all mr-1"
                          style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                          onClick={(e) => {
                            e.stopPropagation()
                            setEditingSessionId(sess.session_id)
                            setEditingTitleText(sess.title || '')
                          }}
                        >
                          <Edit2 size={11} />
                        </button>
                        <button
                          type="button"
                          title="Delete chat"
                          className="opacity-0 group-hover:opacity-100 flex items-center justify-center p-1 rounded hover:bg-[var(--bg-3)] text-[var(--text-3)] hover:text-[var(--danger)] transition-all"
                          style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                          onClick={async (e) => {
                            e.stopPropagation()
                            if (confirm('Delete this chat session?')) {
                              try {
                                await api.deleteChat(sess.session_id)
                                if (sess.session_id === copilotSessionId) {
                                  resetCopilotSession()
                                  useWorkflowStore.getState().resetCopilotStreamUi()
                                }
                                await loadHistorySessions()
                              } catch (err) {
                                toast.error(`Could not delete chat: ${(err as Error).message}`)
                              }
                            }
                          }}
                        >
                          <TrashIcon size={12} />
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {/* Active Thread Header at the top of the chat area */}
          {copilotMessages.length > 0 && (
            <div
              className="flex items-center justify-between mb-4 pb-2"
              style={{ borderBottom: '1px solid var(--border-soft)' }}
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <ArcIcon icon={MessageSquare} size={12} style={{ color: 'var(--accent)' }} />
                {isEditingTitle ? (
                  <input
                    type="text"
                    value={editedTitle}
                    onChange={(e) => setEditedTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') void saveRenamedTitle()
                      if (e.key === 'Escape') setIsEditingTitle(false)
                    }}
                    autoFocus
                    className="bg-[var(--bg-3)] text-[12.5px] text-[var(--text-0)] px-2 py-0.5 rounded border border-[var(--border)] focus:outline-none focus:border-[var(--accent)]"
                    style={{ width: '180px' }}
                  />
                ) : (
                  <span
                    className="truncate text-[12.5px] font-medium"
                    style={{ color: 'var(--text-1)' }}
                  >
                    {activeSession?.title || 'Active Chat'}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {isEditingTitle ? (
                  <>
                    <button
                      onClick={() => void saveRenamedTitle()}
                      title="Save"
                      className="flex items-center justify-center p-1 rounded hover:bg-[var(--bg-3)] text-[var(--success)]"
                      style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                    >
                      <Check size={11} />
                    </button>
                    <button
                      onClick={() => setIsEditingTitle(false)}
                      title="Cancel"
                      className="flex items-center justify-center p-1 rounded hover:bg-[var(--bg-3)] text-[var(--danger)]"
                      style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                    >
                      <XIcon size={11} />
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => {
                      setEditedTitle(activeSession?.title || 'Active Chat')
                      setIsEditingTitle(true)
                    }}
                    title="Rename thread"
                    className="flex items-center justify-center p-1 rounded hover:bg-[var(--bg-3)] text-[var(--text-3)] hover:text-[var(--accent)]"
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                  >
                    <Edit2 size={11} />
                  </button>
                )}
              </div>
            </div>
          )}
          {copilotMessages.length === 0 && (
            <div className="space-y-3">
              <div
                className="flex items-start gap-2.5"
                style={{ marginBottom: 6 }}
              >
                <div className="shrink-0 flex items-center justify-center" style={{ width: 16, height: 16 }}>
                  <AiGlyph size={14} />
                </div>
                <div
                  style={{
                    fontSize: 12.5,
                    color: 'var(--text-1)',
                    lineHeight: 1.5,
                    letterSpacing: '-0.005em',
                    paddingTop: 2,
                  }}
                >
                  Describe a workflow, ask a question, or press <code>\</code> for routes like <code>/build</code>, <code>/run</code>, and <code>/check-run</code>.
                </div>
              </div>

              <SherpaRouteChips
                hasWorkflow={Boolean(currentWorkflow)}
                hasRunLog={runLog.length > 0}
                hasErrors={collectErrorHints(validationIssues, runLog, runError).length > 0}
                onSelect={fillChatPrompt}
                limit={3}
                title="Quick routes"
              />
              <SherpaPromptSuggestions
                variant="copilot"
                limit={5}
                hasCanvasWorkflow={Boolean(currentWorkflow?.nodes?.length)}
                canvasWorkflowName={currentWorkflow?.name ?? null}
                onSelect={fillChatPrompt}
              />
              {guardrails && (
                <div
                  className="font-mono"
                  style={{
                    fontSize: 9.5,
                    color: 'var(--text-3)',
                    letterSpacing: '0.02em',
                    marginTop: 12,
                    paddingLeft: 4,
                  }}
                >
                  {guardrails.nodes.length} nodes · {guardrails.data_sources.length} sources · {guardrails.skills.length} skills
                </div>
              )}
            </div>
          )}

          {copilotMessages.map((msg, i) => (
            <MessageBubble
              key={i}
              msg={msg}
              index={i}
              onRevert={revertWorkflow}
              onRedo={redoWorkflow}
            />
          ))}

          {(isLoading || thinkingSteps.length > 0 || streamText || workflowCreated) && (
            <div className="mb-3 flex flex-col gap-2 pl-0.5">
              {(isLoading || thinkingSteps.length > 0) && !copilotMessages.some(
                (m, i) => i === copilotMessages.length - 1 && m.role === 'assistant' && (m.steps?.length ?? 0) > 0,
              ) && (
                    <ThinkingBlock
                      steps={thinkingSteps}
                      summary={finalSummary}
                      open={thinkingOpen}
                      isStreaming={isLoading}
                      outputPhase={!isLoading}
                      onToggle={() =>
                        patchCopilotStream({ copilotThinkingOpen: !thinkingOpen })
                      }
                      onMonologueComplete={() => setMonologueDone(true)}
                    />
                  )}
                  {showStreamReply && (
                    <div style={{ fontSize: 12, lineHeight: 1.55 }}>
                      <MarkdownMessage content={streamText} />
                      {isLoading ? (
                        <span className="num live-blink" style={{ color: 'var(--text-3)' }}> ▍</span>
                      ) : null}
                    </div>
                  )}
                  {pendingAutomationLink && (
                    <CopilotAutomationLink
                      id={pendingAutomationLink.id}
                      name={pendingAutomationLink.name}
                      scheduleSummary={pendingAutomationLink.schedule_summary}
                    />
                  )}
                  {workflowCreated && (
                    <button
                      type="button"
                      title={`${workflowCreated.name} · ${workflowCreated.nodeCount} nodes`}
                      className="flex items-center justify-center"
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: 8,
                        background: 'color-mix(in srgb, var(--accent) 12%, transparent)',
                        border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)',
                        color: 'var(--accent)',
                      }}
                    >
                      <ArcIcon icon={GitMerge} size={15} />
                    </button>
                  )}
                  {streamError && !thinkingSteps.some(s => s.status === 'error') && (
                    <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.55 }}>{streamError}</div>
                  )}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {(copilotMessages.length > 0 || runLog.length > 0) && (
        <div className="px-3 pt-2 shrink-0">
          <SherpaRouteChips
            hasWorkflow={Boolean(currentWorkflow)}
            hasRunLog={runLog.length > 0}
            hasErrors={collectErrorHints(validationIssues, runLog, runError).length > 0}
            onSelect={fillChatPrompt}
            limit={3}
            showMoreHint={copilotMessages.length > 0 || runLog.length > 0}
            title={runLog.length > 0 ? 'After this run' : 'Next step'}
          />
        </div>
      )}

      {copilotPendingClarification ? (
        <SherpaClarificationPanel
          pending={copilotPendingClarification}
          onContinue={(id, other) => void onClarificationContinue(id, other)}
          onSkip={onClarificationSkip}
        />
      ) : null}

      <CopilotChatInput
        ref={chatInputRef}
        isLoading={isLoading || Boolean(copilotPendingClarification)}
        draft={copilotDraft}
        onDraftConsumed={() => setCopilotDraft(null)}
        onSend={send}
        onStop={stopProcessing}
        currentWorkflow={currentWorkflow}
        validationIssues={validationIssues}
        runLog={runLog}
        runError={runError}
        selectedNodeId={selectedNodeId}
        threadMessages={buildThreadMessages(copilotMessages, { excludeLast: false })}
      />
    </div>
  )
}
