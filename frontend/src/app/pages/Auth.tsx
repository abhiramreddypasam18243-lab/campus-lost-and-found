import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { errorMessage } from '../format'
import { Link, navigate } from '../router'
import { Alert, Button, Card, Loading, TextField } from '../ui'

/** Synthetic accounts created by `python -m app.seed` (README). Never real people. */
const DEMO_ACCOUNTS = [
  { label: 'Student (Alice)', email: 'student1@campus.edu', password: 'StudentPass2026!' },
  { label: 'Student (Bob)', email: 'student2@campus.edu', password: 'StudentPass2026!' },
  { label: 'Moderator', email: 'moderator@campus.edu', password: 'CampusMod2026!' },
  { label: 'Admin', email: 'admin@campus.edu', password: 'CampusAdmin2026!' },
]
const SHOW_DEMO = import.meta.env.VITE_SHOW_DEMO_ACCOUNTS !== 'false'

export function LoginPage({ next }: { next: string }) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e?: FormEvent, override?: { email: string; password: string }) => {
    e?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(override?.email ?? email.trim(), override?.password ?? password)
      navigate(next || '/')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-intro">
        <p className="eyebrow">Campus Lost &amp; Found</p>
        <h1 className="auth-title">Lost something on campus? Found something?</h1>
        <p className="auth-lead">
          Report it once. We suggest likely matches using the description, photos, place and time —
          and a moderator checks every claim before anything changes hands.
        </p>
        <ul className="auth-points">
          <li>Lost reports stay private to you and campus staff.</li>
          <li>Found items are shown without private details.</li>
          <li>Items are collected at the desk with a one-time code.</li>
        </ul>
      </div>

      <Card className="auth-card">
        <h2>Sign in</h2>
        <form onSubmit={submit} noValidate>
          {error !== null && <Alert tone="danger">{errorMessage(error)}</Alert>}
          <TextField
            label="Campus email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button type="submit" busy={busy} className="btn-block">
            Sign in
          </Button>
        </form>
        <p className="auth-switch">
          New here? <Link to="/register">Create an account</Link>
        </p>

        {SHOW_DEMO && (
          <div className="demo-box">
            <p className="demo-title">Demo accounts (synthetic data)</p>
            <div className="demo-grid">
              {DEMO_ACCOUNTS.map((a) => (
                <Button
                  key={a.email}
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => {
                    setEmail(a.email)
                    setPassword(a.password)
                    void submit(undefined, a)
                  }}
                >
                  {a.label}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

export function RegisterPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [fields, setFields] = useState<Record<string, string>>({})
  const [error, setError] = useState<unknown>(null)
  const [done, setDone] = useState<{ email: string; url?: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const f: Record<string, string> = {}
    if (!email.includes('@')) f.email = 'Enter your campus email address.'
    if (password.length < 12 || password.length > 128) f.password = 'Use 12 to 128 characters.'
    if (confirm !== password) f.confirm = 'The passwords do not match.'
    setFields(f)
    if (Object.keys(f).length) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.post<{ email: string; verification_url?: string }>('/api/auth/register', {
        email: email.trim(),
        password,
        display_name: name.trim() || null,
      })
      setDone({ email: email.trim(), url: res.verification_url })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'email_domain_not_allowed') {
        setFields({ email: errorMessage(err) })
      } else if (err instanceof ApiError && Object.keys(err.fields).length) {
        setFields(err.fields)
      } else {
        setError(err)
      }
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="narrow">
        <Card>
          <div className="state">
            <div className="state-icon" aria-hidden="true">📬</div>
            <h1 className="state-title">Check your inbox</h1>
            <p className="state-text">
              We sent a verification link to <strong>{done.email}</strong>. Open it within 24 hours to activate
              reporting and claims.
            </p>
            {done.url && (
              <div style={{ margin: '1rem 0' }}>
                <Button onClick={() => navigate(done.url!.replace('/#', ''))}>
                  Verify email now (Instant Verification)
                </Button>
              </div>
            )}
            <Button variant="ghost" onClick={() => navigate('/login')}>Go to sign in</Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="narrow">
      <Card>
        <h1>Create your account</h1>
        <p className="muted">Only your campus email and an optional display name are stored.</p>
        <form onSubmit={submit} noValidate>
          {error !== null && <Alert tone="danger">{errorMessage(error)}</Alert>}
          <TextField
            label="Display name"
            hint="Optional. Shown to moderators, never to other students."
            autoComplete="nickname"
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <TextField
            label="Campus email"
            type="email"
            autoComplete="email"
            required
            error={fields.email}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            required
            hint="12 to 128 characters. A short sentence works well."
            error={fields.password}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <TextField
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            required
            error={fields.confirm}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
          <Button type="submit" busy={busy} className="btn-block">
            Create account
          </Button>
        </form>
        <p className="auth-switch">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </Card>
    </div>
  )
}

export function VerifyPage({ token }: { token: string | null }) {
  const { refresh, user } = useAuth()
  const [state, setState] = useState<'working' | 'ok' | 'error'>('working')
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    if (!token) {
      setState('error')
      return
    }
    api
      .post('/api/auth/verify-email', { token })
      .then(async () => {
        setState('ok')
        await refresh()
      })
      .catch((err: unknown) => {
        setError(err)
        setState('error')
      })
  }, [token, refresh])

  return (
    <div className="narrow">
      <Card>
        {state === 'working' && <Loading label="Confirming your email" />}
        {state === 'ok' && (
          <div className="state">
            <div className="state-icon" aria-hidden="true">✅</div>
            <h1 className="state-title">Email confirmed</h1>
            <p className="state-text">You can now report items and submit claims.</p>
            <Button onClick={() => navigate(user ? '/' : '/login')}>{user ? 'Continue' : 'Sign in'}</Button>
          </div>
        )}
        {state === 'error' && (
          <div className="state state-error">
            <div className="state-icon" aria-hidden="true">⏱️</div>
            <h1 className="state-title">This link can’t be used</h1>
            <p className="state-text">
              {error instanceof ApiError && error.status === 410
                ? 'It was already used or has expired (links last 24 hours).'
                : 'The verification link is missing or invalid.'}
            </p>
          </div>
        )}
      </Card>
    </div>
  )
}
