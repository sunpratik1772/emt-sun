import { describe, expect, it } from 'vitest'
import { findWorkflowNameConflicts } from './workflowNameConflict'

describe('findWorkflowNameConflicts', () => {
  const workflows = [
    { filename: 'a.json', name: 'GitHub Activity Briefing Report', node_count: 4 },
    { filename: 'b.yaml', name: 'GitHub Activity Briefing Report', node_count: 7 },
    { filename: 'other.json', name: 'Other', node_count: 1 },
  ]

  it('returns other files with the same display name', () => {
    const hits = findWorkflowNameConflicts(workflows, 'GitHub Activity Briefing Report', 'a.json')
    expect(hits.map((h) => h.filename)).toEqual(['b.yaml'])
  })

  it('is case-insensitive', () => {
    const hits = findWorkflowNameConflicts(workflows, 'github activity briefing report', null)
    expect(hits).toHaveLength(2)
  })

  it('returns empty when only the excluded file matches', () => {
    expect(findWorkflowNameConflicts(workflows, 'GitHub Activity Briefing Report', 'a.json').length).toBe(1)
    expect(findWorkflowNameConflicts(workflows, 'GitHub Activity Briefing Report', 'b.yaml').length).toBe(1)
    expect(findWorkflowNameConflicts(workflows, 'Other', 'other.json')).toEqual([])
  })
})
