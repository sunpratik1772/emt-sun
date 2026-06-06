/** Prefetch Monaco editor chunk on hover so code view opens faster. */
let prefetchStarted = false

export function prefetchMonacoEditor(): void {
  if (prefetchStarted) return
  prefetchStarted = true
  void import('../components/WorkflowCodeEditor')
}
