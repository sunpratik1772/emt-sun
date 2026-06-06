import { Suspense, lazy } from 'react'
import { useWorkflowStore } from '../../store/workflowStore'
import ConfigView from './ConfigView'
import OutputView from './OutputView'
import RunLogView from './RunLogView'
import AsyncFallback from '../AsyncFallback'

const Copilot = lazy(() => import('../Copilot'))

/**
 * Single right-side panel that switches between Config / Run Log / Copilot
 * based on the activity rail selection. Copilot is lazy-loaded (heavy bundle).
 */
export default function RightPanel() {
  const mode = useWorkflowStore((s) => s.rightPanelMode)
  if (mode === null) return null
  if (mode === 'config') return <ConfigView />
  if (mode === 'runlog') return <RunLogView />
  if (mode === 'copilot') {
    return (
      <Suspense fallback={<AsyncFallback label="Loading sherpa…" />}>
        <Copilot />
      </Suspense>
    )
  }
  if (mode === 'output') return <OutputView />
  return null
}
