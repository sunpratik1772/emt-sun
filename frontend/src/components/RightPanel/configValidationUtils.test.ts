import { describe, expect, it } from 'vitest'
import { issueForField, issueMatchesField, issuesForNode, nodeLevelIssues } from './configValidationUtils'

describe('configValidationUtils', () => {
  it('collects issues for a node', () => {
    const issues = issuesForNode(
      'n01',
      [{ code: 'X', message: 'bad', severity: 'error', node_id: 'n01' }],
      [{ code: 'W', message: 'warn', severity: 'warning', node_id: 'n01' }],
    )
    expect(issues).toHaveLength(2)
  })

  it('matches nested field paths', () => {
    expect(issueMatchesField({ code: 'X', message: 'm', severity: 'error', field: 'config.input_name' }, 'input_name')).toBe(true)
  })

  it('finds field-specific issue', () => {
    const issues = [{ code: 'X', message: 'missing input', severity: 'error' as const, field: 'input_name' }]
    expect(issueForField(issues, 'input_name')?.message).toBe('missing input')
  })

  it('returns node-level issues without field', () => {
    const issues = [
      { code: 'A', message: 'node bad', severity: 'error' as const },
      { code: 'B', message: 'field bad', severity: 'error' as const, field: 'x' },
    ]
    expect(nodeLevelIssues(issues)).toHaveLength(1)
  })
})
