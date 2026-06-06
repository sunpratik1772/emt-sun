import { useStudioSectionStore } from '../store/studioSectionStore'
import { useWorkflowStore } from '../store/workflowStore'

/** Open workflow studio with Sherpa side panel; optionally auto-send the message. */
export function launchSherpaPrompt(message: string, autoSend = false) {
  const trimmed = message.trim()
  if (!trimmed) return

  const store = useWorkflowStore.getState()
  const studio = useStudioSectionStore.getState()

  studio.setSection(null)
  studio.clearAutomationFocus()
  store.setWorkflowDrawerOpen(false)
  store.setWorkspaceView('canvas')
  store.setRightPanelMode('copilot')

  if (!store.workflow) {
    store.newBlankWorkflow()
  }

  store.requestCopilotPrompt(trimmed, autoSend)
}
