import type { RunLogEntry, RunResult, RunArtifact } from '../types'
import type { AutomationRun, RunLogSummary } from '../services/api'
import { generateStepsForRun } from '../components/drawers/runHistoryUtils'

export interface HydratedRunOutput {
  runLog: RunLogEntry[]
  runResult: RunResult | null
  runError: string | null
  runTotalMs: number | null
  artifacts: RunArtifact[]
}

function stepsToRunLog(run: RunLogSummary): RunLogEntry[] {
  const steps = generateStepsForRun(run)
  return steps.map((step, idx) => ({
    node_id: step.id,
    node_type: step.type,
    label: step.label,
    index: idx + 1,
    total: Math.max(steps.length, run.node_count ?? steps.length),
    status: step.status === 'error' ? 'error' : 'ok',
    started_at: run.started_at,
    duration_ms: step.duration_ms,
    output: step.output_preview ? { node_output: { message: step.output_preview } } : undefined,
    error: step.error,
  }))
}

function fallbackRunResult(run: RunLogSummary): RunResult | null {
  if (run.run_result) return run.run_result
  if (!run.disposition && !run.download_url && !run.error && run.status === 'success') {
    return null
  }
  return {
    disposition: (run.status === 'error' ? 'ESCALATE' : run.disposition || 'REVIEW') as RunResult['disposition'],
    flag_count: run.flag_count ?? (run.status === 'error' ? 1 : 0),
    output_branch: 'default',
    report_path: run.download_url || '',
    download_url: run.download_url || undefined,
    datasets: [],
    sections: {},
    executive_summary: run.run_error || run.error || 'Run executed.',
    workflow: run.workflow,
    run_id: run.run_id,
  }
}

/** Best-effort run-log row when opening output from Automations → Run History. */
export function buildRunLogFromAutomationRun(
  automationRun: AutomationRun,
  workflowLabel: string,
  persisted?: RunLogSummary | null,
): RunLogSummary {
  if (persisted?.run_id === automationRun.run_id) return persisted

  const finishedAt =
    automationRun.status === 'running'
      ? undefined
      : new Date(new Date(automationRun.triggered_at).getTime() + automationRun.duration_ms).toISOString()

  return {
    run_id: automationRun.run_id,
    workflow: workflowLabel,
    started_at: automationRun.triggered_at,
    finished_at: finishedAt,
    duration_ms: automationRun.duration_ms,
    status: automationRun.status === 'running' ? 'warning' : automationRun.status,
    error: automationRun.error ?? undefined,
    download_url: automationRun.download_url ?? undefined,
  }
}

/** Map a persisted run-log row into the same shape the output footer panel consumes. */
export function hydrateRunForOutputPanel(run: RunLogSummary): HydratedRunOutput {
  const persisted = run.run_log?.length ? run.run_log : null
  const runLog = (persisted ?? stepsToRunLog(run)) as RunLogEntry[]
  const runResult = fallbackRunResult(run)
  const runError = run.run_error ?? run.error ?? null
  const runTotalMs = run.duration_ms ?? null
  const artifacts = (run.artifacts ?? []) as RunArtifact[]

  return { runLog, runResult, runError, runTotalMs, artifacts }
}
