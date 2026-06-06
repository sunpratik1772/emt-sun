import { useWorkflowStore } from '../store/workflowStore'

export type OutputSummarySource = 'save' | 'copilot' | 'run'

/** Open the right-hand output panel with a fresh canvas / run summary. */
export function openOutputPanelSummary(source: OutputSummarySource) {
  useWorkflowStore.setState({
    rightPanelMode: 'output',
    outputOrientation: 'side',
    outputSummarySource: source,
    outputSummaryAt: Date.now(),
  })
}

/** Open the output panel after a workflow run finishes (success or error). */
export function openRunOutputOnComplete() {
  useWorkflowStore.setState({
    rightPanelMode: 'output',
    outputSummarySource: 'run',
    outputSummaryAt: Date.now(),
  })
}

/** @deprecated Use openRunOutputOnComplete */
export function openRunOutputPanelBottom() {
  openRunOutputOnComplete()
}
