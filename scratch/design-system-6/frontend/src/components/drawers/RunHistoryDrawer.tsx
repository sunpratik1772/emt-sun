import { useEffect, useMemo, useState } from 'react'
import SectionDrawer from '../SectionDrawer'
import { Button } from '../ui/Button'
import {
  ArcIcon, Activity, Trash2, Download, FileOutput,
  CheckCircle2, XCircle, ChevronRight, ChevronDown, ExternalLink, RefreshCw,
} from '../../icons/arc'
import type { RunLogSummary as RunLog } from '../../services/api'
import { useClearRunLogs, useRunLogs } from '../../hooks/useLibraryQueries'
import { generateStepsForRun } from './runHistoryUtils'
import { KV, PanelEmpty, PanelError, PanelLoading, Stat, StatusIcon, ToolbarButton, ListRow, formatDur, formatTime, statusColor } from './shared'
import { useStudioSectionStore } from '../../store/studioSectionStore'

export function RunHistoryDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: runs = [], isLoading: loading, isFetching, isError, error, refetch } = useRunLogs(open)
  const focusedRunId = useStudioSectionStore((s) => s.runHistoryRunId)
  const focusAutoOpenModal = useStudioSectionStore((s) => s.runHistoryAutoOpenModal)
  const prefillRun = useStudioSectionStore((s) => s.runHistoryPrefill)
  const openRunOutputModal = useStudioSectionStore((s) => s.openRunOutputModal)
  const clearRunHistoryFocus = useStudioSectionStore((s) => s.clearRunHistoryFocus)
  const clearMutation = useClearRunLogs()
  const [activeIdx, setActiveIdx] = useState<number | null>(null)
  const [expandedStep, setExpandedStep] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !focusedRunId) return
    if (loading && !prefillRun) return

    const idx = runs.findIndex((r) => r.run_id === focusedRunId)
    const found =
      idx >= 0
        ? runs[idx]
        : prefillRun?.run_id === focusedRunId
          ? prefillRun
          : null

    if (found) {
      if (idx >= 0) {
        setActiveIdx(idx)
        setExpandedStep(null)
      }
      if (focusAutoOpenModal) {
        openRunOutputModal(idx >= 0 ? runs[idx] : found)
      }
      clearRunHistoryFocus()
      return
    }

    if (!loading && focusAutoOpenModal) {
      setActiveIdx(null)
      setExpandedStep(null)
      openRunOutputModal({
        run_id: focusedRunId,
        workflow: `Run ${focusedRunId}`,
        started_at: new Date().toISOString(),
        status: 'warning',
        run_log: [],
        run_result: null,
        run_error: `Run ${focusedRunId} was not found in run history.`,
      })
      clearRunHistoryFocus()
    }
  }, [
    open,
    focusedRunId,
    focusAutoOpenModal,
    loading,
    runs,
    prefillRun,
    openRunOutputModal,
    clearRunHistoryFocus,
  ])

  const handleViewOutput = (run: RunLog) => {
    openRunOutputModal(run)
  }

  const stats = useMemo(() => {
    return {
      total: runs.length,
      success: runs.filter((l) => l.status === 'success').length,
      error: runs.filter((l) => l.status === 'error').length,
      warn: runs.filter((l) => l.status === 'warning').length,
    }
  }, [runs])

  const activeRun = activeIdx != null ? runs[activeIdx] : null
  const showLoading = loading && runs.length === 0

  return (
    <SectionDrawer
      open={open}
      onClose={onClose}
      title="Run History"
      subtitle="Execution history and step-by-step logs for your pipelines. Newest first."
      badge={runs.length ? String(runs.length) : undefined}
      width="100%"
      toolbar={
        <div className="flex items-center gap-1.5">
          <ToolbarButton onClick={() => void refetch()} icon={<ArcIcon icon={RefreshCw} size={11} strokeWidth={2} className={isFetching ? 'animate-spin' : undefined} />}>
            Refresh
          </ToolbarButton>
          <ToolbarButton
            onClick={() => {
              clearMutation.mutate(undefined, {
                onSuccess: () => setActiveIdx(null),
              })
            }}
            icon={<ArcIcon icon={Trash2} size={11} strokeWidth={2} />}
          >
            Clear runs
          </ToolbarButton>
        </div>
      }
    >
      {runs.length > 0 && (
        <div
          className="flex items-center gap-4 px-5 py-2.5 shrink-0"
          style={{ borderBottom: '1px solid var(--border-soft)', background: 'var(--bg-2)' }}
        >
          <Stat label="total" value={stats.total} />
          <Stat label="success" value={stats.success} color="var(--success)" />
          <Stat label="error" value={stats.error} color="var(--danger)" />
          <Stat label="warn" value={stats.warn} color="var(--warning)" />
        </div>
      )}

      <div className="flex h-full" style={{ minHeight: 0 }}>
        <div className="flex-1 min-w-0 overflow-y-auto studio-pane" style={{ maxWidth: 360 }}>
          {showLoading && <PanelLoading />}
          {isError && (
            <PanelError
              message={(error as Error)?.message ?? 'Failed to load run history'}
              onRetry={() => void refetch()}
            />
          )}

          {!showLoading && !isError && runs.length === 0 && (
            <PanelEmpty icon={<ArcIcon icon={Activity} size={18} />}>No runs yet. Hit Run on a workflow.</PanelEmpty>
          )}

          {!showLoading && !isError && runs.map((log, i) => (
            <ListRow
              key={`${log.run_id}-${i}`}
              selected={activeIdx === i}
              accentColor={statusColor(log.status)}
              testId={`run-log-row-${i}`}
              onClick={() => {
                setActiveIdx(i)
                setExpandedStep(null)
              }}
            >
              <StatusIcon status={log.status} />
              <div className="min-w-0 flex-1">
                <div
                  className="display truncate"
                  style={{ fontSize: 12, fontWeight: 510, color: 'var(--text-0)', letterSpacing: '-0.005em' }}
                >
                  {log.workflow ?? log.run_id}
                </div>
                <div
                  className="font-mono"
                  style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2, letterSpacing: '0.02em' }}
                >
                  {formatTime(log.started_at)} · {formatDur(log.duration_ms)}
                </div>
              </div>
            </ListRow>
          ))}
        </div>

        <div className="flex-1 min-w-0 overflow-y-auto studio-detail-pane">
          {!activeRun && <PanelEmpty icon={<ArcIcon icon={Activity} size={18} />}>Select a workflow run to view step execution details</PanelEmpty>}

          {activeRun && (
            <div>
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                <StatusIcon status={activeRun.status} large />
                <span
                  className="display"
                  style={{ fontSize: 13.5, fontWeight: 530, color: 'var(--text-0)', letterSpacing: '-0.005em' }}
                >
                  {activeRun.status}
                </span>
                {activeRun.disposition && (
                  <span
                    className="font-mono"
                    style={{
                      fontSize: 10,
                      padding: '2px 7px',
                      borderRadius: 4,
                      border: '1px solid var(--border-soft)',
                      background: 'var(--bg-2)',
                      color: 'var(--text-2)',
                      letterSpacing: '0.04em',
                      textTransform: 'uppercase',
                    }}
                  >
                    {activeRun.disposition}
                  </span>
                )}
                {typeof activeRun.flag_count === 'number' && activeRun.flag_count > 0 && (
                  <span
                    className="font-mono"
                    style={{
                      fontSize: 10,
                      padding: '2px 7px',
                      borderRadius: 4,
                      background: 'color-mix(in srgb, var(--danger) 12%, transparent)',
                      color: 'var(--danger)',
                      border: '1px solid color-mix(in srgb, var(--danger) 32%, transparent)',
                      letterSpacing: '0.02em',
                    }}
                  >
                    {activeRun.flag_count} flags
                  </span>
                )}
              </div>
              <h3
                className="display"
                style={{ fontSize: 16, fontWeight: 540, color: 'var(--text-0)', letterSpacing: '-0.018em', marginBottom: 12 }}
              >
                {activeRun.workflow ?? activeRun.run_id}
              </h3>

              <div className="grid grid-cols-2 gap-3" style={{ marginBottom: 20 }}>
                <KV label="Run ID" value={activeRun.run_id} mono />
                <KV label="Duration" value={formatDur(activeRun.duration_ms)} />
                <KV label="Started" value={formatTime(activeRun.started_at)} />
                <KV label="Finished" value={activeRun.finished_at ? formatTime(activeRun.finished_at) : '—'} />
                <KV label="Nodes Count" value={String(activeRun.node_count ?? '—')} />
                <KV label="Edges Count" value={String(activeRun.edge_count ?? '—')} />
              </div>

              {/* Step-by-Step Timeline Section */}
              <div style={{ marginBottom: 24 }}>
                <h4
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: 'var(--text-3)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: 12,
                  }}
                >
                  Step-by-Step Node Execution
                </h4>

                <div style={{ position: 'relative', paddingLeft: 12 }}>
                  {/* Vertical Timeline Track Line */}
                  <div
                    style={{
                      position: 'absolute',
                      left: 17,
                      top: 10,
                      bottom: 10,
                      width: 2,
                      background: 'var(--border-soft)',
                    }}
                  />

                  <div className="flex flex-col gap-3">
                    {generateStepsForRun(activeRun).map((step) => {
                      const isExpanded = expandedStep === step.id
                      const stepFailed = step.status === 'error'
                      return (
                        <div key={step.id} style={{ position: 'relative', zIndex: 1 }}>
                          <div
                            onClick={() => setExpandedStep(isExpanded ? null : step.id)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 12,
                              padding: '8px 12px',
                              background: isExpanded ? 'var(--bg-2)' : 'var(--bg-1)',
                              border: '1px solid var(--border-soft)',
                              borderRadius: 6,
                              cursor: 'pointer',
                              userSelect: 'none',
                              transition: 'background 120ms',
                            }}
                            onMouseEnter={(e) => {
                              if (!isExpanded) e.currentTarget.style.background = 'var(--bg-2)'
                            }}
                            onMouseLeave={(e) => {
                              if (!isExpanded) e.currentTarget.style.background = 'var(--bg-1)'
                            }}
                          >
                            {/* Step Indicator Dot/Icon */}
                            <div
                              style={{
                                width: 14,
                                height: 14,
                                borderRadius: '50%',
                                background: stepFailed
                                  ? 'var(--danger)'
                                  : 'var(--success)',
                                color: '#fff',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                              }}
                            >
                              <ArcIcon
                                icon={stepFailed ? XCircle : CheckCircle2}
                                size={12}
                                strokeWidth={2.5}
                              />
                            </div>

                            {/* Node Metadata & Label */}
                            <div className="flex-1 min-w-0">
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span
                                  className="display"
                                  style={{
                                    fontSize: 12,
                                    fontWeight: 550,
                                    color: stepFailed ? 'var(--danger)' : 'var(--text-0)',
                                  }}
                                >
                                  {step.label}
                                </span>
                                <span
                                  className="font-mono"
                                  style={{
                                    fontSize: 9.5,
                                    color: 'var(--text-3)',
                                    background: 'var(--bg-3)',
                                    padding: '1px 5px',
                                    borderRadius: 3,
                                  }}
                                >
                                  {step.type}
                                </span>
                              </div>
                            </div>

                            {/* Step Duration */}
                            <div className="font-mono" style={{ fontSize: 10.5, color: 'var(--text-2)' }}>
                              {step.duration_ms}ms
                            </div>

                            {/* Toggle Arrow */}
                            <ArcIcon icon={isExpanded ? ChevronDown : ChevronRight} size={11} style={{ color: 'var(--text-3)' }} />
                          </div>

                          {/* Expandable Step Outputs / Details */}
                          {isExpanded && (
                            <div
                              style={{
                                marginLeft: 26,
                                marginTop: 4,
                                padding: '8px 12px',
                                background: 'var(--bg-2)',
                                border: '1px solid var(--border-soft)',
                                borderRadius: 6,
                                fontSize: 11.5,
                                color: 'var(--text-1)',
                                lineHeight: 1.45,
                              }}
                            >
                              <div style={{ fontWeight: 500, color: 'var(--text-2)', marginBottom: 4 }}>
                                Step Status: <span style={{ color: stepFailed ? 'var(--danger)' : 'var(--success)' }}>{step.status === 'ok' ? 'Success' : 'Error'}</span>
                              </div>
                              <div>{step.output_preview}</div>
                              {step.error && (
                                <div
                                  className="font-mono"
                                  style={{
                                    marginTop: 6,
                                    padding: '6px 8px',
                                    background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
                                    color: 'var(--danger)',
                                    border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)',
                                    borderRadius: 4,
                                    fontSize: 10.5,
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                  }}
                                >
                                  {step.error}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              {activeRun.error && !expandedStep && (
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: 6,
                    background: 'color-mix(in srgb, var(--danger) 8%, transparent)',
                    border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
                    color: 'var(--danger)',
                    fontSize: 12,
                    lineHeight: 1.55,
                    marginBottom: 16,
                  }}
                >
                  {activeRun.error}
                </div>
              )}

              <div className="flex gap-2 mt-2">
                {activeRun.download_url && (
                  <a
                    href={activeRun.download_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2"
                    style={{
                      fontSize: 12,
                      color: 'var(--accent)',
                      textDecoration: 'none',
                      padding: '6px 10px',
                      borderRadius: 6,
                      border: '1px solid var(--border-soft)',
                    }}
                  >
                    <ArcIcon icon={Download} size={11} strokeWidth={2} />
                    Download report
                    <ArcIcon icon={ExternalLink} size={10} strokeWidth={2} style={{ opacity: 0.6 }} />
                  </a>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleViewOutput(activeRun)}
                  data-testid="run-history-view-output-button"
                  style={{ fontSize: 12, padding: '6px 10px' }}
                >
                  <ArcIcon icon={FileOutput} size={11} strokeWidth={2} />
                  View Output
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </SectionDrawer>
  )
}
