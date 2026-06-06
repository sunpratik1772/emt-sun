import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  type AutomationPayload,
  type StoredWorkflow,
} from '../services/api'
import { queryKeys } from './queryKeys'

export function useLibrarySkills(open: boolean) {
  return useQuery({
    queryKey: queryKeys.librarySkills,
    queryFn: () => api.listLibrarySkills().then((d) => d.skills ?? []),
    enabled: open,
  })
}

export function useLibrarySkillDetail(skillId: string | null, open: boolean) {
  return useQuery({
    queryKey: skillId ? queryKeys.librarySkill(skillId) : ['library', 'skills', 'none'],
    queryFn: () => api.getLibrarySkill(skillId!),
    enabled: open && !!skillId,
  })
}

export function useDataSources(open: boolean) {
  return useQuery({
    queryKey: queryKeys.dataSources,
    queryFn: () => api.listDataSources().then((d) => d.data_sources ?? []),
    enabled: open,
  })
}

export function useRunLogs(open: boolean, pollMs = 5000) {
  return useQuery({
    queryKey: queryKeys.runLogs,
    queryFn: () => api.listRunLogs().then((d) => d.logs ?? []),
    enabled: open,
    refetchInterval: open && pollMs > 0 ? pollMs : false,
  })
}

export function useClearRunLogs() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.clearRunLogs(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.runLogs }),
  })
}

export function useClearWorkspace() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.clearWorkspace(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.runLogs })
      void qc.invalidateQueries({ queryKey: queryKeys.workflows })
      void qc.invalidateQueries({ queryKey: queryKeys.drafts })
      void qc.invalidateQueries({ queryKey: queryKeys.workflowCatalog })
      void qc.invalidateQueries({ queryKey: queryKeys.automations })
      void qc.invalidateQueries({ queryKey: queryKeys.copilotChats })
      void qc.invalidateQueries({ queryKey: queryKeys.copilotExamplePrompts })
    },
  })
}

export function useWorkflowCatalog(open: boolean) {
  return useQuery({
    queryKey: queryKeys.workflowCatalog,
    queryFn: () => api.workflowCatalog().then((d) => d.entries ?? []),
    enabled: open,
    staleTime: 30_000,
  })
}

export function useWorkflowsList(open: boolean) {
  return useQuery({
    queryKey: queryKeys.workflows,
    queryFn: () => api.listWorkflows().then((d) => d.workflows ?? []),
    enabled: open,
  })
}

export function useDraftsList(open: boolean) {
  return useQuery({
    queryKey: queryKeys.drafts,
    queryFn: () => api.listDrafts().then((d) => d.drafts ?? []),
    enabled: open,
  })
}

export function useDeleteWorkflowFile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (filename: string) => api.deleteWorkflow(filename),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.workflows })
      void qc.invalidateQueries({ queryKey: queryKeys.workflowCatalog })
    },
  })
}

export function useDeleteDraftFile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (filename: string) => api.deleteDraft(filename),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.drafts })
      void qc.invalidateQueries({ queryKey: queryKeys.workflowCatalog })
    },
  })
}

export function useAutomations(open: boolean) {
  return useQuery({
    queryKey: queryKeys.automations,
    queryFn: () => api.listAutomations().then((d) => d.automations ?? []),
    enabled: open,
  })
}

export function useAutomationRuns(automationId: string | null, open: boolean, pollMs = 4000) {
  return useQuery({
    queryKey: automationId ? queryKeys.automationRuns(automationId) : ['automations', 'none', 'runs'],
    queryFn: () => api.listAutomationRuns(automationId!).then((d) => d.runs ?? []),
    enabled: open && !!automationId,
    refetchInterval: open && automationId ? pollMs : false,
  })
}

export function useCreateAutomation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<AutomationPayload> & Pick<AutomationPayload, 'name' | 'workflow_filename'>) =>
      api.createAutomation(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.automations }),
  })
}

export function useUpdateAutomation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<AutomationPayload> }) =>
      api.updateAutomation(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.automations }),
  })
}

export function useDeleteAutomation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteAutomation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.automations }),
  })
}

export function useTriggerAutomation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.triggerAutomation(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.automationRuns(id) })
    },
  })
}

export function useDeleteAutomationRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ automationId, runId }: { automationId: string; runId: string }) =>
      api.deleteAutomationRun(automationId, runId),
    onSuccess: (_data, { automationId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.automationRuns(automationId) })
    },
  })
}

export function useClearAutomationRuns() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (automationId: string) => api.clearAutomationRuns(automationId),
    onSuccess: (_data, automationId) => {
      qc.invalidateQueries({ queryKey: queryKeys.automationRuns(automationId) })
    },
  })
}

export function useCopilotGuardrails(open: boolean) {
  return useQuery({
    queryKey: queryKeys.copilotGuardrails,
    queryFn: () => api.getCopilotGuardrails(),
    enabled: open,
    staleTime: 60_000,
  })
}

export function useCopilotChats(open: boolean) {
  return useQuery({
    queryKey: queryKeys.copilotChats,
    queryFn: () => api.listChats().then((d) => d.chats ?? []),
    enabled: open,
  })
}

export function useCopilotExamplePrompts(
  open: boolean,
  context?: { firstName?: string; period?: string },
  options?: {
    staleTime?: number
    gcTime?: number
    refetchOnMount?: boolean | 'always'
    refetchOnWindowFocus?: boolean | 'always'
    refreshNonce?: number
  },
) {
  const first = context?.firstName ?? ''
  const period = context?.period ?? ''
  const isDashboard = Boolean((first && first !== 'there') || period || options?.refreshNonce)
  return useQuery({
    queryKey: [
      ...queryKeys.copilotExamplePrompts,
      first,
      period,
      options?.refreshNonce ?? '',
    ],
    queryFn: () =>
      api.getExamplePrompts({
        first_name: first && first !== 'there' ? first : undefined,
        period: period || undefined,
        refresh: options?.refreshNonce,
      }),
    enabled: open,
    staleTime: options?.staleTime ?? (isDashboard ? 0 : 120_000),
    gcTime: options?.gcTime ?? (isDashboard ? 0 : 300_000),
    refetchOnMount: options?.refetchOnMount ?? true,
    refetchOnWindowFocus: options?.refetchOnWindowFocus ?? (isDashboard ? 'always' : false),
  })
}

export function useVoteWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      filename,
      vote,
      promote_to_folder,
      promote_to_table,
    }: {
      filename: string
      vote: 'up' | 'down'
      promote_to_folder?: boolean
      promote_to_table?: boolean
    }) => api.voteWorkflow(filename, vote, { promote_to_folder, promote_to_table }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.workflows })
      void qc.invalidateQueries({ queryKey: queryKeys.workflowCatalog })
    },
  })
}

export function useDataSourceAccess(open: boolean) {
  return useQuery({
    queryKey: queryKeys.dataSourceAccess,
    queryFn: () => api.listDataSourceAccess().then((d) => d.sources ?? []),
    enabled: open,
  })
}

export function useUpdateDataSourceAccess() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceId, has_access }: { sourceId: string; has_access: boolean }) =>
      api.updateDataSourceAccess(sourceId, has_access),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.dataSourceAccess })
      void qc.invalidateQueries({ queryKey: queryKeys.dataSources })
      void qc.invalidateQueries({ queryKey: queryKeys.copilotGuardrails })
    },
  })
}

export function useGoodExamplePrefs(open: boolean) {
  return useQuery({
    queryKey: queryKeys.goodExamplePrefs,
    queryFn: () => api.getGoodExamplePrefs(),
    enabled: open,
  })
}

export function useAdminUsers(open: boolean, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.adminUsers,
    queryFn: () => api.listUsers().then((d) => d.users ?? []),
    enabled: open && enabled,
  })
}

export function useAdminOverview(open: boolean, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.adminOverview,
    queryFn: () => api.getAdminOverview(),
    enabled: open && enabled,
    staleTime: 15_000,
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof api.createUser>[0]) => api.createUser(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.adminUsers })
      void qc.invalidateQueries({ queryKey: queryKeys.adminOverview })
    },
  })
}

export function useSetUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: 'admin' | 'user' }) =>
      api.setUserRole(userId, role),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.adminUsers })
      void qc.invalidateQueries({ queryKey: queryKeys.adminOverview })
    },
  })
}

export function useDeleteUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: string) => api.deleteUser(userId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.adminUsers })
      void qc.invalidateQueries({ queryKey: queryKeys.adminOverview })
    },
  })
}

export function useUpdateAdminUserDataSourceAccess(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceId, has_access }: { sourceId: string; has_access: boolean }) =>
      api.updateAdminUserDataSourceAccess(userId, sourceId, has_access),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...queryKeys.adminUserDataSourceAccess, userId] })
      void qc.invalidateQueries({ queryKey: queryKeys.adminOverview })
    },
  })
}

export function useUpdateAdminUserSkillAccess(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ skillId, has_access }: { skillId: string; has_access: boolean }) =>
      api.updateAdminUserSkillAccess(userId, skillId, has_access),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...queryKeys.adminUserSkillAccess, userId] })
      void qc.invalidateQueries({ queryKey: queryKeys.adminOverview })
    },
  })
}

export function useUpdateAdminUserFeatureAccess(userId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ featureKey, enabled }: { featureKey: string; enabled: boolean }) =>
      api.updateAdminUserFeatureAccess(userId, featureKey, enabled),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [...queryKeys.adminUserFeatureAccess, userId] })
    },
  })
}

export function useUpdateGoodExamplePrefs() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (prefs: { promote_to_folder?: boolean; promote_to_table?: boolean }) =>
      api.updateGoodExamplePrefs(prefs),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.goodExamplePrefs }),
  })
}

export type { StoredWorkflow }
