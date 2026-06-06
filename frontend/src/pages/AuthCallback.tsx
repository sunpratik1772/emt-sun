/**
 * /dashboard#session_id=… handler.
 *
 * The Emergent OAuth flow drops the user back here with a one-time
 * `session_id` in the URL fragment. We exchange it for a real
 * session token via `/api/auth/session`, store the user in the auth
 * store, and replace the URL so a refresh doesn't re-trigger the
 * exchange.
 *
 * Race-condition notes:
 *   • The `session_id` is detected synchronously (during render in
 *     the Router shell) — useEffect runs too late to beat the
 *     ProtectedRoute's `checkAuth`.
 *   • The actual exchange happens here in useEffect, but we use a
 *     `useRef` flag to guarantee idempotency under React StrictMode.
 */
import { useEffect, useRef, useState } from 'react'
import { ArcIcon, Loader2 } from '../icons/arc'
import { useAuthStore, type AuthUser } from '../store/authStore'

export default function AuthCallback() {
  const setUser = useAuthStore((s) => s.setUser)
  const hasProcessed = useRef(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (hasProcessed.current) return
    hasProcessed.current = true

    const m = window.location.hash.match(/session_id=([^&]+)/)
    if (!m) {
      setError('Missing session_id')
      return
    }
    const sessionId = decodeURIComponent(m[1])

    ;(async () => {
      try {
        const r = await fetch('/api/auth/session', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId }),
        })
        if (!r.ok) {
          const txt = await r.text()
          throw new Error(`auth failed: ${r.status} ${txt.slice(0, 200)}`)
        }
        const data: { user: AuthUser } = await r.json()
        setUser(data.user)
        // Replace the URL so the next reload doesn't try to
        // re-exchange a now-spent session_id.
        window.history.replaceState({}, '', '/dashboard')
        // Hard navigate to ensure the rest of the app re-mounts under
        // the authenticated route.
        window.location.replace('/dashboard')
      } catch (e) {
        setError((e as Error).message)
      }
    })()
  }, [setUser])

  return (
    <div
      className="flex flex-col items-center justify-center min-h-screen"
      style={{ background: 'var(--bg-base)', color: 'var(--text-0)' }}
    >
      <ArcIcon icon={Loader2} size={20} className="animate-spin" style={{ color: 'var(--text-2)' }} />
      <div
        className="font-mono mt-4"
        style={{ fontSize: 11, color: 'var(--text-2)', letterSpacing: '0.10em', textTransform: 'uppercase' }}
      >
        {error ? 'Sign-in failed' : 'Signing you in…'}
      </div>
      {error && (
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--danger)', maxWidth: 420, textAlign: 'center' }}>
          {error}{' '}
          <a href="/login" style={{ color: 'var(--text-0)', textDecoration: 'underline' }}>
            Try again
          </a>
        </div>
      )}
    </div>
  )
}
