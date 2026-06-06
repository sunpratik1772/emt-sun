/**
 * Top-level layout. Five regions, all driven by the workflow store:
 *
 *   ┌────────────────────────────────────────────────────────────────┐
 *   │ LeftNav │ Topbar                                               │
 *   │         ├──────────────────────────────────────────────────────┤
 *   │         │ NodePanel │ WorkflowCanvas │ Activity │ RightPanel  │
 *   │         ├──────────────────────────────────────────────────────┤
 *   │         │ BottomOutputPanel (when Output mode — resizable)     │
 *   └────────────────────────────────────────────────────────────────┘
 */
import { Suspense, lazy, useEffect } from 'react'
import NodePanel from './components/NodePanel'
import RightPanel from './components/RightPanel'
import Topbar from './components/Topbar'
import WorkflowDrawer from './components/WorkflowDrawer'
import ActivityRail from './components/ActivityRail'
import LeftNav from './components/LeftNav'
import BottomOutputPanel from './components/BottomOutputPanel'
import ErrorBoundary from './components/ErrorBoundary'
import ToastHost from './components/ToastHost'
import AsyncFallback from './components/AsyncFallback'
import DashboardHome from './pages/DashboardHome'
import { ArcIcon, PanelLeftOpen } from './icons/arc'
import { SkillsDrawer, DataSourcesDrawer, RunHistoryDrawer, NodesDrawer, AutomationsDrawer, SettingsDrawer } from './components/drawers'
import { useCopilotChatAutosave } from './hooks/useCopilotChatAutosave'
import { useDraftAutosave } from './store/useDraftAutosave'
import { useNodeRegistryStore } from './store/nodeRegistryStore'
import { useStudioSectionStore } from './store/studioSectionStore'
import { useWorkflowStore } from './store/workflowStore'
import { useCompactStudio } from './hooks/useCompactStudio'
import { parseAutomationHash } from './lib/studioNavigation'
import RunOutputModal from './components/RunOutputModal'
import { hydrateRunForOutputPanel } from './lib/runHistoryOutput'
import { openOutputPanelSummary } from './lib/openOutputPanel'
import CommandPalette from './components/CommandPalette'
import WorkspaceToolbar from './components/WorkspaceToolbar'
import { CodeEditorToolbarProvider } from './components/WorkspaceToolbar/context'

const WorkflowCanvas = lazy(() => import('./components/WorkflowCanvas'))
const WorkflowCodeEditor = lazy(() => import('./components/WorkflowCodeEditor'))

export default function App() {
  useDraftAutosave()
  useCopilotChatAutosave()
  const compact = useCompactStudio()
  const section = useStudioSectionStore((s) => s.section)
  const setSection = useStudioSectionStore((s) => s.setSection)
  const runOutputModalRun = useStudioSectionStore((s) => s.runOutputModalRun)
  const closeRunOutputModal = useStudioSectionStore((s) => s.closeRunOutputModal)
  const workspaceView = useWorkflowStore((s) => s.workspaceView)
  const rightPanelMode = useWorkflowStore((s) => s.rightPanelMode)
  const outputOrientation = useWorkflowStore((s) => s.outputOrientation)
  const mobilePaletteOpen = useWorkflowStore((s) => s.mobilePaletteOpen)
  const setMobilePaletteOpen = useWorkflowStore((s) => s.setMobilePaletteOpen)
  const showOutputFooter =
    rightPanelMode === 'output' && section === null && outputOrientation === 'bottom'
  const showRightPanel =
    rightPanelMode !== 'output' || outputOrientation === 'side'
  const showDashboard = section === 'dashboard'
  const showStudio = section === null
  const workflowDrawerOpen = useWorkflowStore((s) => s.workflowDrawerOpen)

  useEffect(() => {
    if (compact && rightPanelMode !== null) setMobilePaletteOpen(false)
  }, [compact, rightPanelMode, setMobilePaletteOpen])

  useEffect(() => {
    const syncFromHash = () => {
      const automationId = parseAutomationHash(window.location.hash)
      if (automationId) {
        useStudioSectionStore.getState().openAutomation(automationId)
      }
    }
    syncFromHash()
    window.addEventListener('hashchange', syncFromHash)
    return () => window.removeEventListener('hashchange', syncFromHash)
  }, [])

  useEffect(() => {
    const store = useNodeRegistryStore.getState()
    void store.refreshFromBackend({ force: true })
    const intervalId = window.setInterval(() => {
      void useNodeRegistryStore.getState().refreshFromBackend({ silent: true })
    }, 15000)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        void useNodeRegistryStore.getState().refreshFromBackend({ silent: true })
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return (
    <div className={`relative h-screen overflow-hidden font-sans text-[var(--text-0)]${compact ? ' studio-compact' : ''}`}>
      <div className="studio-backdrop" aria-hidden>
        <div className="studio-backdrop__wash" />
      </div>
      <div className="relative z-10 flex h-full min-w-0">
        <LeftNav />
        <div className="flex flex-col flex-1 min-w-0">
          {showStudio && !workflowDrawerOpen ? <Topbar /> : null}
          <div className="flex flex-col flex-1 min-h-0 overflow-hidden relative">
            <div className="studio-workspace flex flex-1 overflow-hidden relative min-h-0">
              {showDashboard ? (
                <ErrorBoundary region="Dashboard">
                  <div className="flex flex-1 min-w-0 min-h-0 overflow-hidden">
                    <DashboardHome />
                  </div>
                </ErrorBoundary>
              ) : null}
              {showStudio ? (
                <>
              {compact && mobilePaletteOpen && (
                <button
                  type="button"
                  aria-label="Close node palette"
                  className="studio-palette-backdrop"
                  onClick={() => setMobilePaletteOpen(false)}
                />
              )}
              <div
                className={`studio-node-panel shrink-0 h-full${compact && mobilePaletteOpen ? ' studio-node-panel--open' : ''}`}
              >
                <ErrorBoundary region="Node palette">
                  <NodePanel />
                </ErrorBoundary>
              </div>
              <div className="studio-canvas flex flex-1 min-w-0 min-h-0 relative flex-col">
                {compact && !mobilePaletteOpen && (
                  <button
                    type="button"
                    title="Open node palette"
                    aria-label="Open node palette"
                    className="studio-palette-toggle"
                    onClick={() => setMobilePaletteOpen(true)}
                  >
                    <ArcIcon icon={PanelLeftOpen} size={14} />
                  </button>
                )}
                <CodeEditorToolbarProvider>
                  <WorkspaceToolbar />
                  <div className="flex-1 min-h-0 min-w-0 relative">
                    <ErrorBoundary region="Workflow canvas">
                      <Suspense
                        fallback={
                          <AsyncFallback
                            label={workspaceView === 'canvas' ? 'Loading canvas…' : 'Loading editor…'}
                          />
                        }
                      >
                        {workspaceView === 'canvas' ? <WorkflowCanvas /> : <WorkflowCodeEditor />}
                      </Suspense>
                    </ErrorBoundary>
                  </div>
                </CodeEditorToolbarProvider>
              </div>
              <ActivityRail />
              <ErrorBoundary region="Right panel">
                {showRightPanel ? (
                  <div className="studio-right-panel h-full shrink-0">
                    <RightPanel />
                  </div>
                ) : null}
              </ErrorBoundary>
                </>
              ) : null}
              <WorkflowDrawer />
              <SkillsDrawer open={section === 'skills'} onClose={() => setSection('dashboard')} />
              <DataSourcesDrawer open={section === 'data'} onClose={() => setSection('dashboard')} />
              <RunHistoryDrawer open={section === 'run-history'} onClose={() => setSection('dashboard')} />
              <NodesDrawer open={section === 'nodes'} onClose={() => setSection('dashboard')} />
              <AutomationsDrawer open={section === 'automations'} onClose={() => setSection('dashboard')} />
              <SettingsDrawer open={section === 'settings'} onClose={() => setSection('dashboard')} />
            </div>
            {showOutputFooter ? (
              <ErrorBoundary region="Output panel">
                <BottomOutputPanel />
              </ErrorBoundary>
            ) : null}
          </div>
        </div>
      </div>
      <ToastHost />
      {runOutputModalRun && (
        <RunOutputModal
          run={runOutputModalRun}
          hydrated={hydrateRunForOutputPanel(runOutputModalRun)}
          onClose={closeRunOutputModal}
          onOpenInOutputPanel={(run) => {
            const hydrated = hydrateRunForOutputPanel(run)
            useWorkflowStore.setState({
              runLog: hydrated.runLog,
              runResult: hydrated.runResult,
              runTotalMs: hydrated.runTotalMs,
              runError: hydrated.runError,
            })
            openOutputPanelSummary('run')
            closeRunOutputModal()
            setSection(null)
          }}
        />
      )}
      <CommandPalette />
    </div>
  )
}
