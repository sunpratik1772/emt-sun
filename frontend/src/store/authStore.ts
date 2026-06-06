/**
 * Auth store + helpers.
 *
 * Single source of truth for the current user. The component tree
 * subscribes via `useAuthStore`; the imperative `loginWithGoogle()`
 * helper kicks off the Emergent OAuth dance; `logout()` calls the
 * backend and clears local state.
 *
 * The actual session-id-for-session-token exchange happens in
 * `AuthCallback` because it needs the URL fragment (which only
 * exists on the redirect bounce). Everything else just calls
 * `/api/auth/me` and trusts the cookie.
 */
import { create } from 'zustand'
import { DEMO_AUTH_ENABLED } from '../lib/env'

export interface AuthUser {
  user_id: string
  username?: string | null
  email: string
  name: string
  picture?: string | null
  role?: string | null
}

export function userIsAdmin(user: AuthUser | null | undefined): boolean {
  return (user?.role || 'user').toLowerCase() === 'admin'
}

const DEMO_AUTH_STORAGE_KEY = 'dbsherpa_demo_auth'
export const DEMO_USERNAME = 'johndoe'
export const DEMO_PASSWORD = 'password123'

function readDemoAuthFlag(): boolean {
  if (!DEMO_AUTH_ENABLED) return false
  try {
    return window.localStorage.getItem(DEMO_AUTH_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function persistDemoAuth(enabled: boolean): void {
  if (!DEMO_AUTH_ENABLED) return
  try {
    if (enabled) window.localStorage.setItem(DEMO_AUTH_STORAGE_KEY, '1')
    else window.localStorage.removeItem(DEMO_AUTH_STORAGE_KEY)
  } catch {
    /* noop: auth state still lives in-memory */
  }
}

async function loginJohnDoe(): Promise<AuthUser | null> {
  const r = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: DEMO_USERNAME, password: DEMO_PASSWORD }),
  })
  if (!r.ok) return null
  const payload = (await r.json()) as { user: AuthUser }
  persistDemoAuth(true)
  return payload.user
}

interface AuthState {
  user: AuthUser | null
  /** `null` = not yet checked, `true` = checked + signed in, `false` = checked + signed out. */
  status: 'idle' | 'checking' | 'authenticated' | 'unauthenticated'
  setUser: (u: AuthUser | null) => void
  setStatus: (s: AuthState['status']) => void
  enableDemoUser: () => Promise<void>
  /** Fetch /auth/me and update state. Returns `true` if signed in. */
  refresh: () => Promise<boolean>
  logout: () => Promise<void>
}

const API = '/api'

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  status: 'idle',
  setUser: (u) => {
    if (u?.username === DEMO_USERNAME) persistDemoAuth(true)
    if (!u) persistDemoAuth(false)
    set({ user: u, status: u ? 'authenticated' : 'unauthenticated' })
  },
  setStatus: (s) => set({ status: s }),
  enableDemoUser: async () => {
    if (!DEMO_AUTH_ENABLED) return
    set({ status: 'checking' })
    try {
      const user = await loginJohnDoe()
      if (!user) throw new Error('demo login failed')
      set({ user, status: 'authenticated' })
    } catch {
      persistDemoAuth(false)
      set({ user: null, status: 'unauthenticated' })
    }
  },
  refresh: async () => {
    set({ status: 'checking' })
    try {
      const r = await fetch(`${API}/auth/me`, { credentials: 'include' })
      if (r.ok) {
        const u: AuthUser = await r.json()
        set({ user: u, status: 'authenticated' })
        return true
      }
    } catch {
      /* fall through */
    }

    if (DEMO_AUTH_ENABLED || readDemoAuthFlag()) {
      try {
        const user = await loginJohnDoe()
        if (user) {
          set({ user, status: 'authenticated' })
          return true
        }
      } catch {
        /* fall through */
      }
    }

    set({ user: null, status: 'unauthenticated' })
    return false
  },
  logout: async () => {
    persistDemoAuth(false)
    try {
      await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' })
    } catch {
      /* swallow — local state is what the UI cares about */
    }
    set({ user: null, status: 'unauthenticated' })
  },
}))

/**
 * Kick off Google OAuth via Emergent's hosted flow. After the user
 * accepts, the browser is redirected back to `${origin}/dashboard`
 * with `#session_id=…` in the fragment.
 *
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
 */
export function loginWithGoogle(): void {
  const redirectUrl = window.location.origin + '/dashboard'
  window.location.href =
    'https://auth.emergentagent.com/?redirect=' + encodeURIComponent(redirectUrl)
}

/** "Pratik Singh" → "PS"; falls back to first letter of email. */
export function userInitials(u: AuthUser | null | undefined): string {
  if (!u) return '?'
  const name = (u.name || '').trim()
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean)
    const a = parts[0]?.[0] ?? ''
    const b = parts.length > 1 ? parts[parts.length - 1][0] : ''
    return (a + b).toUpperCase().slice(0, 2)
  }
  return (u.email?.[0] ?? '?').toUpperCase()
}
