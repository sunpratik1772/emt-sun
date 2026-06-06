export type DayPeriod = 'morning' | 'afternoon' | 'evening'

export function dayPeriod(hour = new Date().getHours()): DayPeriod {
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}

export function greetingForHour(hour = new Date().getHours()): string {
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}
