import type { ValidationIssue } from '../../types'

export function issuesForNode(
  nodeId: string,
  errors: ValidationIssue[] | null | undefined,
  warnings: ValidationIssue[] | null | undefined,
): ValidationIssue[] {
  const all = [...(errors ?? []), ...(warnings ?? [])]
  return all.filter((issue) => issue.node_id === nodeId)
}

export function issueMatchesField(issue: ValidationIssue, fieldKey: string): boolean {
  if (!issue.field) return false
  const f = issue.field
  return f === fieldKey || f.endsWith(`.${fieldKey}`) || f.endsWith(`/${fieldKey}`)
}

export function issueForField(issues: ValidationIssue[], fieldKey: string): ValidationIssue | undefined {
  return issues.find((issue) => issueMatchesField(issue, fieldKey))
}

export function nodeLevelIssues(issues: ValidationIssue[]): ValidationIssue[] {
  return issues.filter((issue) => !issue.field)
}
