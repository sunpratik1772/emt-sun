/**
 * /login — half-hero CTA on the left, auth panel on the right.
 *
 * The hero side is intentionally minimal monochrome (matches the
 * Studio aesthetic): a wordmark, a one-line pitch, and the "Start
 * building" CTA that drops the user into the same Google sign-in
 * flow the right-side panel uses. The right side hosts the actual
 * Google button so the page works whether the user clicks the CTA
 * or jumps straight to "Sign in".
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArcIcon, ArrowRight, Sparkles, Loader2, Mail, Lock } from '../icons/arc'
import { DEMO_AUTH_ENABLED } from '../lib/env'
import { useAuthStore } from '../store/authStore'
import { BASE } from '../services/api'
import BrandMark from '../components/BrandMark'

export default function LoginPage() {
  const navigate = useNavigate()
  const status = useAuthStore((s) => s.status)
  const refresh = useAuthStore((s) => s.refresh)
  const enableDemoUser = useAuthStore((s) => s.enableDemoUser)
  
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [error, setError] = useState('')

  // If a session cookie is already present, skip the login screen.
  useEffect(() => {
    // Don't flash login if we're returning from the OAuth callback —
    // that path is owned by AuthCallback and writes the cookie first.
    if (window.location.hash?.includes('session_id=')) return
    if (status === 'idle') {
      void (async () => {
        const ok = await refresh()
        if (!ok && DEMO_AUTH_ENABLED) await enableDemoUser()
      })()
    }
  }, [status, refresh, enableDemoUser])

  useEffect(() => {
    if (status === 'authenticated') navigate('/dashboard', { replace: true })
  }, [status, navigate])

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/register'
      const body = mode === 'login' 
        ? { email, password }
        : { email, password, name }

      const res = await fetch(`${BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'include',
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Authentication failed' }))
        throw new Error(data.detail || 'Authentication failed')
      }

      // Refresh auth state and redirect
      await refresh()
      navigate('/dashboard', { replace: true })
    } catch (err: any) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const handleDemoLogin = async () => {
    setError('')
    setDemoLoading(true)
    try {
      await enableDemoUser()
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      setError((err as Error).message || 'Demo login failed')
    } finally {
      setDemoLoading(false)
    }
  }

  return (
    <div
      className="relative min-h-screen w-full grid grid-cols-1 lg:grid-cols-2"
      style={{
        background: 'var(--bg-base)',
        color: 'var(--text-0)',
      }}
    >
      {/* LEFT — hero half */}
      <div
        className="relative flex flex-col"
        style={{
          padding: '40px 56px',
          borderRight: '1px solid var(--border)',
          background:
            'radial-gradient(ellipse 60% 50% at 30% 20%, color-mix(in srgb, var(--accent) 7%, transparent) 0%, transparent 70%)',
        }}
      >
        {/* Wordmark */}
        <div className="flex items-center gap-2.5">
          <BrandMark size={28} style={{ borderRadius: 7 }} />
          <div className="display" style={{ fontSize: 14.5, fontWeight: 540, letterSpacing: '-0.018em' }}>
            dbSherpa
          </div>
          <div
            className="font-mono"
            style={{
              fontSize: 9.5,
              padding: '1px 6px',
              borderRadius: 3,
              background: 'var(--bg-3)',
              border: '1px solid var(--border-soft)',
              color: 'var(--text-2)',
              letterSpacing: '0.10em',
              textTransform: 'uppercase',
            }}
          >
            Studio
          </div>
        </div>

        {/* Hero copy + CTA */}
        <div className="flex-1 flex flex-col justify-center" style={{ maxWidth: 540 }}>
          <div
            className="font-mono"
            style={{
              fontSize: 10.5,
              color: 'var(--text-2)',
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              marginBottom: 18,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <Sparkles size={12} strokeWidth={1.8} />
            <span>Agentic workflow studio</span>
          </div>
          <h1
            className="display"
            style={{
              fontSize: 'clamp(40px, 5.4vw, 64px)',
              lineHeight: 1.02,
              fontWeight: 540,
              letterSpacing: '-0.035em',
              marginBottom: 18,
              color: 'var(--text-0)',
            }}
          >
            Build AI workflows{' '}
            <span style={{ color: 'var(--text-2)' }}>visually.</span>
          </h1>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.55,
              color: 'var(--text-2)',
              marginBottom: 32,
              maxWidth: 480,
              letterSpacing: '-0.005em',
            }}
          >
            Drag intelligent nodes, chain them through AI agent layers,
            and create powerful automations — all from one canvas.
          </p>
          <button
            type="button"
            disabled
            data-testid="hero-start-building-btn"
            className="flex items-center gap-2"
            style={{
              alignSelf: 'flex-start',
              padding: '11px 20px',
              borderRadius: 8,
              background: 'var(--bg-3)',
              color: 'var(--text-3)',
              border: '1px solid var(--border-soft)',
              fontSize: 13.5,
              fontWeight: 540,
              letterSpacing: '-0.01em',
              cursor: 'not-allowed',
              fontFamily: 'inherit',
              opacity: 0.8,
            }}
          >
            <span>Google sign-in disabled</span>
            <ArcIcon icon={ArrowRight} size={14} />
          </button>

          {/* Tiny feature row */}
          <div className="flex items-center gap-5 mt-10 flex-wrap">
            {[
              ['32', 'nodes'],
              ['5', 'data sources'],
              ['5', 'skills'],
            ].map(([n, l]) => (
              <div key={l} className="flex items-baseline gap-1.5">
                <span
                  className="num"
                  style={{ fontSize: 14, color: 'var(--text-0)', fontWeight: 540, letterSpacing: '-0.01em' }}
                >
                  {n}
                </span>
                <span
                  className="font-mono"
                  style={{
                    fontSize: 10.5,
                    color: 'var(--text-3)',
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                  }}
                >
                  {l}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div
          className="font-mono flex items-center justify-between"
          style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.04em' }}
        >
          <span>© 2026 · dbSherpa Studio</span>
          <span>v1.1.0</span>
        </div>
      </div>

      {/* RIGHT — auth panel */}
      <div className="flex items-center justify-center" style={{ padding: '40px 32px' }}>
        <div
          className="w-full"
          style={{
            maxWidth: 420,
            padding: 32,
            borderRadius: 12,
            background: 'var(--bg-2)',
            border: '1px solid var(--border)',
            boxShadow: '0 24px 60px -32px rgba(0,0,0,0.18)',
          }}
        >
          <h2
            className="display"
            style={{ fontSize: 22, fontWeight: 540, letterSpacing: '-0.022em', marginBottom: 6 }}
          >
            {mode === 'login' ? 'Welcome back' : 'Create account'}
          </h2>
          <p style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 24, lineHeight: 1.5 }}>
            {mode === 'login' 
              ? 'Sign in to keep your workflows, drafts, and run history.'
              : 'Get started with your AI workflow studio.'}
          </p>

          {/* Email/Password Form */}
          <form onSubmit={handleEmailAuth} style={{ marginBottom: 16 }}>
            {mode === 'register' && (
              <div style={{ marginBottom: 12 }}>
                <label
                  htmlFor="name"
                  className="font-mono"
                  style={{
                    display: 'block',
                    fontSize: 10,
                    color: 'var(--text-2)',
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    marginBottom: 6,
                  }}
                >
                  Name
                </label>
                <div className="relative">
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required={mode === 'register'}
                    data-testid="register-name-input"
                    placeholder="Your name"
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 6,
                      border: '1px solid var(--border-strong)',
                      background: 'var(--bg-1)',
                      color: 'var(--text-0)',
                      fontSize: 13.5,
                      fontFamily: 'inherit',
                      outline: 'none',
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = 'var(--accent)'
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border-strong)'
                    }}
                  />
                </div>
              </div>
            )}
            
            <div style={{ marginBottom: 12 }}>
              <label
                htmlFor="email"
                className="font-mono"
                style={{
                  display: 'block',
                  fontSize: 10,
                  color: 'var(--text-2)',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  marginBottom: 6,
                }}
              >
                Email
              </label>
              <div className="relative">
                <Mail
                  size={14}
                  style={{
                    position: 'absolute',
                    left: 12,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-3)',
                  }}
                />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  data-testid={mode === 'login' ? 'login-email-input' : 'register-email-input'}
                  placeholder="you@example.com"
                  style={{
                    width: '100%',
                    padding: '10px 12px 10px 36px',
                    borderRadius: 6,
                    border: '1px solid var(--border-strong)',
                    background: 'var(--bg-1)',
                    color: 'var(--text-0)',
                    fontSize: 13.5,
                    fontFamily: 'inherit',
                    outline: 'none',
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent)'
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-strong)'
                  }}
                />
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label
                htmlFor="password"
                className="font-mono"
                style={{
                  display: 'block',
                  fontSize: 10,
                  color: 'var(--text-2)',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  marginBottom: 6,
                }}
              >
                Password
              </label>
              <div className="relative">
                <Lock
                  size={14}
                  style={{
                    position: 'absolute',
                    left: 12,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: 'var(--text-3)',
                  }}
                />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  data-testid={mode === 'login' ? 'login-password-input' : 'register-password-input'}
                  placeholder={mode === 'register' ? 'Min. 8 characters' : '••••••••'}
                  style={{
                    width: '100%',
                    padding: '10px 12px 10px 36px',
                    borderRadius: 6,
                    border: '1px solid var(--border-strong)',
                    background: 'var(--bg-1)',
                    color: 'var(--text-0)',
                    fontSize: 13.5,
                    fontFamily: 'inherit',
                    outline: 'none',
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent)'
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-strong)'
                  }}
                />
              </div>
            </div>

            {error && (
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 6,
                  background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
                  border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
                  color: 'var(--danger)',
                  fontSize: 12,
                  marginBottom: 16,
                  lineHeight: 1.5,
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              data-testid={mode === 'login' ? 'login-submit-btn' : 'register-submit-btn'}
              className="w-full flex items-center justify-center gap-2"
              style={{
                padding: '11px 16px',
                borderRadius: 8,
                background: 'var(--text-0)',
                color: 'var(--bg-base)',
                border: 'none',
                fontSize: 13.5,
                fontWeight: 540,
                letterSpacing: '-0.01em',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1,
                fontFamily: 'inherit',
              }}
            >
              {loading && <ArcIcon icon={Loader2} size={14} className="animate-spin" />}
              <span>{mode === 'login' ? 'Sign in' : 'Create account'}</span>
            </button>
          </form>

          {/* Toggle between login/register */}
          <div
            style={{
              textAlign: 'center',
              fontSize: 12,
              color: 'var(--text-2)',
              marginBottom: 16,
            }}
          >
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError('')
              }}
              data-testid="toggle-auth-mode-btn"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent)',
                cursor: 'pointer',
                fontFamily: 'inherit',
                fontSize: 12,
                fontWeight: 500,
                padding: 0,
              }}
            >
              {mode === 'login' ? 'Create one' : 'Sign in'}
            </button>
          </div>

          {/* Divider */}
          <div
            className="flex items-center gap-3"
            style={{ marginBottom: 16 }}
          >
            <div style={{ flex: 1, height: 1, background: 'var(--border-soft)' }} />
            <span
              className="font-mono"
              style={{ fontSize: 10, color: 'var(--text-3)', letterSpacing: '0.08em' }}
            >
              OR
            </span>
            <div style={{ flex: 1, height: 1, background: 'var(--border-soft)' }} />
          </div>

          {/* Google Sign In */}
          <button
            type="button"
            disabled
            data-testid="login-google-btn"
            className="w-full flex items-center justify-center gap-2.5"
            style={{
              padding: '11px 16px',
              borderRadius: 8,
              background: 'var(--bg-3)',
              color: 'var(--text-3)',
              border: '1px solid var(--border-soft)',
              fontSize: 13.5,
              fontWeight: 510,
              letterSpacing: '-0.005em',
              cursor: 'not-allowed',
              fontFamily: 'inherit',
              opacity: 0.85,
            }}
          >
            <GoogleGlyph />
            <span>Continue with Google (disabled)</span>
          </button>

          <button
            type="button"
            onClick={handleDemoLogin}
            disabled={demoLoading || loading}
            data-testid="login-demo-btn"
            className="w-full flex items-center justify-center gap-2.5"
            style={{
              marginTop: 10,
              padding: '11px 16px',
              borderRadius: 8,
              background: 'var(--text-0)',
              color: 'var(--bg-base)',
              border: '1px solid var(--text-0)',
              fontSize: 13.5,
              fontWeight: 540,
              letterSpacing: '-0.01em',
              cursor: demoLoading || loading ? 'not-allowed' : 'pointer',
              opacity: demoLoading || loading ? 0.65 : 1,
              fontFamily: 'inherit',
            }}
          >
            {demoLoading && <ArcIcon icon={Loader2} size={14} className="animate-spin" />}
            <span>Continue as John Doe</span>
          </button>

          <div
            className="font-mono"
            style={{
              fontSize: 10,
              color: 'var(--text-3)',
              letterSpacing: '0.04em',
              marginTop: 18,
              textAlign: 'center',
              lineHeight: 1.55,
            }}
          >
            By continuing you agree to our terms.<br />
            We'll only use your name, email and avatar.
          </div>
        </div>
      </div>
    </div>
  )
}

function GoogleGlyph() {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} aria-hidden>
      <path
        fill="#4285F4"
        d="M22.5 12.27c0-.79-.07-1.55-.2-2.27H12v4.3h5.92a5.06 5.06 0 0 1-2.2 3.32v2.76h3.55c2.08-1.92 3.28-4.74 3.28-8.11Z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.55-2.76c-.99.66-2.25 1.06-3.73 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.11A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.11V7.05H2.18a11 11 0 0 0 0 9.9l3.66-2.84Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.61 0 3.06.55 4.2 1.64l3.15-3.15C17.45 2.05 14.97 1 12 1A11 11 0 0 0 2.18 7.05l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"
      />
    </svg>
  )
}
