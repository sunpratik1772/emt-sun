/**
 * SettingsDrawer — Cursor-style two-pane layout:
 *   left:   grouped category rail
 *   right:  selected category content with section titles, mode tiles, and
 *           toggle/dropdown rows. Modern teal toggles + yellow warning callouts.
 *
 * The full pre-existing settings logic is preserved verbatim — only the
 * surrounding shell + visual rhythm has changed.
 */
import { useEffect, useMemo, useState } from 'react'
import StudioOverlay from '../StudioOverlay'
import Modal from '../Modal'
import { Button } from '../ui/Button'
import {
  ArcIcon,
  Trash2,
  AlertTriangle,
  Settings as IconSettings,
  Shield,
  Users as IconUsers,
  Database as IconDatabase,
  Activity as IconActivity,
  type LucideIcon,
} from '../../icons/arc'
import type { AdminUserRowWithCounts } from '../../services/api'
import {
  useAdminOverview,
  useAdminUsers,
  useClearWorkspace,
  useCreateUser,
  useDataSourceAccess,
  useDataSources,
  useGoodExamplePrefs,
  useUpdateDataSourceAccess,
  useUpdateGoodExamplePrefs,
} from '../../hooks/useLibraryQueries'
import { UserAccessPanel } from './UserAccessPanel'
import { toast } from '../../store/toastStore'
import { useAuthStore, userIsAdmin } from '../../store/authStore'
import { useWorkflowStore } from '../../store/workflowStore'
import {
  getLeftNavMode,
  setLeftNavMode,
  LEFT_NAV_MODE_EVENT,
  type LeftNavMode,
} from '../../lib/leftNavMode'

const WORKSPACE_NAME_KEY = 'dbsherpa.workspace.name'

const SIDEBAR_OPTIONS: { id: LeftNavMode; label: string; desc: string }[] = [
  { id: 'expanded', label: 'Expanded', desc: 'Full width rail with labels always visible.' },
  { id: 'collapsed', label: 'Collapsed', desc: 'Compact icon-only rail.' },
  { id: 'hover', label: 'Expand on hover', desc: 'Compact rail that pushes content on hover.' },
]

type CatId = 'general' | 'permissions' | 'sources' | 'examples' | 'users' | 'admin' | 'danger'

interface CatDef {
  id: CatId
  label: string
  icon: LucideIcon
  group: 'general' | 'admin'
  adminOnly?: boolean
}

const CATEGORIES: CatDef[] = [
  { id: 'general', label: 'General', icon: IconSettings, group: 'general' },
  { id: 'permissions', label: 'Permissions', icon: Shield, group: 'general' },
  { id: 'sources', label: 'Data sources', icon: IconDatabase, group: 'general' },
  { id: 'examples', label: 'Good examples', icon: IconActivity, group: 'general' },
  { id: 'users', label: 'Users', icon: IconUsers, group: 'admin', adminOnly: true },
  { id: 'admin', label: 'Platform overview', icon: IconActivity, group: 'admin', adminOnly: true },
  { id: 'danger', label: 'Danger zone', icon: AlertTriangle, group: 'admin' },
]

function ownerLabel(users: AdminUserRowWithCounts[], userId?: string | null): string {
  if (!userId) return '—'
  const user = users.find((u) => u.user_id === userId)
  return user ? `@${user.username}` : userId
}

function formatWhen(iso?: string | null): string {
  if (!iso) return '—'
  const ms = Date.parse(iso)
  if (!Number.isFinite(ms)) return iso
  return new Date(ms).toLocaleString()
}

function Toggle({
  on,
  disabled,
  onChange,
  testid,
}: {
  on: boolean
  disabled?: boolean
  onChange: (next: boolean) => void
  testid?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      data-testid={testid}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`set2-toggle${on ? ' set2-toggle--on' : ''}`}
    >
      <span className="set2-toggle__knob" />
    </button>
  )
}

function SectionRow({
  title,
  desc,
  action,
  testid,
}: {
  title: string
  desc?: string
  action: React.ReactNode
  testid?: string
}) {
  return (
    <div className="set2-card-row" data-testid={testid}>
      <div className="set2-card-row__text">
        <div className="set2-card-row__title">{title}</div>
        {desc ? <div className="set2-card-row__desc">{desc}</div> : null}
      </div>
      <div className="set2-card-row__action">{action}</div>
    </div>
  )
}

export function SettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const currentUser = useAuthStore((s) => s.user)
  const isAdmin = userIsAdmin(currentUser)
  const clearWorkspace = useClearWorkspace()
  const { data: sourceAccess = [] } = useDataSourceAccess(open)
  const { data: allDataSources = [] } = useDataSources(open && isAdmin)
  const updateSourceAccess = useUpdateDataSourceAccess()
  const { data: goodExamplePrefs } = useGoodExamplePrefs(open)
  const updateGoodExamplePrefs = useUpdateGoodExamplePrefs()
  const { data: adminUsers = [] } = useAdminUsers(open, isAdmin)
  const { data: adminOverview, isLoading: adminOverviewLoading } = useAdminOverview(open, isAdmin)
  const createUser = useCreateUser()
  const environment = useWorkflowStore((s) => s.environment)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [sidebar, setSidebar] = useState<LeftNavMode>(() => getLeftNavMode())
  const [workspaceName, setWorkspaceName] = useState(() => {
    if (typeof window === 'undefined') return 'dbSherpa — DEV'
    return window.localStorage.getItem(WORKSPACE_NAME_KEY) ?? `dbSherpa — ${environment.toUpperCase()}`
  })
  const [newFirstName, setNewFirstName] = useState('')
  const [newLastName, setNewLastName] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newUserAccess, setNewUserAccess] = useState<Record<string, boolean>>({})
  const [grantAdminRole, setGrantAdminRole] = useState(false)
  const [newUserSkillAccess, setNewUserSkillAccess] = useState<Record<string, boolean>>({})
  const [newUserFeatureAccess, setNewUserFeatureAccess] = useState<Record<string, boolean>>({})
  const [managingUserId, setManagingUserId] = useState<string | null>(null)
  const [cat, setCat] = useState<CatId>('general')

  useEffect(() => {
    const onMode = (e: Event) => {
      const next = (e as CustomEvent<LeftNavMode>).detail
      if (next) setSidebar(next)
    }
    window.addEventListener(LEFT_NAV_MODE_EVENT, onMode)
    return () => window.removeEventListener(LEFT_NAV_MODE_EVENT, onMode)
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(WORKSPACE_NAME_KEY, workspaceName)
  }, [workspaceName])

  const handleSidebar = (id: LeftNavMode) => {
    setSidebar(id)
    setLeftNavMode(id)
  }

  const handleClear = async () => {
    try {
      await clearWorkspace.mutateAsync()
      toast.success('Workspace cleared')
      setConfirmOpen(false)
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  const handleCreateUser = async () => {
    if (!newFirstName.trim() || !newLastName.trim() || !newUsername.trim() || !newPassword.trim()) {
      toast.error('All fields are required')
      return
    }
    try {
      await createUser.mutateAsync({
        first_name: newFirstName.trim(),
        last_name: newLastName.trim(),
        username: newUsername.trim(),
        password: newPassword,
        data_source_access: newUserAccess,
        skill_access: newUserSkillAccess,
        feature_access: newUserFeatureAccess,
        role: grantAdminRole ? 'admin' : 'user',
      })
      toast.success(`Created @${newUsername.trim()}`)
      setNewFirstName('')
      setNewLastName('')
      setNewUsername('')
      setNewPassword('')
      setNewUserAccess({})
      setNewUserSkillAccess({})
      setNewUserFeatureAccess({})
      setGrantAdminRole(false)
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  const visibleCats = useMemo(
    () => CATEGORIES.filter((c) => !c.adminOnly || isAdmin),
    [isAdmin],
  )
  const activeCat = visibleCats.find((c) => c.id === cat) ?? visibleCats[0]
  const sourcesOn = sourceAccess.filter((r) => r.has_access).length
  const sourcesTotal = sourceAccess.length

  // Permissions mode (derived from the toggles to give the 3-tile selector
  // semantics from the screenshot — Full access / Selective / Strict).
  const permMode: 'full' | 'selective' | 'strict' =
    sourcesTotal === 0
      ? 'selective'
      : sourcesOn === sourcesTotal
        ? 'full'
        : sourcesOn === 0
          ? 'strict'
          : 'selective'

  const setPermMode = async (mode: 'full' | 'selective' | 'strict') => {
    if (mode === 'full') {
      for (const r of sourceAccess) {
        if (!r.has_access) {
          await updateSourceAccess
            .mutateAsync({ sourceId: r.source_id, has_access: true })
            .catch(() => undefined)
        }
      }
    } else if (mode === 'strict') {
      for (const r of sourceAccess) {
        if (r.has_access) {
          await updateSourceAccess
            .mutateAsync({ sourceId: r.source_id, has_access: false })
            .catch(() => undefined)
        }
      }
    }
  }

  return (
    <>
      <StudioOverlay
        open={open}
        onClose={onClose}
        eyebrow="Workspace"
        title={`Settings · ${activeCat?.label ?? ''}`}
        subtitle="Workspace configuration, permissions, and admin tools."
        bodyClass="ov__body--full"
        ariaLabel="Settings"
        footLeft={
          <button type="button" className="ov-bbtn" data-testid="settings-close-button" onClick={onClose}>
            Close
          </button>
        }
        footRight={<span className="ov__foot-meta">Changes are saved automatically</span>}
      >
        <div className="set2">
          {/* Left rail */}
          <aside className="set2__rail" aria-label="Settings categories">
            {(['general', 'admin'] as const).map((group) => {
              const items = visibleCats.filter((c) => c.group === group)
              if (items.length === 0) return null
              return (
                <div key={group} className="set2__rail-group">
                  <div className="set2__rail-label">
                    {group === 'general' ? 'General' : 'Workspace admin'}
                  </div>
                  {items.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      data-testid={`settings-rail-${c.id}-button`}
                      className={`set2__rail-item${cat === c.id ? ' set2__rail-item--on' : ''}`}
                      onClick={() => setCat(c.id)}
                    >
                      <ArcIcon icon={c.icon} size={14} strokeWidth={1.8} />
                      <span>{c.label}</span>
                    </button>
                  ))}
                </div>
              )
            })}
          </aside>

          {/* Right pane */}
          <main className="set2__main">
            {cat === 'general' && (
              <>
                <header className="set2__head">
                  <h2 className="set2__title">General</h2>
                  <p className="set2__sub">
                    Workspace name, deployment target, and rail behaviour. These preferences are stored locally.
                  </p>
                </header>

                <div className="set2__group-label">Workspace</div>
                <div className="set2__card">
                  <SectionRow
                    title="Workspace name"
                    desc="Shown across Studio and in exports."
                    action={
                      <input
                        className="set2-input"
                        data-testid="settings-workspace-name-input"
                        value={workspaceName}
                        onChange={(e) => setWorkspaceName(e.target.value)}
                        aria-label="Workspace name"
                      />
                    }
                  />
                  <SectionRow
                    title="Environment"
                    desc="Active deployment target."
                    action={<span className="env-badge">{environment}</span>}
                  />
                </div>

                <div className="set2__group-label">Sidebar</div>
                <div className="set2__card">
                  <SectionRow
                    title="Navigation rail behaviour"
                    desc="How the left rail expands."
                    action={
                      <div className="set2-seg" role="group" aria-label="Sidebar behaviour">
                        {SIDEBAR_OPTIONS.map(({ id, label }) => (
                          <button
                            key={id}
                            type="button"
                            data-testid={`settings-sidebar-mode-${id}-button`}
                            className={`set2-seg__btn${sidebar === id ? ' set2-seg__btn--on' : ''}`}
                            onClick={() => handleSidebar(id)}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    }
                  />
                </div>
              </>
            )}

            {cat === 'permissions' && (
              <>
                <header className="set2__head">
                  <h2 className="set2__title">Agent permission mode</h2>
                  <p className="set2__sub">
                    Select one of the three options. Per-source permissions can be further customised in
                    Data sources.
                  </p>
                </header>

                <div className="set2-tiles" role="radiogroup" aria-label="Agent permission mode">
                  {(
                    [
                      {
                        id: 'full',
                        title: 'Full access',
                        desc: 'Sherpa can read every connected data source and use every skill.',
                      },
                      {
                        id: 'selective',
                        title: 'Selective',
                        desc: 'You explicitly choose which sources Sherpa is allowed to use.',
                      },
                      {
                        id: 'strict',
                        title: 'Strict',
                        desc: 'No data sources are exposed to Sherpa until you opt-in per request.',
                      },
                    ] as const
                  ).map((tile) => (
                    <button
                      key={tile.id}
                      type="button"
                      role="radio"
                      aria-checked={permMode === tile.id}
                      data-testid={`settings-perm-mode-${tile.id}-button`}
                      className={`set2-tile${permMode === tile.id ? ' set2-tile--on' : ''}`}
                      onClick={() => void setPermMode(tile.id)}
                    >
                      <div className="set2-tile__title">{tile.title}</div>
                      <div className="set2-tile__desc">{tile.desc}</div>
                    </button>
                  ))}
                </div>

                {permMode === 'full' ? (
                  <div className="set2-warn" data-testid="settings-perm-warning">
                    <ArcIcon icon={AlertTriangle} size={14} strokeWidth={2} />
                    <span>
                      <b>Warning:</b> Full access exposes every connected source to the agent. Switch to
                      Selective for a safer default.
                    </span>
                  </div>
                ) : null}

                <div className="set2__group-label">Source detail</div>
                <p className="set2__sub" style={{ marginTop: -4 }}>
                  {sourcesOn} of {sourcesTotal} sources currently visible to the agent. Toggle individual rows
                  in <b>Data sources</b>.
                </p>
              </>
            )}

            {cat === 'sources' && (
              <>
                <header className="set2__head">
                  <h2 className="set2__title">Data source access</h2>
                  <p className="set2__sub">
                    Toggle which connectors Sherpa and your workflows can see. Disabled sources are hidden from
                    the agent and library.
                  </p>
                </header>

                <div className="set2__card">
                  {sourceAccess.length === 0 ? (
                    <div className="set2-card-row set2-card-row--empty">No data sources configured yet.</div>
                  ) : (
                    sourceAccess.map((row) => (
                      <SectionRow
                        key={row.source_id}
                        title={row.id || row.source_id}
                        desc={row.description || undefined}
                        action={
                          <Toggle
                            testid={`settings-source-toggle-${row.source_id}`}
                            on={row.has_access}
                            disabled={updateSourceAccess.isPending}
                            onChange={(next) => {
                              void updateSourceAccess
                                .mutateAsync({ sourceId: row.source_id, has_access: next })
                                .catch((err) => toast.error((err as Error).message))
                            }}
                          />
                        }
                      />
                    ))
                  )}
                </div>
              </>
            )}

            {cat === 'examples' && (
              <>
                <header className="set2__head">
                  <h2 className="set2__title">Good examples on upvote</h2>
                  <p className="set2__sub">
                    When you upvote a workflow, choose where promoted copies are stored.
                  </p>
                </header>

                <div className="set2__card">
                  <SectionRow
                    title="Promote to database table"
                    desc="Adds an entry to good_examples so it surfaces in Library search."
                    action={
                      <Toggle
                        testid="settings-upvote-promote-table-toggle"
                        on={goodExamplePrefs?.promote_to_table ?? true}
                        disabled={updateGoodExamplePrefs.isPending}
                        onChange={(next) => {
                          void updateGoodExamplePrefs
                            .mutateAsync({ promote_to_table: next })
                            .catch((err) => toast.error((err as Error).message))
                        }}
                      />
                    }
                  />
                  <SectionRow
                    title="Promote to good_examples folder"
                    desc="Writes a YAML copy to the on-disk good_examples directory."
                    action={
                      <Toggle
                        testid="settings-upvote-promote-folder-toggle"
                        on={goodExamplePrefs?.promote_to_folder ?? true}
                        disabled={updateGoodExamplePrefs.isPending}
                        onChange={(next) => {
                          void updateGoodExamplePrefs
                            .mutateAsync({ promote_to_folder: next })
                            .catch((err) => toast.error((err as Error).message))
                        }}
                      />
                    }
                  />
                </div>
              </>
            )}

            {cat === 'users' && isAdmin && (
              <>
                <header className="set2__head">
                  <h2 className="set2__title">Users</h2>
                  <p className="set2__sub">
                    Create accounts and grant selective access to data sources, skills, and Studio features.
                  </p>
                </header>

                <div className="set2__card">
                  <div className="set2-user-form">
                    <div className="set2-user-form__row">
                      <input
                        className="set2-input"
                        data-testid="settings-create-user-first-name-input"
                        placeholder="First name"
                        value={newFirstName}
                        onChange={(e) => setNewFirstName(e.target.value)}
                        aria-label="First name"
                      />
                      <input
                        className="set2-input"
                        data-testid="settings-create-user-last-name-input"
                        placeholder="Last name"
                        value={newLastName}
                        onChange={(e) => setNewLastName(e.target.value)}
                        aria-label="Last name"
                      />
                    </div>
                    <div className="set2-user-form__row">
                      <input
                        className="set2-input"
                        data-testid="settings-create-user-username-input"
                        placeholder="Username"
                        value={newUsername}
                        onChange={(e) => setNewUsername(e.target.value)}
                        aria-label="Username"
                      />
                      <input
                        className="set2-input"
                        type="password"
                        data-testid="settings-create-user-password-input"
                        placeholder="Password (8+ chars)"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        aria-label="Password"
                      />
                    </div>

                    <div className="set2__group-label">Default data source access</div>
                    <div className="set2__card set2__card--nested">
                      {allDataSources.map((src) => {
                        const sourceId = src.id || ''
                        if (!sourceId) return null
                        return (
                          <SectionRow
                            key={sourceId}
                            title={sourceId}
                            desc={src.description || undefined}
                            action={
                              <Toggle
                                testid={`settings-create-user-source-toggle-${sourceId}`}
                                on={newUserAccess[sourceId] ?? false}
                                onChange={(next) =>
                                  setNewUserAccess((prev) => ({ ...prev, [sourceId]: next }))
                                }
                              />
                            }
                          />
                        )
                      })}
                    </div>

                    {(adminOverview?.skill_catalog ?? []).length > 0 ? (
                      <>
                        <div className="set2__group-label">Skills</div>
                        <div className="set2__card set2__card--nested">
                          {adminOverview!.skill_catalog!.map((skillId) => (
                            <SectionRow
                              key={skillId}
                              title={skillId}
                              action={
                                <Toggle
                                  testid={`settings-create-user-skill-toggle-${skillId}`}
                                  on={newUserSkillAccess[skillId] ?? false}
                                  onChange={(next) =>
                                    setNewUserSkillAccess((prev) => ({ ...prev, [skillId]: next }))
                                  }
                                />
                              }
                            />
                          ))}
                        </div>
                      </>
                    ) : null}

                    {(adminOverview?.feature_catalog ?? []).length > 0 ? (
                      <>
                        <div className="set2__group-label">Studio features</div>
                        <div className="set2__card set2__card--nested">
                          {adminOverview!.feature_catalog!.map((f) => (
                            <SectionRow
                              key={f.feature_key}
                              title={f.label}
                              action={
                                <Toggle
                                  testid={`settings-create-user-feature-toggle-${f.feature_key}`}
                                  on={newUserFeatureAccess[f.feature_key] ?? true}
                                  onChange={(next) =>
                                    setNewUserFeatureAccess((prev) => ({
                                      ...prev,
                                      [f.feature_key]: next,
                                    }))
                                  }
                                />
                              }
                            />
                          ))}
                        </div>
                      </>
                    ) : null}

                    <SectionRow
                      title="Grant admin role"
                      desc="Admin users see Platform overview and can manage everyone else."
                      action={
                        <Toggle
                          testid="settings-create-user-admin-role-toggle"
                          on={grantAdminRole}
                          onChange={setGrantAdminRole}
                        />
                      }
                    />

                    <div className="set2-user-form__cta">
                      <button
                        type="button"
                        className="ov-bbtn ov-bbtn--primary"
                        data-testid="settings-create-user-submit-button"
                        disabled={createUser.isPending}
                        onClick={() => void handleCreateUser()}
                      >
                        {createUser.isPending ? 'Creating…' : 'Create user'}
                      </button>
                    </div>
                  </div>
                </div>

                {adminUsers.length > 0 ? (
                  <>
                    <div className="set2__group-label">Existing users</div>
                    <div className="set2-user-list">
                      {adminUsers.map((u) => (
                        <div key={u.user_id} className="set2-user-list__row">
                          <div className="set2-user-list__head">
                            <span className="set2-user-list__name">{u.name}</span>
                            {(u.role || 'user') === 'admin' ? (
                              <span className="set-admin-pill set-admin-pill--success">Admin</span>
                            ) : null}
                          </div>
                          <span className="set2-user-list__meta">
                            @{u.username} · {u.email}
                          </span>
                          <button
                            type="button"
                            className="ov-bbtn set2-user-list__manage"
                            data-testid={`settings-manage-user-access-${u.user_id}-button`}
                            onClick={() =>
                              setManagingUserId((prev) => (prev === u.user_id ? null : u.user_id))
                            }
                          >
                            {managingUserId === u.user_id ? 'Hide access' : 'Manage access'}
                          </button>
                          {managingUserId === u.user_id ? (
                            <UserAccessPanel
                              user={u}
                              onDeleted={() => setManagingUserId(null)}
                            />
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </>
                ) : null}
              </>
            )}

            {cat === 'admin' && isAdmin && (
              <>
                <header className="set2__head">
                  <h2 className="set2__title">Platform overview</h2>
                  <p className="set2__sub">
                    Admin view of all users and workspace data across the platform.
                  </p>
                </header>

                {adminOverviewLoading && !adminOverview ? (
                  <p className="set2__sub">Loading platform data…</p>
                ) : adminOverview ? (
                  <>
                    <div className="set2-stats">
                      {(
                        [
                          ['Users', adminOverview.totals.users],
                          ['Workflows', adminOverview.totals.workflows],
                          ['Drafts', adminOverview.totals.drafts],
                          ['Runs', adminOverview.totals.runs],
                          ['Automations', adminOverview.totals.automations],
                          ['Chats', adminOverview.totals.chats],
                        ] as const
                      ).map(([label, value]) => (
                        <div key={label} className="set2-stat">
                          <span className="set2-stat__value">{value}</span>
                          <span className="set2-stat__label">{label}</span>
                        </div>
                      ))}
                    </div>

                    <div className="set2__group-label">All users</div>
                    <div className="set-admin-table-wrap">
                      <table className="set-admin-table">
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Username</th>
                            <th>Role</th>
                            <th>Workflows</th>
                            <th>Drafts</th>
                            <th>Runs</th>
                            <th>Automations</th>
                            <th>Chats</th>
                          </tr>
                        </thead>
                        <tbody>
                          {adminOverview.users.map((u) => (
                            <tr key={u.user_id}>
                              <td>{u.name}</td>
                              <td>@{u.username}</td>
                              <td>{(u.role || 'user') === 'admin' ? 'Admin' : 'User'}</td>
                              <td>{u.counts.workflows}</td>
                              <td>{u.counts.drafts}</td>
                              <td>{u.counts.runs}</td>
                              <td>{u.counts.automations}</td>
                              <td>{u.counts.chats}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="set2__group-label">All workflows ({adminOverview.workflows.length})</div>
                    <div className="set-admin-table-wrap">
                      <table className="set-admin-table">
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>File</th>
                            <th>Owner</th>
                            <th>Updated</th>
                            <th>Votes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {adminOverview.workflows.length === 0 ? (
                            <tr>
                              <td colSpan={5} className="set-admin-table__empty">
                                No saved workflows
                              </td>
                            </tr>
                          ) : (
                            adminOverview.workflows.map((w) => (
                              <tr key={`${w.user_id}:${w.filename}`}>
                                <td>{w.name || w.filename}</td>
                                <td className="set-admin-table__mono">{w.filename}</td>
                                <td>{ownerLabel(adminOverview.users, w.user_id)}</td>
                                <td>{formatWhen(w.updated_at)}</td>
                                <td>
                                  ↑{w.upvote_count ?? 0} ↓{w.downvote_count ?? 0}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>

                    <div className="set2__group-label">All drafts ({adminOverview.drafts.length})</div>
                    <div className="set-admin-table-wrap">
                      <table className="set-admin-table">
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>File</th>
                            <th>Owner</th>
                            <th>Updated</th>
                          </tr>
                        </thead>
                        <tbody>
                          {adminOverview.drafts.length === 0 ? (
                            <tr>
                              <td colSpan={4} className="set-admin-table__empty">
                                No drafts
                              </td>
                            </tr>
                          ) : (
                            adminOverview.drafts.slice(0, 40).map((d) => (
                              <tr key={`${d.user_id}:${d.filename}`}>
                                <td>{d.name || d.filename}</td>
                                <td className="set-admin-table__mono">{d.filename}</td>
                                <td>{ownerLabel(adminOverview.users, d.user_id)}</td>
                                <td>{formatWhen(d.updated_at)}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>

                    <div className="set2__group-label">Recent runs ({adminOverview.runs.length})</div>
                    <div className="set-admin-table-wrap">
                      <table className="set-admin-table">
                        <thead>
                          <tr>
                            <th>Workflow</th>
                            <th>Status</th>
                            <th>Owner</th>
                            <th>Started</th>
                            <th>Error</th>
                          </tr>
                        </thead>
                        <tbody>
                          {adminOverview.runs.length === 0 ? (
                            <tr>
                              <td colSpan={5} className="set-admin-table__empty">
                                No runs
                              </td>
                            </tr>
                          ) : (
                            adminOverview.runs.map((r) => (
                              <tr key={r.run_id}>
                                <td>{r.workflow || '—'}</td>
                                <td>
                                  <span className={`set-admin-pill set-admin-pill--${r.status || 'unknown'}`}>
                                    {r.status || '—'}
                                  </span>
                                </td>
                                <td>{ownerLabel(adminOverview.users, r.user_id)}</td>
                                <td>{formatWhen(r.started_at)}</td>
                                <td className="set-admin-table__error">{r.error || '—'}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>

                    <div className="set2__group-label">
                      All automations ({adminOverview.automations.length})
                    </div>
                    <div className="set-admin-table-wrap">
                      <table className="set-admin-table">
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Workflow</th>
                            <th>Owner</th>
                            <th>Schedule</th>
                            <th>Active</th>
                          </tr>
                        </thead>
                        <tbody>
                          {adminOverview.automations.length === 0 ? (
                            <tr>
                              <td colSpan={5} className="set-admin-table__empty">
                                No automations
                              </td>
                            </tr>
                          ) : (
                            adminOverview.automations.map((a) => (
                              <tr key={a.id}>
                                <td>{a.name || a.id}</td>
                                <td className="set-admin-table__mono">{a.workflow_filename || '—'}</td>
                                <td>{ownerLabel(adminOverview.users, a.user_id)}</td>
                                <td>{a.schedule_type || '—'}</td>
                                <td>{a.active ? 'Yes' : 'No'}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : null}
              </>
            )}

            {cat === 'danger' && (
              <>
                <header className="set2__head">
                  <h2 className="set2__title">Danger zone</h2>
                  <p className="set2__sub">
                    Irreversible workspace actions. Run with care — destructive operations cannot be undone.
                  </p>
                </header>

                <div className="set2-warn set2-warn--danger">
                  <ArcIcon icon={AlertTriangle} size={14} strokeWidth={2} />
                  <span>
                    <b>Clearing the workspace</b> removes every Sherpa chat, saved workflow, draft, run log,
                    automation, and audit log from the database. Studio demo workflows in{' '}
                    <code>good_examples/</code> are preserved. User accounts are not affected.
                  </span>
                </div>

                <div className="set2-user-form__cta" style={{ marginTop: 18 }}>
                  <button
                    type="button"
                    className="ov-bbtn ov-bbtn--danger"
                    data-testid="settings-clear-everything-button"
                    onClick={() => setConfirmOpen(true)}
                  >
                    <ArcIcon icon={Trash2} size={14} strokeWidth={2} />
                    Clear everything
                  </button>
                </div>
              </>
            )}
          </main>
        </div>
      </StudioOverlay>

      {confirmOpen && (
        <Modal ariaLabel="Confirm clear workspace" onClose={() => setConfirmOpen(false)} zIndex={200}>
          <div style={{ padding: '22px 24px', maxWidth: 420 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-0)', marginBottom: 8 }}>
              Clear all workspace data?
            </div>
            <p style={{ fontSize: 12.5, lineHeight: 1.55, color: 'var(--text-2)', marginBottom: 18 }}>
              This permanently removes chats, workflows, drafts, runs, automations, and logs. Studio good
              examples stay on disk. This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                size="sm"
                data-testid="settings-confirm-cancel-button"
                className="font-mono"
                onClick={() => setConfirmOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                className="font-mono"
                data-testid="settings-confirm-clear-workspace-button"
                disabled={clearWorkspace.isPending}
                onClick={() => void handleClear()}
              >
                {clearWorkspace.isPending ? 'Clearing…' : 'Clear everything'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
