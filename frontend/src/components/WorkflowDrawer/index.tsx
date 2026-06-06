/**
 * Templates — saved workflows and Copilot drafts.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArcIcon,
  FileStack,
  Sparkles,
  Trash2,
  Loader2,
} from '../../icons/arc'
import StudioOverlay from '../StudioOverlay'
import { PanelEmpty, PanelError, PanelLoading } from '../drawers/shared'
import { useWorkflowStore } from '../../store/workflowStore'
import {
  useDeleteDraftFile,
  useDeleteWorkflowFile,
  useDraftsList,
  useWorkflowsList,
} from '../../hooks/useLibraryQueries'
import { toast } from '../../store/toastStore'
import WorkflowVoteButtons from '../WorkflowVoteButtons'
import { api, type StoredWorkflow } from '../../services/api'

type DrawerTab = 'saved' | 'drafts'
type SortBy = 'recent' | 'name'

const SORT_STORAGE_KEY = 'dbsherpa.wf-drawer.sort'

function readSortPreference(): SortBy {
  try {
    const v = window.localStorage.getItem(SORT_STORAGE_KEY)
    if (v === 'name' || v === 'recent') return v
  } catch {
    /* noop */
  }
  return 'recent'
}

function sortItems(items: StoredWorkflow[], sortBy: SortBy): StoredWorkflow[] {
  const copy = [...items]
  if (sortBy === 'name') {
    return copy.sort((a, b) =>
      (a.name || a.filename).localeCompare(b.name || b.filename, undefined, {
        sensitivity: 'base',
      }),
    )
  }
  return copy.sort((a, b) => (b.modified_ms ?? 0) - (a.modified_ms ?? 0))
}

export default function WorkflowDrawer() {
  const open = useWorkflowStore((s) => s.workflowDrawerOpen)
  const setOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const sourceFilename = useWorkflowStore((s) => s.sourceFilename)
  const sourceKind = useWorkflowStore((s) => s.sourceKind)
  const loadWorkflowFromFile = useWorkflowStore((s) => s.loadWorkflowFromFile)
  const loadDraftFromFile = useWorkflowStore((s) => s.loadDraftFromFile)

  const [tab, setTab] = useState<DrawerTab>('saved')
  const [sortBy, setSortBy] = useState<SortBy>(readSortPreference)
  const [focusIndex, setFocusIndex] = useState(0)
  const {
    data: saved = [],
    isLoading: savedLoading,
    isError: savedError,
    error: savedFetchError,
    refetch: refetchSaved,
  } = useWorkflowsList(open)
  const {
    data: drafts = [],
    isLoading: draftsLoading,
    isError: draftsError,
    error: draftsFetchError,
    refetch: refetchDrafts,
  } = useDraftsList(open)
  const deleteWorkflow = useDeleteWorkflowFile()
  const deleteDraft = useDeleteDraftFile()
  const [actionError, setActionError] = useState<string | null>(null)
  const [loadingFile, setLoadingFile] = useState<string | null>(null)
  const [deletingFile, setDeletingFile] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const listLoading = tab === 'saved' ? savedLoading : draftsLoading
  const listFetchError = tab === 'saved' ? savedFetchError : draftsFetchError
  const listHasError = tab === 'saved' ? savedError : draftsError
  const refetchList = tab === 'saved' ? refetchSaved : refetchDrafts

  const items = tab === 'saved' ? saved : drafts

  const filteredSorted = useMemo(() => sortItems(items, sortBy), [items, sortBy])

  useEffect(() => {
    setFocusIndex(0)
  }, [tab, sortBy])

  useEffect(() => {
    if (focusIndex >= filteredSorted.length) {
      setFocusIndex(Math.max(0, filteredSorted.length - 1))
    }
  }, [filteredSorted.length, focusIndex])

  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-wf-focus-index="${focusIndex}"]`)
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [focusIndex, filteredSorted])

  function setSort(next: SortBy) {
    setSortBy(next)
    try {
      window.localStorage.setItem(SORT_STORAGE_KEY, next)
    } catch {
      /* noop */
    }
  }

  const handleOpen = useCallback(
    async (filename: string) => {
      setLoadingFile(filename)
      setActionError(null)
      try {
        const dag =
          tab === 'saved'
            ? await api.getWorkflow(filename)
            : await api.getDraft(filename)
        if (tab === 'saved') loadWorkflowFromFile(filename, dag)
        else loadDraftFromFile(filename, dag)
        setOpen(false)
      } catch (e) {
        const message = (e as Error).message
        setActionError(message)
        toast.error(`Could not open workflow: ${message}`)
      } finally {
        setLoadingFile(null)
      }
    },
    [tab, loadWorkflowFromFile, loadDraftFromFile, setOpen],
  )

  useEffect(() => {
    if (!open) return

    const onKey = (e: KeyboardEvent) => {
      const target = e.target
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement
      ) {
        return
      }

      if (listLoading || filteredSorted.length === 0) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setFocusIndex((i) => Math.min(i + 1, filteredSorted.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setFocusIndex((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        const item = filteredSorted[focusIndex]
        if (item && !loadingFile && !deletingFile) {
          e.preventDefault()
          void handleOpen(item.filename)
        }
      }
    }

    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, listLoading, filteredSorted, focusIndex, loadingFile, deletingFile, handleOpen])

  async function handleDelete(filename: string) {
    const ok = window.confirm(
      tab === 'drafts'
        ? `Delete draft "${filename}"?`
        : `Delete saved workflow "${filename}"? This cannot be undone.`,
    )
    if (!ok) return
    setDeletingFile(filename)
    setActionError(null)
    try {
      if (tab === 'saved') await deleteWorkflow.mutateAsync(filename)
      else await deleteDraft.mutateAsync(filename)
      toast.success(tab === 'saved' ? 'Workflow deleted' : 'Draft deleted')
    } catch (e) {
      const message = (e as Error).message
      setActionError(message)
      toast.error(`Delete failed: ${message}`)
    } finally {
      setDeletingFile(null)
    }
  }

  const savedCount = saved.length
  const draftsCount = drafts.length
  const displayError =
    actionError ??
    (listHasError ? (listFetchError as Error)?.message ?? 'Failed to load workflows' : null)

  return (
    <StudioOverlay
      open={open}
      onClose={() => setOpen(false)}
      eyebrow="Saved workflows"
      title="Templates"
      subtitle="Saved workflows and Sherpa drafts — open one in the canvas to continue."
      ariaLabel="Templates"
      bodyClass="ov__body--wide ov__body--mng"
    >
      <div className="screen__inner h-full flex flex-col" style={{ minHeight: '100%' }}>
        <div className="wfp-bar">
          <div className="wfp-tabs" role="tablist" aria-label="Template lists">
            <TabButton
              label="Saved"
              icon={<ArcIcon icon={FileStack} size={14} strokeWidth={2} />}
              active={tab === 'saved'}
              count={savedCount}
              onClick={() => setTab('saved')}
            />
            <TabButton
              label="Drafts"
              icon={<ArcIcon icon={Sparkles} size={14} strokeWidth={2} />}
              active={tab === 'drafts'}
              count={draftsCount}
              onClick={() => setTab('drafts')}
            />
          </div>
          <div className="wfp-sort" role="group" aria-label="Sort order">
            <button
              type="button"
              className={`wfp-sort__btn${sortBy === 'recent' ? ' wfp-sort__btn--on' : ''}`}
              onClick={() => setSort('recent')}
            >
              Recent
            </button>
            <button
              type="button"
              className={`wfp-sort__btn${sortBy === 'name' ? ' wfp-sort__btn--on' : ''}`}
              onClick={() => setSort('name')}
            >
              Name
            </button>
          </div>
        </div>

        <div ref={listRef} className="wfp-grid">
          {listLoading && (
            <div className="wfp-status">
              <PanelLoading />
            </div>
          )}

          {displayError && (
            <div className="wfp-status wfp-status--error">
              <div>{displayError}</div>
              {listHasError && (
                <button type="button" className="ov-bbtn" onClick={() => void refetchList()}>
                  Retry
                </button>
              )}
            </div>
          )}

          {!listLoading && filteredSorted.length === 0 && !listHasError && (
            <div className="wfp-empty">
              <PanelEmpty icon={<ArcIcon icon={FileStack} size={18} />}>
                {tab === 'saved'
                  ? 'No saved workflows yet. Build one in Studio, then save from the top bar.'
                  : 'No drafts yet. Sherpa and manual edits appear here automatically.'}
              </PanelEmpty>
            </div>
          )}

          {filteredSorted.map((w, index) => {
            const isCurrent =
              w.filename === sourceFilename &&
              ((tab === 'saved' && sourceKind === 'saved') ||
                (tab === 'drafts' && sourceKind === 'draft'))
            const loading = w.filename === loadingFile
            const deleting = w.filename === deletingFile
            const focused = index === focusIndex
            return (
              <TemplateCard
                key={w.filename}
                item={w}
                tab={tab}
                focusIndex={index}
                active={isCurrent}
                focused={focused}
                loading={loading}
                deleting={deleting}
                onOpen={() => handleOpen(w.filename)}
                onDelete={() => handleDelete(w.filename)}
                onHover={() => setFocusIndex(index)}
              />
            )
          })}
        </div>
      </div>
    </StudioOverlay>
  )
}

function TabButton({
  label,
  icon,
  active,
  count,
  onClick,
}: {
  label: string
  icon: React.ReactNode
  active: boolean
  count: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`wfp-tab${active ? ' wfp-tab--on' : ''}`}
    >
      {icon}
      <span>{label}</span>
      <span className="wfp-tab__count">{count}</span>
    </button>
  )
}

function TemplateCard({
  item: w,
  tab,
  focusIndex,
  active,
  focused,
  loading,
  deleting,
  onOpen,
  onDelete,
  onHover,
}: {
  item: StoredWorkflow
  tab: DrawerTab
  focusIndex: number
  active: boolean
  focused: boolean
  loading: boolean
  deleting: boolean
  onOpen: () => void
  onDelete: () => void
  onHover: () => void
}) {
  return (
    <article
      role="button"
      tabIndex={focused ? 0 : -1}
      data-wf-focus-index={focusIndex}
      data-testid={`workflow-item-${w.filename}`}
      className={[
        'wfp-card',
        active ? 'wfp-card--active' : '',
        focused ? 'wfp-card--focused' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{ cursor: loading ? 'progress' : 'pointer' }}
      onMouseEnter={onHover}
      onClick={loading || deleting ? undefined : onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          if (!loading && !deleting) onOpen()
        }
      }}
    >
      <div className="wfp-card__top">
        <span className="wfp-card__ico" aria-hidden>
          <ArcIcon
            icon={tab === 'saved' ? FileStack : Sparkles}
            size={15}
            strokeWidth={2}
          />
        </span>
        {w.modified_ms != null ? (
          <span className="wfp-card__date">{relativeTime(w.modified_ms)}</span>
        ) : null}
      </div>

      <div className="wfp-card__name">{w.name || w.filename}</div>
      {w.description ? <p className="wfp-card__desc">{w.description}</p> : null}

      <div className="wfp-card__foot">
        <span className="wfp-card__file">{w.filename}</span>
        <div className="wfp-card__foot-end">
          {tab === 'saved' ? (
            <WorkflowVoteButtons
              filename={w.filename}
              upvoteCount={w.upvote_count ?? 0}
              downvoteCount={w.downvote_count ?? 0}
              compact
            />
          ) : null}
          {w.node_count != null ? (
            <span className="wfp-card__nodes">{w.node_count} nodes</span>
          ) : null}
          <button
            type="button"
            className="wfp-card__delete"
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            disabled={loading || deleting}
            aria-label="Delete"
            title="Delete"
          >
            {deleting ? (
              <ArcIcon icon={Loader2} size={13} strokeWidth={2.5} className="animate-spin" />
            ) : (
              <ArcIcon icon={Trash2} size={13} strokeWidth={2.5} />
            )}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="wfp-card__loading">
          <ArcIcon icon={Loader2} size={14} strokeWidth={2.5} className="animate-spin" />
        </div>
      ) : null}
    </article>
  )
}

function relativeTime(epochMs: number): string {
  const delta = Date.now() - epochMs
  if (delta < 60_000) return 'just now'
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m ago`
  if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)}h ago`
  const d = new Date(epochMs)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
