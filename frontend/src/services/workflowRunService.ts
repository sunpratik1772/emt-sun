/** Active workflow run abort — shared by toolbar and Topbar. */
let activeRunAbort: AbortController | null = null

export function bindWorkflowRunAbort(controller: AbortController): void {
  activeRunAbort = controller
}

export function clearWorkflowRunAbort(): void {
  activeRunAbort = null
}

export function stopWorkflowRun(): void {
  activeRunAbort?.abort()
}

export function isWorkflowRunAbortActive(): boolean {
  return activeRunAbort != null
}
