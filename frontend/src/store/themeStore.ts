/**
 * Theme (dark/light/turquoise/claude) — Zustand store + hook to mirror onto `<html>`.
 *
 * - Default theme is dark.
 * - Changes theme automatically every 2 hours.
 */
import { useLayoutEffect } from 'react'
import { create } from 'zustand'

import { brandLogoForTheme } from '../lib/brandAssets'
import { dayPeriod } from '../lib/timeGreeting'

export type Theme = 'dark' | 'light' | 'turquoise' | 'claude'

interface ThemeStore {
  /** Resolved chrome theme applied to the document. */
  theme: Theme
  /** Local clock bucket for subtle accent shifts (not base dark/light). */
  period: string
  setTheme: (t: Theme) => void
  toggle: () => void
  refreshPeriod: () => void
}

const STORAGE_KEY = 'dbsherpa:theme'

function readPreference(): Theme {
  if (typeof window === 'undefined') return 'dark'
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'aurora') return 'turquoise'
    if (saved === 'dark' || saved === 'light' || saved === 'turquoise' || saved === 'claude') {
      return saved as Theme
    }
  } catch {
    // ignore; fall back to dark
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
        ? 'light'
        : current === 'light'
          ? 'turquoise'
          : current === 'turquoise'
            ? 'claude'
            : 'dark'
    get().setTheme(next)
  },
  refreshPeriod: () => {
    set({ period: dayPeriod() })
  },
}))

/** Call once near the root; keeps `<html data-theme>` and `data-period` in sync. */
export function useApplyTheme(): void {
  const theme = useThemeStore((s) => s.theme)
  const period = useThemeStore((s) => s.period)
  const refreshPeriod = useThemeStore((s) => s.refreshPeriod)
  const toggle = useThemeStore((s) => s.toggle)

  useLayoutEffect(() => {
    if (typeof window === 'undefined') return
    refreshPeriod()
    const id = window.setInterval(refreshPeriod, 60_000)
    return () => window.clearInterval(id)
  }, [refreshPeriod])

  // Automatically cycle through themes every 2 hours
  useLayoutEffect(() => {
    if (typeof window === 'undefined') return
    const id = window.setInterval(() => {
      toggle()
    }, 2 * 60 * 60 * 1000) // 2 hours
    return () => window.clearInterval(id)
  }, [toggle])

  useLayoutEffect(() => {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.setAttribute('data-period', period)
    const favicon = document.querySelector<HTMLLinkElement>('link#app-favicon')
    if (favicon) {
      favicon.href = brandLogoForTheme(theme)
    }
    const appleTouch = document.querySelector<HTMLLinkElement>('link#app-apple-touch-icon')
    if (appleTouch) {
      appleTouch.href = brandLogoForTheme(theme)
    }
  }, [theme, period])
}
