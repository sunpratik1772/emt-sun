/**
 * Supabase-style vertical navigation sidebar.
 *
 * Three modes (toggled via the bottom radio):
 *   • expanded   — full 200px with text labels
 *   • collapsed  — 52px icon-only rail
 *   • hover      — 52px rail that expands to 200px on hover (pushes content)
 *
 * Each item routes the workspace: clicking "Templates" opens the
 * WorkflowDrawer, section drawers, and sherpa panel, etc.
 * "Workflow" is the canvas and is always selected by default.
 */
import { useEffect, useState, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import {
  ArcIcon,
  LayoutGrid,
  LayoutTemplate,
  Boxes,
  Lightbulb,
  Database,
  Activity,
  Settings,
  ChevronsLeft,
  ChevronsRight,
  PanelLeft,
  ArrowUpRight,
  BookOpen,
  LogOut,
  Sliders,
  Code2,
  Zap,
  Workflow,
  Sun,
  Moon,
  Droplets,
  Palette,
  Check,
  type LucideIcon,
} from '../icons/arc'
import { useWorkflowStore } from '../store/workflowStore'
import { useStudioSectionStore, type StudioSection } from '../store/studioSectionStore'
import BrandMark from './BrandMark'
import { useAuthStore, userInitials } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'

type NavMode = 'expanded' | 'collapsed' | 'hover'

const STORAGE_KEY = 'dbsherpa.leftnav.mode'

interface NavItem {
  id: string
  label: string
  icon: LucideIcon
  isActive: (state: NavState) => boolean
  onClick: () => void
  disabled?: boolean
}

interface NavState {
  rightPanelMode: string | null
  drawerOpen: boolean
  section: StudioSection
}

export default function LeftNav() {
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const drawerOpen = useWorkflowStore((s) => s.workflowDrawerOpen)
  const setRightPanelMode = useWorkflowStore((s) => s.setRightPanelMode)
  const rightPanelMode = useWorkflowStore((s) => s.rightPanelMode)
  const environment = useWorkflowStore((s) => s.environment)
  const section = useStudioSectionStore((s) => s.section)
  const setSection = useStudioSectionStore((s) => s.setSection)

  const [mode, setMode] = useState<NavMode>(() => {
    if (typeof window === 'undefined') return 'hover'
    const saved = window.localStorage.getItem(STORAGE_KEY) as NavMode | null
    return saved ?? 'hover'
  })
  const [hovered, setHovered] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, mode)
    }
  }, [mode])

  const showLabels = mode === 'expanded' || (mode === 'hover' && hovered)
  const widthCollapsed = 52
  const widthExpanded = 200
  const navWidth = showLabels ? widthExpanded : widthCollapsed
  const isDashboard = section === 'dashboard'

  useEffect(() => {
    document.documentElement.style.setProperty('--left-nav-w', `${navWidth}px`)
    return () => {
      document.documentElement.style.removeProperty('--left-nav-w')
    }
  }, [navWidth])

  // Closing canvas overlays returns to the dashboard home.
  const goToDashboard = () => {
    setDrawerOpen(false)
    setSection('dashboard')
    if (rightPanelMode === 'copilot') setRightPanelMode(null)
  }

  // Workflow canvas — palette + editor view.
  const goToCanvas = () => {
    setDrawerOpen(false)
    setSection(null)
    if (rightPanelMode === 'copilot') setRightPanelMode(null)
  }

  const items: NavItem[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutGrid,
      isActive: (s) => s.section === 'dashboard' && !s.drawerOpen,
      onClick: goToDashboard,
    },
    {
      id: 'workflow',
      label: 'Workflow',
      icon: Workflow,
      isActive: (s) => !s.drawerOpen && s.rightPanelMode !== 'copilot' && s.section === null,
      onClick: goToCanvas,
    },
    {
      id: 'templates',
      label: 'Templates',
      icon: LayoutTemplate,
      isActive: (s) => s.drawerOpen,
      onClick: () => {
        setSection(null)
        setDrawerOpen(true)
      },
    },
    {
      id: 'nodes',
      label: 'Node Library',
      icon: Boxes,
      isActive: (s) => s.section === 'nodes',
      onClick: () => {
        setDrawerOpen(false)
        setSection(section === 'nodes' ? null : 'nodes')
      },
    },
    {
      id: 'skills',
      label: 'Skills',
      icon: Lightbulb,
      isActive: (s) => s.section === 'skills',
      onClick: () => {
        setDrawerOpen(false)
        setSection(section === 'skills' ? null : 'skills')
      },
    },
    {
      id: 'data',
      label: 'Data Sources',
      icon: Database,
      isActive: (s) => s.section === 'data',
      onClick: () => {
        setDrawerOpen(false)
        setSection(section === 'data' ? null : 'data')
      },
    },
    {
      id: 'run-history',
      label: 'Run History',
      icon: Activity,
      isActive: (s) => s.section === 'run-history',
      onClick: () => {
        setDrawerOpen(false)
        setSection(section === 'run-history' ? null : 'run-history')
      },
    },
    {
      id: 'automations',
      label: 'Automations',
      icon: Zap,
      isActive: (s) => s.section === 'automations',
      onClick: () => {
        setDrawerOpen(false)
        setSection(section === 'automations' ? null : 'automations')
      },
    },
  ]

  const settingsItem: NavItem = {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    isActive: (s) => s.section === 'settings',
    onClick: () => {
      setDrawerOpen(false)
      setSection(section === 'settings' ? null : 'settings')
    },
  }

  const navState: NavState = { rightPanelMode, drawerOpen, section }

  return (
    <aside
      className="panel-glass studio-left-nav shrink-0 flex flex-col relative h-full"
      style={{
        width: navWidth,
        flexShrink: 0,
        borderRight: '1px solid var(--border)',
        transition: 'width 180ms var(--ease-out)',
        overflow: 'visible',
        zIndex: 90,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Brand — compresses inside rail width; pushes main content when expanded */}
      <div
        className="shrink-0 flex items-center min-w-0"
        style={{
          height: 52,
          padding: showLabels ? '0 10px' : '0',
          justifyContent: showLabels ? 'flex-start' : 'center',
          borderBottom: '1px solid var(--border-soft)',
          gap: 8,
        }}
      >
        <BrandMark size={showLabels ? 22 : 24} />
        {showLabels && (
          <div className="flex flex-col min-w-0 flex-1 leading-tight">
            <span
              className="display truncate"
              style={{
                fontSize: 12,
                fontWeight: 560,
                color: 'var(--text-0)',
                letterSpacing: '-0.02em',
              }}
            >
              dbSherpa Studio
            </span>
          </div>
        )}
      </div>

      {/* Workspace selector — hidden on dashboard home for a calmer lobby */}
      {showLabels && !isDashboard && (
        <div
          className="shrink-0 px-2.5 pt-3 pb-2"
          style={{ borderBottom: '1px solid var(--border-soft)' }}
        >
          <div
            className="flex items-center gap-2"
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              background: 'var(--bg-0)',
              border: '1px solid var(--border-soft)',
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: 999,
                background: environment === 'prod' ? 'var(--success)' : environment === 'uat' ? '#f59e0b' : 'var(--accent)',
                boxShadow: `0 0 0 2px color-mix(in srgb, ${environment === 'prod' ? 'var(--success)' : environment === 'uat' ? '#f59e0b' : 'var(--accent)'} 18%, transparent)`,
              }}
            />
            <span
              className="display truncate flex-1 min-w-0"
              style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-0)' }}
            >
              Workspace
            </span>
            <span
              className="font-mono shrink-0"
              style={{
                fontSize: 9,
                padding: '1px 5px',
                borderRadius: 3,
                background: 'var(--bg-3)',
                border: '1px solid var(--border-soft)',
                color: 'var(--text-3)',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              {environment}
            </span>
          </div>
        </div>
      )}

      {/* Items */}
      <nav className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden py-2 flex flex-col gap-0.5 px-1.5">
        {items.map((it) => (
          <NavRow key={it.id} item={it} showLabels={showLabels} state={navState} />
        ))}
        <div
          style={{
            height: 1,
            background: 'var(--border-soft)',
            margin: '8px 6px',
          }}
        />
        <NavRow item={settingsItem} showLabels={showLabels} state={navState} />
        <Link
          to="/docs"
          className="flex items-center"
          style={{
            gap: 10,
            padding: showLabels ? '6px 10px' : 0,
            width: showLabels ? '100%' : 36,
            height: showLabels ? 32 : 36,
            marginInline: showLabels ? undefined : 'auto',
            borderRadius: showLabels ? 6 : 10,
            border: '1px solid transparent',
            color: 'var(--text-2)',
            textDecoration: 'none',
            fontFamily: 'inherit',
            textAlign: 'left',
            justifyContent: showLabels ? 'flex-start' : 'center',
            transition: 'background 120ms, color 120ms, border-color 120ms',
          }}
          onMouseEnter={(e) => {
            ;(e.currentTarget as HTMLElement).style.background = 'var(--bg-2)'
            ;(e.currentTarget as HTMLElement).style.color = 'var(--text-0)'
          }}
          onMouseLeave={(e) => {
            ;(e.currentTarget as HTMLElement).style.background = 'transparent'
            ;(e.currentTarget as HTMLElement).style.color = 'var(--text-2)'
          }}
        >
          <ArcIcon icon={BookOpen} size={15} className="shrink-0" />
          {showLabels && (
            <span
              className="display truncate flex-1 min-w-0"
              style={{
                fontSize: 12.5,
                fontWeight: 460,
                letterSpacing: '-0.005em',
              }}
            >
              Docs
            </span>
          )}
          {showLabels && <ArcIcon icon={ArrowUpRight} size={14} style={{ flexShrink: 0, opacity: 0.5 }} />}
        </Link>
      </nav>

      {/* Sidebar control — compact on dashboard home */}
      <div
        className="shrink-0"
        style={{
          padding: showLabels && !isDashboard ? '10px' : '8px 4px',
          borderTop: '1px solid var(--border-soft)',
        }}
      >
        {showLabels && !isDashboard ? (
          <div>
            <div
              className="font-mono"
              style={{
                fontSize: 9.5,
                color: 'var(--text-3)',
                letterSpacing: '0.10em',
                textTransform: 'uppercase',
                padding: '0 4px 6px',
              }}
            >
              Sidebar control
            </div>
            <div className="flex flex-col" style={{ gap: 1 }}>
              <ModeOption value="expanded" current={mode} onClick={() => setMode('expanded')}>
                Expanded
              </ModeOption>
              <ModeOption value="collapsed" current={mode} onClick={() => setMode('collapsed')}>
                Collapsed
              </ModeOption>
              <ModeOption value="hover" current={mode} onClick={() => setMode('hover')}>
                Expand on hover
              </ModeOption>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() =>
              setMode((m) => (m === 'collapsed' ? 'expanded' : m === 'expanded' ? 'hover' : 'collapsed'))
            }
            title={
              mode === 'collapsed'
                ? 'Expand sidebar'
                : (mode as string) === 'expanded'
                  ? 'Switch to expand-on-hover'
                  : 'Collapse sidebar'
            }
            aria-label="Toggle sidebar mode"
            className="w-full flex items-center justify-center"
            style={{
              height: 30,
              borderRadius: 6,
              background: 'transparent',
              color: 'var(--text-3)',
              border: '1px solid transparent',
              cursor: 'pointer',
              transition: 'background 140ms, color 140ms, border-color 140ms',
            }}
            onMouseEnter={(e) => {
              ;(e.currentTarget as HTMLElement).style.background = 'var(--bg-2)'
              ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--border-soft)'
              ;(e.currentTarget as HTMLElement).style.color = 'var(--text-0)'
            }}
            onMouseLeave={(e) => {
              ;(e.currentTarget as HTMLElement).style.background = 'transparent'
              ;(e.currentTarget as HTMLElement).style.borderColor = 'transparent'
              ;(e.currentTarget as HTMLElement).style.color = 'var(--text-3)'
            }}
          >
            {mode === 'collapsed' ? (
              <ArcIcon icon={ChevronsRight} size={13} />
            ) : mode === 'hover' ? (
              <ArcIcon icon={PanelLeft} size={13} />
            ) : (
              <ArcIcon icon={ChevronsLeft} size={13} />
            )}
          </button>
        )}
      </div>

      {/* Theme Switcher Popover */}
      <ThemePopover showLabels={showLabels} />

      {/* User profile row */}
      <UserProfileRow showLabels={showLabels} sidebarMode={mode} />
    </aside>
  )
}

function NavRow({
  item,
  showLabels,
  state,
}: {
  item: NavItem
  showLabels: boolean
  state: NavState
}) {
  const Icon = item.icon
  const active = item.isActive(state)
  const square = !showLabels
  return (
    <button
      type="button"
      onClick={item.onClick}
      disabled={item.disabled}
      aria-current={active ? 'page' : undefined}
      title={item.disabled ? `${item.label} (coming soon)` : item.label}
      className="flex items-center w-full"
      style={{
        gap: 10,
        padding: showLabels ? '6px 10px' : 0,
        width: square ? 36 : '100%',
        height: square ? 36 : 32,
        marginInline: square ? 'auto' : undefined,
        borderRadius: square ? 10 : 6,
        background: active ? 'var(--bg-3)' : 'transparent',
        border: active ? '1px solid var(--border-strong)' : '1px solid transparent',
        color: item.disabled ? 'var(--text-3)' : active ? 'var(--text-0)' : 'var(--text-1)',
        cursor: item.disabled ? 'not-allowed' : 'pointer',
        opacity: item.disabled ? 0.55 : 1,
        fontFamily: 'inherit',
        textAlign: 'left',
        justifyContent: showLabels ? 'flex-start' : 'center',
        transition:
          'background 120ms, color 120ms, border-color 120ms',
      }}
      onMouseEnter={(e) => {
        if (item.disabled || active) return
        ;(e.currentTarget as HTMLElement).style.background = 'var(--bg-2)'
        ;(e.currentTarget as HTMLElement).style.color = 'var(--text-0)'
      }}
      onMouseLeave={(e) => {
        if (item.disabled || active) return
        ;(e.currentTarget as HTMLElement).style.background = 'transparent'
        ;(e.currentTarget as HTMLElement).style.color = 'var(--text-1)'
      }}
    >
      <ArcIcon icon={Icon} size={15} className="shrink-0" />
      {showLabels && (
        <span
          className="display truncate"
          style={{
            fontSize: 12.5,
            fontWeight: active ? 530 : 460,
            letterSpacing: '-0.005em',
          }}
        >
          {item.label}
        </span>
      )}
    </button>
  )
}

function ModeOption({
  value,
  current,
  onClick,
  children,
}: {
  value: NavMode
  current: NavMode
  onClick: () => void
  children: React.ReactNode
}) {
  const active = value === current
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center w-full"
      style={{
        gap: 8,
        padding: '5px 8px',
        borderRadius: 5,
        background: active ? 'var(--bg-2)' : 'transparent',
        border: '1px solid transparent',
        color: active ? 'var(--text-0)' : 'var(--text-2)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        textAlign: 'left',
        fontSize: 12,
        fontWeight: active ? 500 : 440,
        letterSpacing: '-0.005em',
        transition: 'background 120ms, color 120ms',
      }}
      onMouseEnter={(e) => {
        if (active) return
        ;(e.currentTarget as HTMLElement).style.color = 'var(--text-0)'
      }}
      onMouseLeave={(e) => {
        if (active) return
        ;(e.currentTarget as HTMLElement).style.color = 'var(--text-2)'
      }}
    >
      <span
        aria-hidden
        style={{
          width: 12,
          height: 12,
          borderRadius: 999,
          border: `1.5px solid ${active ? 'var(--accent)' : 'var(--border-strong)'}`,
          background: 'transparent',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        {active && (
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: 999,
              background: 'var(--accent)',
            }}
          />
        )}
      </span>
      <span>{children}</span>
    </button>
  )
}

function AccountMenuButton({
  onClick,
  icon: Icon,
  label,
  testId,
}: {
  onClick: () => void
  icon: LucideIcon
  label: string
  testId?: string
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      data-testid={testId}
      className="w-full flex items-center gap-2"
      style={{
        padding: '8px 10px',
        borderRadius: 5,
        background: 'transparent',
        color: 'var(--text-1)',
        border: '1px solid transparent',
        fontSize: 12,
        fontFamily: 'inherit',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'background 120ms, color 120ms',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-2)'
        ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-0)'
      }}
      onMouseLeave={(e) => {
        ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
        ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-1)'
      }}
    >
      <ArcIcon icon={Icon} size={12} />
      <span>{label}</span>
    </button>
  )
}

function UserProfileRow({ showLabels, sidebarMode }: { showLabels: boolean; sidebarMode: NavMode }) {
  const user = useAuthStore((s) => s.user)
  const refresh = useAuthStore((s) => s.refresh)
  const logout = useAuthStore((s) => s.logout)
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggle)
  const setSection = useStudioSectionStore((s) => s.setSection)
  const setDrawerOpen = useWorkflowStore((s) => s.setWorkflowDrawerOpen)
  const [open, setOpen] = useState(false)
  const [apiKeyModalOpen, setApiKeyModalOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [menuStyle, setMenuStyle] = useState<{ left: number; bottom: number } | null>(null)
  const ref = useRef<HTMLDivElement | null>(null)
  const buttonRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (!user) void refresh()
  }, [user, refresh])

  useEffect(() => {
    if (!open) return
    function handle(e: MouseEvent) {
      const target = e.target as Node
      if (ref.current?.contains(target)) return
      if (document.getElementById('user-account-menu')?.contains(target)) return
      setOpen(false)
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('mousedown', handle)
    window.addEventListener('keydown', handleKey)
    return () => {
      window.removeEventListener('mousedown', handle)
      window.removeEventListener('keydown', handleKey)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    function updatePosition() {
      const rect = buttonRef.current?.getBoundingClientRect()
      if (!rect) return
      const menuWidth = 240
      let left = rect.left
      if (left + menuWidth > window.innerWidth - 8) {
        left = Math.max(8, window.innerWidth - menuWidth - 8)
      }
      setMenuStyle({ left, bottom: window.innerHeight - rect.top + 6 })
    }
    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open, showLabels, sidebarMode])

  const initials = userInitials(user)

  function openSettings() {
    setOpen(false)
    setDrawerOpen(false)
    setSection('settings')
  }

  const accountMenu =
    open && menuStyle
      ? createPortal(
          <div
            id="user-account-menu"
            data-testid="user-popover"
            role="menu"
            style={{
              position: 'fixed',
              left: menuStyle.left,
              bottom: menuStyle.bottom,
              width: 240,
              padding: 4,
              borderRadius: 8,
              background: 'var(--panel-glass-bg)',
              backdropFilter: 'saturate(140%) blur(14px)',
              WebkitBackdropFilter: 'saturate(140%) blur(14px)',
              border: '1px solid var(--border-strong)',
              boxShadow: '0 -14px 32px -14px rgba(0,0,0,0.35)',
              zIndex: 10000,
              fontFamily: 'inherit',
            }}
          >
            <div style={{ padding: '10px 10px 8px', borderBottom: '1px solid var(--border-soft)' }}>
              <div
                className="display truncate"
                style={{ fontSize: 12.5, fontWeight: 540, color: 'var(--text-0)', letterSpacing: '-0.005em' }}
              >
                {user?.name ?? 'Not signed in'}
              </div>
              <div
                className="font-mono truncate"
                style={{ fontSize: 10.5, color: 'var(--text-3)', marginTop: 2, letterSpacing: 0 }}
              >
                {user?.email ?? '—'}
              </div>
            </div>

            <AccountMenuButton onClick={openSettings} icon={Sliders} label="Settings" />

            <AccountMenuButton
              onClick={() => {
                setOpen(false)
                setApiKeyModalOpen(true)
              }}
              icon={Code2}
              label="Developer & API Keys"
            />

            <div style={{ height: 1, background: 'var(--border-soft)', margin: '4px 0' }} />

            <AccountMenuButton
              onClick={async () => {
                setOpen(false)
                await logout()
                window.location.replace('/login')
              }}
              icon={LogOut}
              label="Sign out"
              testId="logout-btn"
            />
          </div>,
          document.body,
        )
      : null

  return (
    <div
      ref={ref}
      className="shrink-0 relative"
      style={{
        borderTop: '1px solid var(--border-soft)',
        padding: showLabels ? '8px 10.5px' : '8px 0',
        display: 'flex',
        justifyContent: showLabels ? 'flex-start' : 'center',
        alignItems: 'center',
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={user ? `${user.name} · ${user.email}` : 'Account'}
        aria-label="Account menu"
        aria-expanded={open}
        aria-haspopup="menu"
        data-testid="user-avatar-btn"
        className="flex items-center text-left"
        style={{
          width: '100%',
          background: open ? 'var(--bg-2)' : 'transparent',
          border: 'none',
          borderRadius: 8,
          padding: showLabels ? '4px 2px' : 0,
          cursor: 'pointer',
          fontFamily: 'inherit',
          gap: 10,
          minWidth: 0,
          justifyContent: showLabels ? 'flex-start' : 'center',
        }}
      >
        <div
          className="flex items-center justify-center shrink-0"
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'var(--bg-3)',
            color: 'var(--text-0)',
            border: '1px solid var(--border-strong)',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '-0.01em',
            overflow: 'hidden',
          }}
        >
          {user?.picture ? (
            <img
              src={user.picture}
              alt=""
              referrerPolicy="no-referrer"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={(e) => {
                ;(e.currentTarget as HTMLImageElement).style.display = 'none'
              }}
            />
          ) : (
            <span>{initials}</span>
          )}
        </div>
        {showLabels && (
          <div className="flex-1 min-w-0" style={{ lineHeight: 1.2 }}>
            <div
              className="display truncate"
              style={{
                fontSize: 12.5,
                fontWeight: 540,
                color: 'var(--text-0)',
                letterSpacing: '-0.005em',
              }}
            >
              {user?.name ?? 'Not signed in'}
            </div>
            <div
              className="font-mono truncate"
              style={{
                fontSize: 10,
                color: 'var(--text-3)',
                marginTop: 1,
              }}
            >
              {user?.email ?? '—'}
            </div>
          </div>
        )}
      </button>

      {accountMenu}

      {apiKeyModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              background: 'var(--panel-glass-bg)',
              backdropFilter: 'saturate(140%) blur(16px)',
              border: '1px solid var(--border-strong)',
              borderRadius: 12,
              padding: 24,
              width: 440,
              boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
              fontFamily: 'inherit',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div
                style={{
                  background: 'var(--bg-3)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: '50%',
                  width: 32,
                  height: 32,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent)',
                }}
              >
                <ArcIcon icon={Code2} size={16} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-0)', margin: 0 }}>
                Developer API Credentials
              </h3>
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.5, marginBottom: 18 }}>
              Use these credentials to authenticate your enterprise client scripts and custom integrations with the dbSherpa Studio API. Keep this key secure and confidential.
            </p>

            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 10.5, fontWeight: 550, color: 'var(--text-3)', display: 'block', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                API Access Token (Live)
              </label>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: 'var(--bg-3)',
                  border: '1px solid var(--border-strong)',
                  borderRadius: 6,
                  padding: '6px 10px',
                  gap: 10,
                }}
              >
                <input
                  type="text"
                  readOnly
                  value="sk_live_dbsherpa_4f89d3a01e7e4088bc01d12cf88ad177"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: 'var(--text-0)',
                    fontFamily: 'monospace',
                    fontSize: 12,
                    flex: 1,
                  }}
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText("sk_live_dbsherpa_4f89d3a01e7e4088bc01d12cf88ad177")
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                  }}
                  style={{
                    background: 'var(--bg-2)',
                    border: '1px solid var(--border-strong)',
                    borderRadius: 4,
                    color: copied ? 'var(--success)' : 'var(--text-1)',
                    fontSize: 11,
                    padding: '4px 8px',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <div
              style={{
                background: 'color-mix(in srgb, var(--warning) 8%, transparent)',
                border: '1px solid color-mix(in srgb, var(--warning) 30%, transparent)',
                borderRadius: 6,
                padding: '10px 12px',
                marginBottom: 20,
              }}
            >
              <span style={{ fontSize: 11.5, color: 'var(--warning)', lineHeight: 1.4, display: 'block' }}>
                ⚠️ <strong>Never commit this key</strong> to public source control repositories or share it with third parties. Revoke and regenerate this key if you suspect it has been compromised.
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setApiKeyModalOpen(false)}
                style={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--border-strong)',
                  color: 'var(--text-0)',
                  borderRadius: 6,
                  padding: '6px 14px',
                  fontSize: 12.5,
                  cursor: 'pointer',
                  fontWeight: 500,
                  transition: 'background 120ms',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-1)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-2)')}
              >
                Close Dialog
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ThemePopover({ showLabels }: { showLabels: boolean }) {
  const theme = useThemeStore((s) => s.theme)
  const setTheme = useThemeStore((s) => s.setTheme)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const close = () => setOpen(false)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    const t = setTimeout(() => document.addEventListener('click', close), 0)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('click', close)
      clearTimeout(t)
    }
  }, [open])

  const opts = [
    { id: 'dark' as const, icon: Moon, label: 'Dark' },
    { id: 'light' as const, icon: Sun, label: 'Light' },
    { id: 'turquoise' as const, icon: Droplets, label: 'Turquoise' },
    { id: 'claude' as const, icon: Palette, label: 'Claude' },
  ]

  const current = opts.find((o) => o.id === theme) || opts[0]
  const Icon = current.icon

  return (
    <div
      ref={ref}
      className="rail__themes shrink-0"
      onClick={(e) => e.stopPropagation()}
      style={{
        padding: '6px 0',
        display: 'flex',
        justifyContent: showLabels ? 'flex-start' : 'center',
        paddingLeft: showLabels ? 10 : 0,
      }}
    >
      <button
        type="button"
        className={`rail__btn${open ? ' rail__btn--active' : ''}`}
        title="Theme"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation()
          setOpen((o) => !o)
        }}
        style={{
          width: showLabels ? 'calc(100% - 20px)' : 40,
          height: 32,
          borderRadius: 6,
          border: '1px solid transparent',
          background: open ? 'var(--bg-3)' : 'transparent',
          color: 'var(--text-1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: showLabels ? 'flex-start' : 'center',
          gap: 10,
          padding: showLabels ? '0 10px' : 0,
          cursor: 'pointer',
        }}
        onMouseEnter={(e) => {
          if (!open) {
            e.currentTarget.style.background = 'var(--bg-2)'
            e.currentTarget.style.borderColor = 'var(--border-soft)'
            e.currentTarget.style.color = 'var(--text-0)'
          }
        }}
        onMouseLeave={(e) => {
          if (!open) {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.borderColor = 'transparent'
            e.currentTarget.style.color = 'var(--text-1)'
          }
        }}
      >
        <ArcIcon icon={Icon} size={15} className="shrink-0" />
        {showLabels && (
          <span
            className="truncate flex-1 text-left"
            style={{
              fontFamily: 'var(--font-display-serif)',
              fontStyle: 'italic',
              fontSize: 12.5,
              fontWeight: 400,
              letterSpacing: '-0.01em',
            }}
          >
            {current.label} theme
          </span>
        )}
      </button>
      {open && (
        <div
          className="theme-pop"
          onClick={(e) => e.stopPropagation()}
          style={{
            bottom: 4,
            left: showLabels ? 190 : 54,
          }}
        >
          <div className="theme-pop__label">Theme</div>
          {opts.map((o) => {
            const ActiveIcon = o.icon
            return (
              <button
                key={o.id}
                type="button"
                className={`theme-pop__item${theme === o.id ? ' theme-pop__item--on' : ''}`}
                aria-pressed={theme === o.id}
                onClick={() => {
                  setTheme(o.id)
                  setOpen(false)
                }}
              >
                <ArcIcon icon={ActiveIcon} size={13} className="shrink-0" />
                <span>{o.label}</span>
                {theme === o.id && (
                  <ArcIcon icon={Check} size={12} className="theme-pop__check shrink-0" />
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
