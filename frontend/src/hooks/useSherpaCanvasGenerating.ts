import { useWorkflowStore } from '../store/workflowStore'

/** True while Sherpa is streaming a visual workflow onto the canvas (harness build only). */
export function useSherpaCanvasGenerating(): boolean {
  return useWorkflowStore((s) => s.copilotHarnessGenerating)
}
