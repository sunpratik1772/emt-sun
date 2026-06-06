/**
 * Theme (dark/light) — Zustand store + hook to mirror onto `<html>`.
 *
 * - Default preference is **system** (follows OS `prefers-color-scheme`).
 * - Manual toggle persists an explicit dark/light choice in localStorage.
 * - `data-period` (morning / afternoon / evening) follows the local clock;
 *   morning keeps neutral black/white chrome; later periods shift accent tints.
 */
import { useLayoutEffect } from 'react'
import { create } from 'zustand'

import { brandLogoForTheme } from '../lib/brandAssets'
import { dayPeriod, type DayPeriod } from '../lib/timeGreeting'

export type Theme = 'dark' | 'light' | 'turquoise' | 'claude'
export type ThemePreference = 'system' | Theme

interface ThemeStore {
  /** Resolved chrome theme applied to the document. */
  theme: Theme
  /** User preference — system follows OS until toggled. */
  preference: ThemePreference
  /** Local clock bucket for subtle accent shifts (not base dark/light). */
  period: DayPeriod
  setTheme: (t: Theme) => void
  followSystem: () => void
  toggle: () => void
  refreshPeriod: () => void
  syncSystemTheme: () => void
}

const STORAGE_KEY = 'dbsherpa:theme'

function systemTheme(): Theme {
  if (typeof window === 'undefined') return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function resolveTheme(preference: ThemePreference): Theme {
  return preference === 'system' ? systemTheme() : preference
}

function readPreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (saved === 'aurora') return 'turquoise'
    if (saved === 'system' || saved === 'dark' || saved === 'light' || saved === 'turquoise' || saved === 'claude') {
      return saved
    }
  } catch {
    // ignore; fall back to system
  }
  return 'system'
}

const initialPreference = readPreference()

export const useThemeStore = create<ThemeStore>((set, get) => ({
  preference: initialPreference,
  theme: resolveTheme(initialPreference),
  period: typeof window === 'undefined' ? 'morning' : dayPeriod(),
  setTheme: (t) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, t)
    } catch {
      /* noop */
    }
    set({ preference: t, theme: t })
  },
  followSystem: () => {
    try {
      window.localStorage.setItem(STORAGE_KEY, 'system')
    } catch {
      /* noop */
    }
    set({ preference: 'system', theme: systemTheme() })
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
  syncSystemTheme: () => {
    if (get().preference !== 'system') return
    set({ theme: systemTheme() })
  },
}))

/** Call once near the root; keeps `<html data-theme>` and `data-period` in sync. */
export function useApplyTheme(): void {
  const theme = useThemeStore((s) => s.theme)
  const preference = useThemeStore((s) => s.preference)
  const period = useThemeStore((s) => s.period)
  const syncSystemTheme = useThemeStore((s) => s.syncSystemTheme)
  const refreshPeriod = useThemeStore((s) => s.refreshPeriod)

  useLayoutEffect(() => {
    if (typeof window === 'undefined' || preference !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => syncSystemTheme()
    syncSystemTheme()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [preference, syncSystemTheme])

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
    if (favicon) {
      favicon.href = brandLogoForTheme(theme)
    }
    const appleTouch = document.querySelector<HTMLLinkElement>('link#app-apple-touch-icon')
    if (appleTouch) {
      appleTouch.href = brandLogoForTheme(theme)
    }
  }, [theme, period])
}
