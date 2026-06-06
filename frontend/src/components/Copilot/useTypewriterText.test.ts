import { describe, expect, it } from 'vitest'
import { collapsedStepCaption, firstSentence, isGenericPlanningFluff } from './useTypewriterText'

describe('firstSentence', () => {
  it('does not truncate on dots in csv filenames', () => {
    const text = '- Access to the leads.csv schema and required columns.'
    expect(firstSentence(text)).toBe(text)
  })

  it('still clips at real sentence boundaries', () => {
    expect(firstSentence('First part. Second part.')).toBe('First part.')
  })
})

describe('collapsedStepCaption', () => {
  it('prefers step title over generic planning fluff', () => {
    const caption = collapsedStepCaption({
      text: 'Checking data sources',
      outcome: 'Clearly define KPIs and initial constraints for the workflow.',
      kind: 'parallel',
    })
    expect(caption).toBe('Checking data sources')
  })
})

describe('isGenericPlanningFluff', () => {
  it('detects corporate planning copy', () => {
    expect(isGenericPlanningFluff('Ensure data integrity and strict CSV format adherence.')).toBe(true)
  })
})
