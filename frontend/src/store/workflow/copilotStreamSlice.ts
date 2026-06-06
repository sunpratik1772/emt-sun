import type { AgentFinalSummary, ThinkingStep } from '../../components/Copilot/thinkingTypes'
import type { CopilotMessage } from '../../types'
import type { SherpaPendingClarification } from '../../components/Copilot/sherpaClarificationTypes'
import type { SherpaActivityMode } from '../../lib/sherpaActivity'
import type { WorkflowSetState, WorkflowStore } from './types'

export type CopilotActiveRoute = 'build' | 'ask' | 'automate' | 'load' | 'explain_run' | null

const emptyStreamSurface = {
  copilotStreamActive: false,
  copilotActiveRoute: null as CopilotActiveRoute,
  copilotHarnessGenerating: false,
  copilotActivityMode: null as SherpaActivityMode,
  copilotThinkingSteps: [] as ThinkingStep[],
  copilotThinkingOpen: false,
  copilotStreamText: '',
  copilotPlanPhaseStreaming: false,
  copilotWorkflowCreated: null as { name: string; nodeCount: number } | null,
  copilotStreamError: null as string | null,
  copilotFinalSummary: null as AgentFinalSummary | null,
  copilotPendingAutomationLink: undefined as CopilotMessage['automationLink'],
}

const emptyStreamUi = {
  ...emptyStreamSurface,
  copilotPendingClarification: null as SherpaPendingClarification | null,
}

export function createCopilotStreamSlice(
  set: WorkflowSetState,
): Pick<
  WorkflowStore,
  | 'copilotStreamActive'
  | 'copilotActiveRoute'
  | 'copilotHarnessGenerating'
  | 'copilotActivityMode'
  | 'copilotThinkingSteps'
  | 'copilotThinkingOpen'
  | 'copilotStreamText'
  | 'copilotPlanPhaseStreaming'
  | 'copilotWorkflowCreated'
  | 'copilotStreamError'
  | 'copilotFinalSummary'
  | 'copilotPendingAutomationLink'
  | 'copilotPendingClarification'
  | 'setCopilotPendingClarification'
  | 'resetCopilotStreamUi'
  | 'resetCopilotStreamSurface'
  | 'patchCopilotStream'
  | 'setCopilotThinkingSteps'
> {
  return {
    ...emptyStreamUi,

    resetCopilotStreamSurface: () => set(emptyStreamSurface),

    resetCopilotStreamUi: () => set(emptyStreamUi),

    patchCopilotStream: (patch) => set((s) => ({ ...s, ...patch })),

    setCopilotThinkingSteps: (updater) =>
      set((s) => {
        const next =
          typeof updater === 'function' ? updater(s.copilotThinkingSteps) : updater
        return { copilotThinkingSteps: next }
      }),

    setCopilotPendingClarification: (pending) =>
      set({ copilotPendingClarification: pending }),
  }
}
