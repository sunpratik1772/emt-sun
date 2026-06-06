import { describe, expect, it } from 'vitest'
import { dayPeriod, greetingForHour } from './timeGreeting'

describe('dayPeriod', () => {
  it('maps hours to morning, afternoon, and evening', () => {
    expect(dayPeriod(8)).toBe('morning')
    expect(dayPeriod(11)).toBe('morning')
    expect(dayPeriod(12)).toBe('afternoon')
    expect(dayPeriod(16)).toBe('afternoon')
    expect(dayPeriod(17)).toBe('evening')
    expect(dayPeriod(22)).toBe('evening')
  })
})

describe('greetingForHour', () => {
  it('matches the day period buckets', () => {
    expect(greetingForHour(9)).toBe('Good morning')
    expect(greetingForHour(14)).toBe('Good afternoon')
    expect(greetingForHour(19)).toBe('Good evening')
  })
})
