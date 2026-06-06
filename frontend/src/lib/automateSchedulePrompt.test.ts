import { describe, expect, it } from 'vitest'
import {
  mergeAutomateWithSchedule,
  needsAutomateSchedulePrompt,
} from './automateSchedulePrompt'

describe('needsAutomateSchedulePrompt', () => {
  it('prompts when automate slash has no schedule body', () => {
    expect(needsAutomateSchedulePrompt('/automate')).toBe(true)
    expect(needsAutomateSchedulePrompt('/automation')).toBe(true)
  })

  it('skips when schedule cues are present', () => {
    expect(needsAutomateSchedulePrompt('/automate weekdays at 9am')).toBe(false)
    expect(needsAutomateSchedulePrompt('automate every 30 minutes')).toBe(false)
  })

  it('merges schedule detail into slash command', () => {
    expect(mergeAutomateWithSchedule('/automate', 'daily at 6pm')).toBe('/automate daily at 6pm')
  })
})
