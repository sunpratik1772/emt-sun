import { useWorkflowStore } from '../store/workflowStore'

/** Open Sherpa in the right side panel (never toggle closed). */
export function focusSherpaSidePanel(opts?: { pop?: boolean }) {
  const s = useWorkflowStore.getState()
  const pop = opts?.pop !== false
  useWorkflowStore.setState({
    rightPanelMode: 'copilot',
    sherpaPanelPopAt: pop ? Date.now() : s.sherpaPanelPopAt,
  })
}
