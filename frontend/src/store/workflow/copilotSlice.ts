import { focusSherpaSidePanel } from '../../lib/focusSherpaSidePanel'
import { layoutAndCompactWorkflow } from '../layout'
import { generateSessionId } from './workflowHelpers'
import type { CopilotDraftRequest } from '../../lib/sherpaStarterPrompts'
import type { WorkflowSetState, WorkflowStore } from './types'

export function createCopilotSlice(
  set: WorkflowSetState,
): Pick<
  WorkflowStore,
  | 'copilotSessionId'
  | 'resetCopilotSession'
  | 'setCopilotSessionMessages'
  | 'copilotMessages'
  | 'addCopilotMessage'
  | 'appendToLastAssistantMessage'
  | 'clearCopilotMessages'
  | 'revertWorkflow'
  | 'redoWorkflow'
  | 'copilotDraft'
  | 'setCopilotDraft'
  | 'requestCopilotPrompt'
> {
  return {
    copilotSessionId: generateSessionId(),
    copilotMessages: [],
    copilotDraft: null,

    resetCopilotSession: () =>
      set((s) => ({
        copilotSessionId: generateSessionId(),
        copilotMessages: [],
      })),

    setCopilotSessionMessages: (msgs) => set({ copilotMessages: msgs }),

    addCopilotMessage: (msg) => set((s) => ({ copilotMessages: [...s.copilotMessages, msg] })),

    appendToLastAssistantMessage: (chunk) =>
      set((s) => {
        const msgs = s.copilotMessages
        for (let i = msgs.length - 1; i >= 0; i--) {
          if (msgs[i].role === 'assistant') {
            const next = msgs.slice()
            next[i] = { ...msgs[i], content: (msgs[i].content || '') + chunk }
            return { copilotMessages: next }
          }
        }
        return {}
      }),

    clearCopilotMessages: () => set({ copilotMessages: [] }),

    revertWorkflow: (index) =>
      set((s) => {
        const msg = s.copilotMessages[index]
        if (!msg || msg.previousWorkflow === undefined) return {}

        const nextWorkflow = msg.previousWorkflow
          ? layoutAndCompactWorkflow(msg.previousWorkflow)
          : null
        const nextMessages = s.copilotMessages.map((m, i) =>
          i === index ? { ...m, reverted: true } : m,
        )

        return {
          workflow: nextWorkflow,
          copilotMessages: nextMessages,
          history: [...s.history, nextWorkflow],
          historyIndex: s.history.length,
          workflowViewportVersion: s.workflowViewportVersion + 1,
        }
      }),

    redoWorkflow: (index) =>
      set((s) => {
        const msg = s.copilotMessages[index]
        if (!msg || !msg.newWorkflow) return {}

        const nextWorkflow = layoutAndCompactWorkflow(msg.newWorkflow)
        const nextMessages = s.copilotMessages.map((m, i) =>
          i === index ? { ...m, reverted: false } : m,
        )

        return {
          workflow: nextWorkflow,
          copilotMessages: nextMessages,
          history: [...s.history, nextWorkflow],
          historyIndex: s.history.length,
          workflowViewportVersion: s.workflowViewportVersion + 1,
        }
      }),

    setCopilotDraft: (v) => {
      if (v == null) {
        set({ copilotDraft: null })
        return
      }
      if (typeof v === 'string') {
        set({ copilotDraft: { text: v, autoSend: false } })
        return
      }
      set({ copilotDraft: v })
    },

    requestCopilotPrompt: (text, autoSend = false) => {
      focusSherpaSidePanel()
      set({ copilotDraft: { text: text.trim(), autoSend } })
    },
  }
}

export type { CopilotDraftRequest }
