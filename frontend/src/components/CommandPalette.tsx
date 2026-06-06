import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArcIcon,
  LayoutGrid,
  LayoutTemplate,
  Boxes,
  Activity,
  Zap,
  Database,
  Lightbulb,
  Settings,
  Play,
  FilePlus2,
  Search,
  Sun,
  Moon,
  Sparkles,
  type LucideIcon,
} from '../icons/arc'
import { useCommandPaletteStore, focusNodeSearch } from '../store/commandPaletteStore'
import { useStudioSectionStore, type StudioSection } from '../store/studioSectionStore'
import { useWorkflowStore } from '../store/workflowStore'
import { useThemeStore } from '../store/themeStore'
import { useEscapeKey } from '../hooks/useFocusTrap'
import { useDraftsList, useWorkflowsList } from '../hooks/useLibraryQueries'
import { api } from '../services/api'
import { toast } from '../store/toastStore'

type CommandGroup = 'Navigate' | 'Workflow' | 'Library' | 'Appearance'

interface CommandAction {
  id: string
  label: string
  hint?: string
  group: CommandGroup
  icon: LucideIcon
  keywords?: string[]
  run: () => void | Promise<void>
}

export default function CommandPalette() {
  const open = useCommandPaletteStore((s) => s.open)
  const setOpen = useCommandPaletteStore((s) => s.setOpen)
  const setSection = useStudioSectionStore((s) => s.setSection)
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggle)
  const { data: saved = [] } = useWorkflowsList(open)
  const { data: drafts = [] } = useDraftsList(open)
  const [query, setQuery] = useState('')
  const [activeIdx, setActiveIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const actions = useMemo<CommandAction[]>(() => {
    const close = () => setOpen(false)
    const openSection = (section: Exclude<StudioSection, null>) => {
      setSection(section)
      close()
    }

    return [
      {
        id: 'ask-sherpa',
        label: 'Ask Sherpa',
        hint: 'Copilot',
        group: 'Navigate',
        icon: Sparkles,
        keywords: ['copilot', 'agent', 'ai', 'build', 'workflow'],
        run: () => {
          useWorkflowStore.getState().setRightPanelMode('copilot')
          setSection(null)
          close()
        },
      },
      {
        id: 'workflow',
        label: 'Go to workflow canvas',
        group: 'Navigate',
        icon: LayoutGrid,
        keywords: ['canvas', 'editor', 'home'],
        run: () => {
          setSection(null)
          close()
        },
      },
      {
        id: 'templates',
        label: 'Open templates',
        group: 'Navigate',
        icon: LayoutTemplate,
        keywords: ['saved', 'drafts', 'workflows'],
        run: () => {
          useWorkflowStore.getState().setWorkflowDrawerOpen(true)
          close()
        },
      },
      {
        id: 'nodes',
        label: 'Open node library',
        group: 'Navigate',
        icon: Boxes,
        run: () => openSection('nodes'),
      },
      {
        id: 'run-history',
        label: 'Open run history',
        group: 'Navigate',
        icon: Activity,
        run: () => openSection('run-history'),
      },
      {
        id: 'automations',
        label: 'Open automations',
        group: 'Navigate',
        icon: Zap,
        run: () => openSection('automations'),
      },
      {
        id: 'data',
        label: 'Open data sources',
        group: 'Navigate',
        icon: Database,
        run: () => openSection('data'),
      },
      {
        id: 'skills',
        label: 'Open skills',
        group: 'Navigate',
        icon: Lightbulb,
        run: () => openSection('skills'),
      },
      {
        id: 'settings',
        label: 'Open settings',
        group: 'Navigate',
        icon: Settings,
        run: () => openSection('settings'),
      },
      {
        id: 'search-nodes',
        label: 'Search nodes',
        hint: 'Palette',
        group: 'Workflow',
        icon: Search,
        keywords: ['palette', 'find'],
        run: () => {
          close()
          focusNodeSearch()
        },
      },
      {
        id: 'new-workflow',
        label: 'New workflow',
        group: 'Workflow',
        icon: FilePlus2,
        run: () => {
          useWorkflowStore.getState().newBlankWorkflow()
          setSection(null)
          close()
        },
      },
      {
        id: 'run-workflow',
        label: 'Run workflow',
        group: 'Workflow',
        icon: Play,
        run: () => {
          document.querySelector<HTMLButtonElement>('[data-testid="run-workflow-btn"]')?.click()
          close()
        },
      },
      {
        id: 'toggle-theme',
        label: theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode',
        group: 'Appearance',
        icon: theme === 'dark' ? Sun : Moon,
        keywords: ['theme', 'dark', 'light'],
        run: () => {
          toggleTheme()
          close()
        },
      },
    ]
  }, [setOpen, setSection, theme, toggleTheme])

  const libraryActions = useMemo<CommandAction[]>(() => {
    const close = () => setOpen(false)
    const loadWorkflowFromFile = useWorkflowStore.getState().loadWorkflowFromFile
    const loadDraftFromFile = useWorkflowStore.getState().loadDraftFromFile

    const rows = [
      ...saved.map((w) => ({ ...w, kind: 'saved' as const })),
      ...drafts.map((w) => ({ ...w, kind: 'draft' as const })),
    ]

    return rows.map((w) => {
      const name = w.name || w.filename.replace(/\.json$/i, '')
      return {
        id: `library-${w.kind}-${w.filename}`,
        label: name,
        hint: w.kind === 'draft' ? 'Draft' : 'Workflow',
        group: 'Library' as const,
        icon: LayoutTemplate,
        keywords: [w.filename, w.kind, name.toLowerCase()],
        run: async () => {
          try {
            const dag = w.kind === 'draft' ? await api.getDraft(w.filename) : await api.getWorkflow(w.filename)
            if (w.kind === 'draft') loadDraftFromFile(w.filename, dag)
            else loadWorkflowFromFile(w.filename, dag)
            setSection(null)
            close()
          } catch (e) {
            toast.error(`Could not open workflow: ${(e as Error).message}`)
          }
        },
      }
    })
  }, [drafts, saved, setOpen, setSection])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const commandMatches = q
      ? actions.filter((action) => {
          const haystack = [action.label, action.group, ...(action.keywords ?? [])].join(' ').toLowerCase()
          return haystack.includes(q)
        })
      : actions

    const libraryMatches = q
      ? libraryActions.filter((action) => {
          const haystack = [action.label, action.hint ?? '', ...(action.keywords ?? [])].join(' ').toLowerCase()
          return haystack.includes(q)
        })
      : []

    return [...commandMatches, ...libraryMatches]
  }, [actions, libraryActions, query])

  useEffect(() => {
    setActiveIdx(0)
  }, [query, open])

  useEffect(() => {
    if (!open) {
      setQuery('')
      return
    }
    const id = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(id)
  }, [open])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'k') return
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || (e.target as HTMLElement)?.isContentEditable) return
      e.preventDefault()
      useCommandPaletteStore.getState().toggle()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  useEscapeKey(() => setOpen(false), open)

  useEffect(() => {
    if (!open) return
    const item = listRef.current?.querySelector<HTMLElement>(`[data-cmd-idx="${activeIdx}"]`)
    item?.scrollIntoView({ block: 'nearest' })
  }, [activeIdx, open])

  if (!open) return null

  const groups = ['Navigate', 'Workflow', 'Library', 'Appearance'] as const

  function runActive() {
    const action = filtered[activeIdx]
    void action?.run()
  }

  return (
    <>
      <button
        type="button"
        className="command-palette-backdrop"
        aria-label="Close command palette"
        onClick={() => setOpen(false)}
      />
      <div className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <input
          ref={inputRef}
          className="command-palette__input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search commands and workflows…"
          aria-label="Search commands and workflows"
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setActiveIdx((i) => Math.min(i + 1, Math.max(filtered.length - 1, 0)))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setActiveIdx((i) => Math.max(i - 1, 0))
            } else if (e.key === 'Enter') {
              e.preventDefault()
              runActive()
            }
          }}
        />
        <div ref={listRef} className="max-h-[min(360px,50vh)] overflow-y-auto p-2">
          {filtered.length === 0 && (
            <div className="studio-meta px-3 py-6 text-center">No matching commands or workflows</div>
          )}
          {groups.map((group) => {
            const items = filtered.filter((a) => a.group === group)
            if (items.length === 0) return null
            return (
              <div key={group} className="mb-2 last:mb-0">
                <div className="studio-label px-2 py-1">{group}</div>
                {items.map((action) => {
                  const idx = filtered.indexOf(action)
                  return (
                    <button
                      key={action.id}
                      type="button"
                      data-cmd-idx={idx}
                      className={`command-palette__item${idx === activeIdx ? ' command-palette__item--active' : ''}`}
                      onMouseEnter={() => setActiveIdx(idx)}
                      onClick={() => void action.run()}
                    >
                      <ArcIcon icon={action.icon} size={14} style={{ color: 'var(--text-2)' }} />
                      <span>{action.label}</span>
                      {action.hint && <span className="studio-meta">{action.hint}</span>}
                      <kbd>↵</kbd>
                    </button>
                  )
                })}
              </div>
            )
          })}
        </div>
        <div
          className="flex items-center gap-3 px-3 py-2 studio-meta"
          style={{ borderTop: '1px solid var(--border-soft)', background: 'var(--bg-1)' }}
        >
          <span><kbd>↑↓</kbd> navigate</span>
          <span><kbd>↵</kbd> run</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </>
  )
}
