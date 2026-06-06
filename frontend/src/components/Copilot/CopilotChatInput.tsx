import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import SherpaSlashMenu from './SherpaSlashMenu'
import AutomateScheduleModal from './AutomateScheduleModal'
import { buildSlashMessage } from '../../hooks/useCopilotRoutes'
import type { SherpaSlashRouteDef } from '../../services/api'
import { Square } from 'lucide-react'
import { ArcIcon, ArrowUp, Wrench } from '../../icons/arc'
import type { CopilotDraftRequest } from '../../lib/sherpaStarterPrompts'
import {
  mergeAutomateWithSchedule,
  needsAutomateSchedulePrompt,
} from '../../lib/automateSchedulePrompt'
import { buildSherpaWelcome } from '../../lib/sherpaGreeting'
import { useSherpaDisplayName } from '../../hooks/useSherpaDisplayName'
import type { RunLogEntry, ValidationIssue, Workflow } from '../../types'
import { Button } from '../ui/Button'
import { collectErrorHints, inputModeHint, normalizeTextareaHeight } from './copilotUtils'
import type { CopilotThreadMessage } from './copilotUtils'

function opensSlashMenu(value: string): boolean {
  return value.startsWith('\\') || value.startsWith('/')
}

export type CopilotChatInputHandle = {
  setText: (value: string) => void
  focus: () => void
}

type CopilotChatInputProps = {
  isLoading: boolean
  draft?: CopilotDraftRequest | null
  onDraftConsumed?: () => void
  onSend: (message: string) => void | Promise<void>
  onStop: () => void
  currentWorkflow: Workflow | null
  validationIssues: ValidationIssue[] | null
  runLog: RunLogEntry[]
  runError: string | null
  selectedNodeId: string | null
  threadMessages?: CopilotThreadMessage[]
}

export const CopilotChatInput = forwardRef<CopilotChatInputHandle, CopilotChatInputProps>(
  function CopilotChatInput(
    {
      isLoading,
      draft,
      onDraftConsumed,
      onSend,
      onStop,
      currentWorkflow,
      validationIssues,
      runLog,
      runError,
      selectedNodeId,
      threadMessages = [],
    },
    ref,
  ) {
    const [input, setInput] = useState('')
    const [slashOpen, setSlashOpen] = useState(false)
    const [automatePrompt, setAutomatePrompt] = useState<string | null>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)
    const hints = collectErrorHints(validationIssues, runLog, runError)
    const hasRunLog = runLog.length > 0
    const hasErrors = hints.length > 0
    const draftHandledRef = useRef<string | null>(null)
    const displayName = useSherpaDisplayName()
    const { inputPlaceholder } = buildSherpaWelcome(displayName)

    useImperativeHandle(ref, () => ({
      setText: (value: string) => {
        setInput(value)
        requestAnimationFrame(() => {
          normalizeTextareaHeight(inputRef.current)
          inputRef.current?.focus()
        })
      },
      focus: () => inputRef.current?.focus(),
    }))

    useEffect(() => {
      if (!draft?.text) {
        draftHandledRef.current = null
        return
      }
      const key = `${draft.text}::${draft.autoSend ? '1' : '0'}`
      if (draftHandledRef.current === key) return
      draftHandledRef.current = key

      if (draft.autoSend) {
        onDraftConsumed?.()
        void onSend(draft.text.trim())
        return
      }

      setInput(draft.text)
      onDraftConsumed?.()
      requestAnimationFrame(() => {
        normalizeTextareaHeight(inputRef.current)
        inputRef.current?.focus()
      })
      // Only react to external draft injection, not local typing.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [draft])

    async function dispatchSend(msg: string) {
      setInput('')
      setSlashOpen(false)
      requestAnimationFrame(() => normalizeTextareaHeight(inputRef.current))
      await onSend(msg)
    }

    async function handleSend() {
      const msg = input.trim()
      if (!msg || isLoading) return
      if (needsAutomateSchedulePrompt(msg)) {
        setAutomatePrompt(msg)
        return
      }
      await dispatchSend(msg)
    }

    return (
      <div className="agent__input">
        {automatePrompt ? (
          <AutomateScheduleModal
            onCancel={() => setAutomatePrompt(null)}
            onConfirm={(scheduleDetail) => {
              const merged = mergeAutomateWithSchedule(automatePrompt, scheduleDetail)
              setAutomatePrompt(null)
              void dispatchSend(merged)
            }}
          />
        ) : null}
        {currentWorkflow && (() => {
          const selected = selectedNodeId
            ? currentWorkflow.nodes.find((n) => n.id === selectedNodeId)
            : null
          const mode = inputModeHint(input, currentWorkflow.name, { threadMessages })
          const parts: string[] = [
            mode === 'run'
              ? `Will run "${currentWorkflow.name}" with sample data`
              : mode === 'edit'
                ? `Editing "${currentWorkflow.name}"`
                : `Generate will replace "${currentWorkflow.name}"`,
          ]
          if (hints.length) {
            parts.push(`${hints.length} issue${hints.length === 1 ? '' : 's'}`)
          } else {
            parts.push(`${currentWorkflow.nodes.length} node${currentWorkflow.nodes.length === 1 ? '' : 's'}`)
          }
          if (selected) {
            parts.push(`"this" = ${selected.id} (${selected.type})`)
          }
          const label = parts.join(' · ')
          const title = hints.length
            ? hints.map((h) => `${(h.kind || 'error').toUpperCase()}${h.node_id ? ' @' + h.node_id : ''}: ${h.message}`).join('\n')
            : mode === 'run'
              ? 'This will execute the canvas workflow with sample data — not regenerate it.'
              : mode === 'edit' && selected
                ? `This edit prompt will attach the current canvas. Deictic references like "this" / "here" resolve to ${selected.id} (${selected.type}).`
                : mode === 'edit'
                  ? 'This prompt will attach the current canvas so sherpa can make a targeted edit.'
                  : 'Create/generate prompts start from a fresh workflow and replace the loaded canvas only after validation succeeds.'
          return (
            <div className="agent__chip" title={title}>
              <ArcIcon icon={Wrench} size={10} strokeWidth={2.2} />
              <span className="num truncate" style={{ flex: 1, minWidth: 0 }}>{label}</span>
            </div>
          )
        })()}
        <div className="agent__box">
          {slashOpen && (
            <SherpaSlashMenu
              filter={input}
              hasWorkflow={Boolean(currentWorkflow)}
              hasRunLog={hasRunLog}
              hasErrors={hasErrors}
              onPick={(route: SherpaSlashRouteDef) => {
                setInput(buildSlashMessage(route, ''))
                setSlashOpen(false)
                requestAnimationFrame(() => {
                  normalizeTextareaHeight(inputRef.current)
                  inputRef.current?.focus()
                })
              }}
              onClose={() => setSlashOpen(false)}
            />
          )}
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => {
              const v = e.target.value
              setInput(v)
              setSlashOpen(opensSlashMenu(v))
              normalizeTextareaHeight(e.target)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSend()
              }
            }}
            placeholder={inputPlaceholder}
            rows={1}
            data-testid="copilot-input"
            className="agent__ta"

          />
          <button
            type="button"
            onClick={isLoading ? onStop : () => void handleSend()}
            disabled={!isLoading && !input.trim()}
            data-testid="copilot-send-btn"
            className="agent__send"
            aria-label={isLoading ? 'Stop' : 'Send'}
          >
            {isLoading ? (
              <Square size={11} strokeWidth={3.2} />
            ) : (
              <ArcIcon icon={ArrowUp} size={14} strokeWidth={2.5} />
            )}
          </button>
        </div>
        <p className="agent__foot">
          ⏎ send · ⇧⏎ newline · <span className="sherpa-routes__hint-inline">\ for routes · /run /build /check-run …</span>
        </p>
      </div>
    )
  },
)
