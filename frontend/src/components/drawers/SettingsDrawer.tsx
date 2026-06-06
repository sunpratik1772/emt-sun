import { useEffect, useState } from 'react'
import StudioOverlay from '../StudioOverlay'
import Modal from '../Modal'
import { Button } from '../ui/Button'
import { ArcIcon, Trash2, AlertTriangle } from '../../icons/arc'
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

const SIDEBAR_OPTIONS: { id: LeftNavMode; label: string }[] = [
  { id: 'expanded', label: 'Expanded' },
  { id: 'collapsed', label: 'Collapsed' },
  { id: 'hover', label: 'Expand on hover' },
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
      useWorkflowStore.getState().clearWorkflow()
      useWorkflowStore.getState().clearCopilotMessages()
      setConfirmOpen(false)
      toast.success('Workspace cleared — chats, workflows, drafts, runs, and automations removed')
    } catch (err) {
      toast.error(`Failed to clear workspace: ${(err as Error).message}`)
    }
  }

  const handleCreateUser = async () => {
    const first_name = newFirstName.trim()
    const last_name = newLastName.trim()
    const username = newUsername.trim().toLowerCase()
    const password = newPassword
    if (!first_name || !last_name || !username || password.length < 8) {
      toast.error('First name, last name, username, and password (8+ chars) are required')
      return
    }
    try {
      await createUser.mutateAsync({
        first_name,
        last_name,
        username,
        password,
        data_source_access: newUserAccess,
        skill_access: newUserSkillAccess,
        feature_access: newUserFeatureAccess,
        role: grantAdminRole ? 'admin' : 'user',
      })
      setNewFirstName('')
      setNewLastName('')
      setNewUsername('')
      setNewPassword('')
      setNewUserAccess({})
      setNewUserSkillAccess({})
      setNewUserFeatureAccess({})
      setGrantAdminRole(false)
      toast.success(`User ${username} created`)
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  return (
    <>
      <StudioOverlay
        open={open}
        onClose={onClose}
        eyebrow="Workspace"
        title="Settings"
        subtitle="Workspace maintenance and data controls."
        bodyClass="ov__body--wide"
        footLeft={
          <button type="button" className="ov-bbtn" onClick={onClose}>
            Close
          </button>
        }
        footRight={<span className="ov__foot-meta">Changes are saved automatically</span>}
      >
        <div className="set-sec">
          <div className="set-sec__label">General</div>
          <div className="set-row">
            <div>
              <div className="set-row__k">Workspace name</div>
              <div className="set-row__d">Shown across Studio and in exports</div>
            </div>
            <input
              className="set-input"
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              aria-label="Workspace name"
            />
          </div>
          <div className="set-row">
            <div>
              <div className="set-row__k">Environment</div>
              <div className="set-row__d">Active deployment target</div>
            </div>
            <span className="env-badge">{environment}</span>
          </div>
        </div>

        <div className="set-sec">
          <div className="set-sec__label">Sidebar behavior</div>
          <div className="set-row">
            <div>
              <div className="set-row__k">Navigation rail</div>
              <div className="set-row__d">How the left rail expands</div>
            </div>
            <div className="set-seg" role="group" aria-label="Sidebar behavior">
              {SIDEBAR_OPTIONS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  className={`set-seg__btn${sidebar === id ? ' set-seg__btn--on' : ''}`}
                  onClick={() => handleSidebar(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="set-sec">
          <div className="set-sec__label">Data source access</div>
          <p className="set-sec__hint">
            Toggle which connectors Sherpa and your workflows can see. Disabled sources are hidden from the agent
            and library.
          </p>
          <div className="set-access-list">
            {sourceAccess.map((row) => (
              <label key={row.source_id} className="set-access-row">
                <span className="set-access-row__meta">
                  <span className="set-access-row__name">{row.id || row.source_id}</span>
                  {row.description ? (
                    <span className="set-access-row__desc">{row.description}</span>
                  ) : null}
                </span>
                <input
                  type="checkbox"
                  checked={row.has_access}
                  disabled={updateSourceAccess.isPending}
                  onChange={(e) => {
                    void updateSourceAccess
                      .mutateAsync({ sourceId: row.source_id, has_access: e.target.checked })
                      .catch((err) => toast.error((err as Error).message))
                  }}
                />
              </label>
            ))}
          </div>
        </div>

        <div className="set-sec">
          <div className="set-sec__label">Good examples on upvote</div>
          <p className="set-sec__hint">
            When you upvote a workflow, choose where promoted copies are stored.
          </p>
          <label className="set-access-row">
            <span className="set-access-row__name">Promote to database table</span>
            <input
              type="checkbox"
              checked={goodExamplePrefs?.promote_to_table ?? true}
              disabled={updateGoodExamplePrefs.isPending}
              onChange={(e) => {
                void updateGoodExamplePrefs
                  .mutateAsync({ promote_to_table: e.target.checked })
                  .catch((err) => toast.error((err as Error).message))
              }}
            />
          </label>
          <label className="set-access-row">
            <span className="set-access-row__name">Promote to good_examples folder</span>
            <input
              type="checkbox"
              checked={goodExamplePrefs?.promote_to_folder ?? true}
              disabled={updateGoodExamplePrefs.isPending}
              onChange={(e) => {
                void updateGoodExamplePrefs
                  .mutateAsync({ promote_to_folder: e.target.checked })
                  .catch((err) => toast.error((err as Error).message))
              }}
            />
          </label>
        </div>

        {isAdmin ? (
          <div className="set-sec">
            <div className="set-sec__label">Users</div>
            <p className="set-sec__hint">
              Create accounts and grant selective access to data sources, skills, and Studio features.
            </p>
            <div className="set-user-form">
              <div className="set-user-form__row">
                <input
                  className="set-input"
                  placeholder="First name"
                  value={newFirstName}
                  onChange={(e) => setNewFirstName(e.target.value)}
                  aria-label="First name"
                />
                <input
                  className="set-input"
                  placeholder="Last name"
                  value={newLastName}
                  onChange={(e) => setNewLastName(e.target.value)}
                  aria-label="Last name"
                />
              </div>
              <div className="set-user-form__row">
                <input
                  className="set-input"
                  placeholder="Username"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  aria-label="Username"
                />
                <input
                  className="set-input"
                  type="password"
                  placeholder="Password (8+ chars)"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  aria-label="Password"
                />
              </div>
              <div className="set-access-list">
                {allDataSources.map((src) => {
                  const sourceId = src.id || ''
                  if (!sourceId) return null
                  return (
                    <label key={sourceId} className="set-access-row">
                      <span className="set-access-row__meta">
                        <span className="set-access-row__name">{sourceId}</span>
                        {src.description ? (
                          <span className="set-access-row__desc">{src.description}</span>
                        ) : null}
                      </span>
                      <input
                        type="checkbox"
                        checked={newUserAccess[sourceId] ?? false}
                        onChange={(e) =>
                          setNewUserAccess((prev) => ({ ...prev, [sourceId]: e.target.checked }))
                        }
                      />
                    </label>
                  )
                })}
              </div>
              {(adminOverview?.skill_catalog ?? []).length > 0 ? (
                <div className="set-access-list">
                  <div className="set-admin-block__title">Skills (on create)</div>
                  {adminOverview!.skill_catalog!.map((skillId) => (
                    <label key={skillId} className="set-access-row">
                      <span className="set-access-row__name">{skillId}</span>
                      <input
                        type="checkbox"
                        checked={newUserSkillAccess[skillId] ?? false}
                        onChange={(e) =>
                          setNewUserSkillAccess((prev) => ({ ...prev, [skillId]: e.target.checked }))
                        }
                      />
                    </label>
                  ))}
                </div>
              ) : null}
              {(adminOverview?.feature_catalog ?? []).length > 0 ? (
                <div className="set-access-list">
                  <div className="set-admin-block__title">Features (on create)</div>
                  {adminOverview!.feature_catalog!.map((f) => (
                    <label key={f.feature_key} className="set-access-row">
                      <span className="set-access-row__name">{f.label}</span>
                      <input
                        type="checkbox"
                        checked={newUserFeatureAccess[f.feature_key] ?? true}
                        onChange={(e) =>
                          setNewUserFeatureAccess((prev) => ({
                            ...prev,
                            [f.feature_key]: e.target.checked,
                          }))
                        }
                      />
                    </label>
                  ))}
                </div>
              ) : null}
              <label className="set-access-row">
                <span className="set-access-row__name">Grant admin role</span>
                <input
                  type="checkbox"
                  checked={grantAdminRole}
                  onChange={(e) => setGrantAdminRole(e.target.checked)}
                />
              </label>
              <button
                type="button"
                className="ov-bbtn ov-bbtn--primary"
                disabled={createUser.isPending}
                onClick={() => void handleCreateUser()}
              >
                {createUser.isPending ? 'Creating…' : 'Create user'}
              </button>
            </div>
            {adminUsers.length > 0 ? (
              <div className="set-user-list">
                {adminUsers.map((u) => (
                  <div key={u.user_id} className="set-user-list__row">
                    <div className="set-user-list__head">
                      <span className="set-user-list__name">{u.name}</span>
                      {(u.role || 'user') === 'admin' ? (
                        <span className="set-admin-pill set-admin-pill--success">Admin</span>
                      ) : null}
                    </div>
                    <span className="set-user-list__meta">
                      @{u.username} · {u.email}
                    </span>
                    <button
                      type="button"
                      className="ov-bbtn set-user-list__manage"
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
            ) : null}
          </div>
        ) : null}

        {isAdmin ? (
          <div className="set-sec">
            <div className="set-sec__label">Platform overview</div>
            <p className="set-sec__hint">
              Admin view of all users and workspace data across the platform.
            </p>
            {adminOverviewLoading && !adminOverview ? (
              <p className="set-sec__hint">Loading platform data…</p>
            ) : adminOverview ? (
              <>
                <div className="set-admin-stats">
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
                    <div key={label} className="set-admin-stat">
                      <span className="set-admin-stat__value">{value}</span>
                      <span className="set-admin-stat__label">{label}</span>
                    </div>
                  ))}
                </div>

                <div className="set-admin-block">
                  <div className="set-admin-block__title">All users</div>
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
                </div>

                <div className="set-admin-block">
                  <div className="set-admin-block__title">
                    All workflows ({adminOverview.workflows.length})
                  </div>
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
                </div>

                <div className="set-admin-block">
                  <div className="set-admin-block__title">All drafts ({adminOverview.drafts.length})</div>
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
                  {adminOverview.drafts.length > 40 ? (
                    <p className="set-sec__hint">Showing 40 of {adminOverview.drafts.length} drafts</p>
                  ) : null}
                </div>

                <div className="set-admin-block">
                  <div className="set-admin-block__title">
                    Recent runs ({adminOverview.runs.length})
                  </div>
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
                </div>

                <div className="set-admin-block">
                  <div className="set-admin-block__title">
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
                </div>
              </>
            ) : null}
          </div>
        ) : null}

        <div className="set-sec">
          <div className="set-sec__label">Danger zone</div>
          <div className="set-card set-card--danger">
            <span className="set-card__ico">
              <ArcIcon icon={AlertTriangle} size={18} strokeWidth={2} />
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="set-card__title">Clear all workspace data</div>
              <div className="set-card__desc">
                Deletes every Sherpa chat, saved workflow, draft, run log, automation, and audit log from the
                database. Studio demo workflows in <code>good_examples/</code> are preserved. User accounts are
                not affected.
              </div>
              <button type="button" className="ov-bbtn ov-bbtn--danger" onClick={() => setConfirmOpen(true)}>
                <ArcIcon icon={Trash2} size={14} strokeWidth={2} />
                Clear everything
              </button>
            </div>
          </div>
        </div>
      </StudioOverlay>

      {confirmOpen && (
        <Modal ariaLabel="Confirm clear workspace" onClose={() => setConfirmOpen(false)} zIndex={200}>
          <div style={{ padding: '22px 24px', maxWidth: 420 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-0)', marginBottom: 8 }}>
              Clear all workspace data?
            </div>
            <p style={{ fontSize: 12.5, lineHeight: 1.55, color: 'var(--text-2)', marginBottom: 18 }}>
              This permanently removes chats, workflows, drafts, runs, automations, and logs. Studio good examples
              stay on disk. This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" className="font-mono" onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                className="font-mono"
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
