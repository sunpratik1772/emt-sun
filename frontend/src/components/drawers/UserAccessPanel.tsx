import { useQuery } from '@tanstack/react-query'
import { api } from '../../services/api'
import { queryKeys } from '../../hooks/queryKeys'
import { toast } from '../../store/toastStore'
import {
  useDeleteUser,
  useSetUserRole,
  useUpdateAdminUserDataSourceAccess,
  useUpdateAdminUserFeatureAccess,
  useUpdateAdminUserSkillAccess,
} from '../../hooks/useLibraryQueries'
import type { AdminUserRow } from '../../services/api'
import { useAuthStore } from '../../store/authStore'
import { ArcIcon, Trash2 } from '../../icons/arc'

export function UserAccessPanel({
  user,
  onDeleted,
}: {
  user: AdminUserRow
  onDeleted?: () => void
}) {
  const currentUser = useAuthStore((s) => s.user)
  const deleteUser = useDeleteUser()
  const setUserRole = useSetUserRole()
  const updateSource = useUpdateAdminUserDataSourceAccess(user.user_id)
  const updateSkill = useUpdateAdminUserSkillAccess(user.user_id)
  const updateFeature = useUpdateAdminUserFeatureAccess(user.user_id)

  const { data: sources = [] } = useQuery({
    queryKey: [...queryKeys.adminUserDataSourceAccess, user.user_id],
    queryFn: () => api.getAdminUserDataSourceAccess(user.user_id).then((d) => d.sources ?? []),
  })
  const { data: skills = [] } = useQuery({
    queryKey: [...queryKeys.adminUserSkillAccess, user.user_id],
    queryFn: () => api.getAdminUserSkillAccess(user.user_id).then((d) => d.skills ?? []),
  })
  const { data: features = [] } = useQuery({
    queryKey: [...queryKeys.adminUserFeatureAccess, user.user_id],
    queryFn: () => api.getAdminUserFeatureAccess(user.user_id).then((d) => d.features ?? []),
  })

  const handleDelete = async () => {
    if (!window.confirm(`Delete ${user.name} (@${user.username}) and all their data?`)) return
    try {
      await deleteUser.mutateAsync(user.user_id)
      toast.success(`Deleted ${user.username}`)
      onDeleted?.()
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  return (
    <div className="set-user-access">
      <div className="set-user-access__head">
        <span className="set-user-access__title">Access for @{user.username}</span>
        {user.user_id !== currentUser?.user_id ? (
          <button
            type="button"
            className="ov-bbtn ov-bbtn--danger set-user-access__delete"
            disabled={deleteUser.isPending}
            onClick={() => void handleDelete()}
          >
            <ArcIcon icon={Trash2} size={13} strokeWidth={2} />
            Delete user
          </button>
        ) : null}
      </div>

      <p className="set-sec__hint">
        Workflows and run history are per-user (users only see their own). Toggle connectors, skills,
        and Studio features below. Node palette maps to the canvas node library.
      </p>

      <label className="set-access-row set-access-row--compact">
        <span className="set-access-row__name">Admin role</span>
        <input
          type="checkbox"
          checked={(user.role || 'user') === 'admin'}
          disabled={setUserRole.isPending}
          onChange={(e) => {
            void setUserRole
              .mutateAsync({
                userId: user.user_id,
                role: e.target.checked ? 'admin' : 'user',
              })
              .then(async () => {
                if (user.user_id === currentUser?.user_id) {
                  await useAuthStore.getState().refresh()
                }
              })
              .catch((err) => toast.error((err as Error).message))
          }}
        />
      </label>

      <div className="set-user-access__block">
        <div className="set-admin-block__title">Data sources</div>
        <div className="set-access-list">
          {sources.map((row) => (
            <label key={row.source_id} className="set-access-row">
              <span className="set-access-row__name">{row.id || row.source_id}</span>
              <input
                type="checkbox"
                checked={row.has_access}
                disabled={updateSource.isPending}
                onChange={(e) => {
                  void updateSource
                    .mutateAsync({ sourceId: row.source_id, has_access: e.target.checked })
                    .catch((err) => toast.error((err as Error).message))
                }}
              />
            </label>
          ))}
        </div>
      </div>

      <div className="set-user-access__block">
        <div className="set-admin-block__title">Skills</div>
        <div className="set-access-list">
          {skills.map((row) => (
            <label key={row.skill_id} className="set-access-row">
              <span className="set-access-row__name">{row.skill_id}</span>
              <input
                type="checkbox"
                checked={row.has_access}
                disabled={updateSkill.isPending}
                onChange={(e) => {
                  void updateSkill
                    .mutateAsync({ skillId: row.skill_id, has_access: e.target.checked })
                    .catch((err) => toast.error((err as Error).message))
                }}
              />
            </label>
          ))}
        </div>
      </div>

      <div className="set-user-access__block">
        <div className="set-admin-block__title">Studio features</div>
        <div className="set-access-list">
          {features.map((row) => (
            <label key={row.feature_key} className="set-access-row">
              <span className="set-access-row__meta">
                <span className="set-access-row__name">{row.label}</span>
                <span className="set-access-row__desc">{row.feature_key}</span>
              </span>
              <input
                type="checkbox"
                checked={row.enabled}
                disabled={updateFeature.isPending}
                onChange={(e) => {
                  void updateFeature
                    .mutateAsync({ featureKey: row.feature_key, enabled: e.target.checked })
                    .catch((err) => toast.error((err as Error).message))
                }}
              />
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}
