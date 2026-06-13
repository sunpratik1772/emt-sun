/**
 * Theme system (dark / altermind / ripeplanet).
 *
 *  - `dark`       → Vercel + Linear feel. Near-black `#08090a` chrome, crisp white type.
 *                   This is the default.
 *  - `altermind`  → Editorial deep-forest-green chrome with warm cream accents.
 *  - `ripeplanet` → Warm cream `#dddad7` ground with terracotta `#d3817a` accent,
 *                   deep forest `#005955` secondary, tall condensed Anton display.
 *                   Subtle topographic line texture overlay.
 */
import { useLayoutEffect } from 'react'
import { create } from 'zustand'

import { brandLogoForTheme } from '../lib/brandAssets'
import { dayPeriod } from '../lib/timeGreeting'

export type Theme = 'dark' | 'altermind' | 'ripeplanet'

interface ThemeStore {
  theme: Theme
  period: string
  setTheme: (t: Theme) => void
  toggle: () => void
  refreshPeriod: () => void
}

const STORAGE_KEY = 'dbsherpa:theme'
const VALID: readonly Theme[] = ['dark', 'altermind', 'ripeplanet']

function readPreference(): Theme {
  if (typeof window === 'undefined') return 'dark'
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Theme | null
    if (stored && VALID.includes(stored)) return stored
    // Migrate legacy values (light/turquoise/claude) → dark
    if (stored && !VALID.includes(stored)) {
      window.localStorage.setItem(STORAGE_KEY, 'dark')
    }
  } catch {
    /* noop */
  }
  return 'dark'
}

const initialPreference = readPreference()

export const useThemeStore = create<ThemeStore>((set, get) => ({
  theme: initialPreference,
  period: typeof window === 'undefined' ? 'morning' : dayPeriod(),
  setTheme: (t) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, t)
    } catch {
      /* noop */
    }
    set({ theme: t })
  },
  toggle: () => {
    const current = get().theme
    const next: Theme =
      current === 'dark'
        ? 'altermind'
        : current === 'altermind'
          ? 'ripeplanet'
          : 'dark'
    get().setTheme(next)
  },
  refreshPeriod: () => {
    set({ period: dayPeriod() })
  },
}))

export function useApplyTheme(): void {
  const theme = useThemeStore((s) => s.theme)
  const period = useThemeStore((s) => s.period)
  const refreshPeriod = useThemeStore((s) => s.refreshPeriod)

  useLayoutEffect(() => {
    if (typeof window === 'undefined') return
    refreshPeriod()
    const id = window.setInterval(refreshPeriod, 60_000)
    return () => window.clearInterval(id)
  }, [refreshPeriod])

  useLayoutEffect(() => {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.setAttribute('data-period', period)
    const favicon = document.querySelector<HTMLLinkElement>('link#app-favicon')
    if (favicon) favicon.href = brandLogoForTheme(theme)
    const appleTouch = document.querySelector<HTMLLinkElement>('link#app-apple-touch-icon')
    if (appleTouch) appleTouch.href = brandLogoForTheme(theme)
  }, [theme, period])
}
