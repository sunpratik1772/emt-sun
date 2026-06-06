import { useEffect, useMemo, useState } from 'react'
import StudioOverlay from '../StudioOverlay'
import {
  ArcIcon,
  Activity,
  Trash2,
  RefreshCw,
  Search,
} from '../../icons/arc'
import type { RunLogSummary as RunLog } from '../../services/api'
import { useClearRunLogs, useRunLogs } from '../../hooks/useLibraryQueries'
import { PanelEmpty, PanelError, PanelLoading, formatDur, formatTime, statusColor, SearchInput } from './shared'
import { useStudioSectionStore } from '../../store/studioSectionStore'

export function RunHistoryDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: runs = [], isLoading: loading, isFetching, isError, error, refetch } = useRunLogs(open)
  const focusedRunId = useStudioSectionStore((s) => s.runHistoryRunId)
  const focusAutoOpenModal = useStudioSectionStore((s) => s.runHistoryAutoOpenModal)
  const prefillRun = useStudioSectionStore((s) => s.runHistoryPrefill)
  const openRunOutputModal = useStudioSectionStore((s) => s.openRunOutputModal)
  const clearRunHistoryFocus = useStudioSectionStore((s) => s.clearRunHistoryFocus)
  const clearMutation = useClearRunLogs()
  const [searchQuery, setSearchQuery] = useState('')

  const filteredRuns = useMemo(() => {
    const query = searchQuery.toLowerCase().trim()
    if (!query) return runs
    return runs.filter((run) => {
      const workflowName = (run.workflow || '').toLowerCase()
      const runId = (run.run_id || '').toLowerCase()
      const errorText = (run.run_error || '').toLowerCase()
      return workflowName.includes(query) || runId.includes(query) || errorText.includes(query)
    })
  }, [runs, searchQuery])

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
      if (focusAutoOpenModal) {
        openRunOutputModal(idx >= 0 ? runs[idx] : found)
      }
      clearRunHistoryFocus()
      return
    }

    if (!loading && focusAutoOpenModal) {
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

  const stats = useMemo(() => ({
    total: runs.length,
    success: runs.filter((l) => l.status === 'success').length,
    error: runs.filter((l) => l.status === 'error').length,
    running: runs.filter((l) => l.status === 'running').length,
  }), [runs])

  const showLoading = loading && runs.length === 0

  const statusText = (status: string) => {
    if (status === 'success') return 'Succeeded'
    if (status === 'error') return 'Failed'
    if (status === 'running') return 'Running'
    if (status === 'warning') return 'Warning'
    return status
  }

  return (
    <StudioOverlay
      open={open}
      onClose={onClose}
      eyebrow="Execution log"
      title="Run History"
      subtitle="Every workflow run with status, duration, and rows processed. Newest first."
      bodyClass="ov__body--wide"
      footLeft={
        <>
          <button type="button" className="ov-bbtn" onClick={() => void refetch()}>
            <ArcIcon icon={RefreshCw} size={14} strokeWidth={2} className={isFetching ? 'animate-spin' : undefined} />
            Refresh
          </button>
          <button
            type="button"
            className="ov-bbtn"
            onClick={() => clearMutation.mutate()}
          >
            <ArcIcon icon={Trash2} size={14} strokeWidth={2} />
            Clear runs
          </button>
        </>
      }
      footRight={<span className="ov__foot-meta">{runs.length} runs</span>}
    >
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
      {!showLoading && !isError && runs.length > 0 && (
        <>
          <div className="flex items-center justify-end mb-4">
            <SearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search runs…"
              icon={<Search size={13} />}
              style={{ width: 220 }}
            />
          </div>
          <div className="rh-strip">
            <div>
              <div className="rh-stat__v">{stats.total}</div>
              <div className="rh-stat__l">Total</div>
            </div>
            <div>
              <div className="rh-stat__v" style={{ color: 'var(--success)' }}>{stats.success}</div>
              <div className="rh-stat__l">Success</div>
            </div>
            <div>
              <div className="rh-stat__v" style={{ color: 'var(--danger)' }}>{stats.error}</div>
              <div className="rh-stat__l">Error</div>
            </div>
            <div>
              <div className="rh-stat__v" style={{ color: 'var(--running)' }}>{stats.running}</div>
              <div className="rh-stat__l">Running</div>
            </div>
          </div>
          {filteredRuns.length === 0 ? (
            <PanelEmpty icon={<ArcIcon icon={Activity} size={18} />}>
              {searchQuery ? `No runs found matching "${searchQuery}"` : 'No runs available.'}
            </PanelEmpty>
          ) : (
            <div className="runs-table">
              <div className="runs-row runs-row--head">
                <span />
                <span>Workflow</span>
                <span>When</span>
                <span>Duration</span>
                <span>Rows</span>
                <span>Status</span>
              </div>
              {filteredRuns.map((log, i) => {
                const hasErr = log.status === 'error' && log.run_error
                const rowCount = log.run_result ? log.run_result.row_count ?? log.run_result.rows ?? null : null
                const tone = statusColor(log.status)
                return (
                  <div
                    className="runs-row"
                    key={`${log.run_id}-${i}`}
                    data-testid={`run-log-row-${i}`}
                    onClick={() => openRunOutputModal(log)}
                    style={{ cursor: 'pointer' }}
                  >
                    <span className="runs-status" style={{ background: tone }} />
                    <div style={{ minWidth: 0 }}>
                      <div className="runs-wf">{log.workflow ?? log.run_id}</div>
                      {hasErr ? (
                        <div className="runs-err truncate">{log.run_error}</div>
                      ) : (
                        <div className="runs-when" style={{ marginTop: 2 }}>
                          {log.node_count ?? 0} nodes
                        </div>
                      )}
                    </div>
                    <span className="runs-when">{formatTime(log.started_at)}</span>
                    <span className="runs-cell">{formatDur(log.duration_ms)}</span>
                    <span className="runs-cell">{rowCount == null ? '—' : rowCount.toLocaleString()}</span>
                    <span>
                      <span
                        className="runs-badge"
                        style={{
                          background: `color-mix(in srgb, ${tone} 13%, transparent)`,
                          color: tone,
                        }}
                      >
                        <span className="runs-status" style={{ background: tone, width: 6, height: 6 }} />
                        {statusText(log.status)}
                      </span>
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </StudioOverlay>
  )
}
