/**
 * Tracks which "section" of the studio is currently open.
 * The LeftNav writes here, the App renders the matching drawer.
 *
 * `null` means the workflow canvas is active.
 * `'dashboard'` is the Shoal-style home view.
 */
import { create } from 'zustand'
import type { RunLogSummary } from '../services/api'
import { hydrateRunForOutputPanel } from '../lib/runHistoryOutput'
import { useWorkflowStore } from './workflowStore'

export type StudioSection = null | 'dashboard' | 'skills' | 'data' | 'run-history' | 'nodes' | 'settings' | 'automations'

function clearAutomationHash() {
  if (typeof window === 'undefined') return
  if (window.location.hash.startsWith('#automations/')) {
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
  }
}

interface State {
  section: StudioSection
  automationId: string | null
  runHistoryRunId: string | null
  runHistoryAutoOpenModal: boolean
  runHistoryPrefill: RunLogSummary | null
  runOutputModalRun: RunLogSummary | null
  setSection: (s: StudioSection) => void
  toggleSection: (s: Exclude<StudioSection, null>) => void
  openAutomation: (automationId: string) => void
  openRunHistory: (runId: string, autoOpenModal?: boolean, prefill?: RunLogSummary | null) => void
  openRunOutputModal: (run: RunLogSummary) => void
  closeRunOutputModal: () => void
  clearAutomationFocus: () => void
  clearRunHistoryFocus: () => void
}

function clearRunHistoryState() {
  return {
    runHistoryRunId: null as string | null,
    runHistoryAutoOpenModal: false,
    runHistoryPrefill: null as RunLogSummary | null,
  }
}

export const useStudioSectionStore = create<State>((set, get) => ({
  section: 'dashboard',
  automationId: null,
  runHistoryRunId: null,
  runHistoryAutoOpenModal: false,
  runHistoryPrefill: null,
  runOutputModalRun: null,
  setSection: (section) => {
    if (section !== 'automations') {
      clearAutomationHash()
      set({ automationId: null })
    }
    if (section !== 'run-history') {
      set({
        section,
        ...clearRunHistoryState(),
        runOutputModalRun: null,
      })
      return
    }
    set({ section })
  },
  toggleSection: (s) => {
    const next = get().section === s ? null : s
    if (next !== 'automations') {
      clearAutomationHash()
      set({ automationId: null })
    }
    if (next !== 'run-history') {
      set({
        section: next,
        ...clearRunHistoryState(),
        runOutputModalRun: null,
      })
      return
    }
    set({ section: next })
  },
  openRunHistory: (runId, autoOpenModal = true, prefill = null) => {
    clearAutomationHash()
    set({
      section: 'run-history',
      automationId: null,
      runHistoryRunId: runId,
      runHistoryAutoOpenModal: autoOpenModal,
      runHistoryPrefill: prefill,
    })
  },
  openRunOutputModal: (run) => {
    const hydrated = hydrateRunForOutputPanel(run)
    useWorkflowStore.setState({
      runLog: hydrated.runLog,
      runResult: hydrated.runResult,
      runTotalMs: hydrated.runTotalMs,
      runError: hydrated.runError,
      rightPanelMode: 'output',
      outputOrientation: 'bottom',
      outputSummarySource: 'run',
      outputSummaryAt: Date.now(),
    })
    set({
      section: null,
      runOutputModalRun: null,
    })
  },
  closeRunOutputModal: () => {
    set({ runOutputModalRun: null })
  },
  openAutomation: (automationId) => {
    set({
      section: 'automations',
      automationId,
      ...clearRunHistoryState(),
      runOutputModalRun: null,
    })
    const base = `${window.location.pathname}${window.location.search}`
    const nextHash = `#automations/${encodeURIComponent(automationId)}`
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, '', `${base}${nextHash}`)
    }
  },
  clearAutomationFocus: () => {
    clearAutomationHash()
    set({ automationId: null })
  },
  clearRunHistoryFocus: () => {
    set(clearRunHistoryState())
  },
}))
