import { useEffect } from 'react'
import { useWorkflowStore } from '../store/workflowStore'
import { api } from '../services/api'
import { toast } from '../store/toastStore'

/** Persists sherpa messages even when the panel is collapsed or unmounted. */
export function useCopilotChatAutosave() {
  const copilotMessages = useWorkflowStore((s) => s.copilotMessages)
  const copilotSessionId = useWorkflowStore((s) => s.copilotSessionId)

  useEffect(() => {
    if (copilotMessages.length === 0) return
    const messagesToSend = copilotMessages.map((m) => ({
      role: m.role,
      content: m.content,
      timestamp: m.timestamp.toISOString(),
      ...(m.steps ? { steps: m.steps } : {}),
      ...(m.summary ? { summary: m.summary } : {}),
    }))
    const firstUserMsg = copilotMessages.find((m) => m.role === 'user')
    const title = firstUserMsg
      ? firstUserMsg.content.slice(0, 50) + (firstUserMsg.content.length > 50 ? '...' : '')
      : 'New Chat'

    void api
      .saveChat(copilotSessionId, messagesToSend, title)
      .catch((err) => toast.warning(`Chat history not saved: ${(err as Error).message}`))
  }, [copilotMessages, copilotSessionId])
}
