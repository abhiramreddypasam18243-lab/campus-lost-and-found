import { useCallback, useEffect, useState, type FormEvent } from 'react'
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
        <h1 className="auth-title">
          Lost it? <em>Someone</em> probably found it.
        </h1>
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
  const [done, setDone] = useState<{ email: string } | null>(null)
  const [verifyInput, setVerifyInput] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [verifiedSuccess, setVerifiedSuccess] = useState(false)
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
      const res = await api.post<{ verified?: boolean }>('/api/auth/register', {
        email: email.trim(),
        password,
        display_name: name.trim() || null,
      })
      setDone({ email: email.trim() })
      setVerifiedSuccess(res?.verified === true)
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
            <div className="state-icon" aria-hidden="true">{verifiedSuccess ? '✅' : '📬'}</div>
            <h1 className="state-title">{verifiedSuccess ? 'Account ready' : 'Check your email'}</h1>
            {verifiedSuccess ? (
              <div>
                <p className="state-text">Your campus email is confirmed. You can now sign in.</p>
                <Button onClick={() => navigate('/login')}>Sign in now</Button>
              </div>
            ) : (
              <div style={{ width: '100%' }}>
                <p className="state-text">
                  A 6-digit verification code has been sent to <strong>{done.email}</strong>.
                  Check your inbox and enter the code below to activate your account.
                </p>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault()
                    const c = verifyInput.trim()
                    if (!c) return
                    setVerifying(true)
                    setVerifyError(null)
                    try {
                      await api.post('/api/auth/verify-email', { token: c })
                      setVerifiedSuccess(true)
                    } catch {
                      setVerifyError('Invalid or expired verification code. Please check and try again.')
                    } finally {
                      setVerifying(false)
                    }
                  }}
                  style={{ marginTop: '1rem', textAlign: 'left' }}
                >
                  {verifyError && <Alert tone="danger">{verifyError}</Alert>}
                  <TextField
                    label="Enter 6-digit code"
                    placeholder="e.g. 123456"
                    value={verifyInput}
                    onChange={(e) => setVerifyInput(e.target.value)}
                    required
                    maxLength={32}
                  />
                  <Button type="submit" busy={verifying} className="btn-block">
                    Verify Code
                  </Button>
                  <p style={{ marginTop: '0.75rem', textAlign: 'center' }}>
                    <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>Skip to sign in</Button>
                  </p>
                </form>
              </div>
            )}
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
  const [manualCode, setManualCode] = useState(token || '')
  const [state, setState] = useState<'working' | 'ok' | 'idle' | 'error'>(token ? 'working' : 'idle')
  const [error, setError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)

  const verifyWithCode = useCallback(async (codeToVerify: string) => {
    const clean = codeToVerify.trim()
    if (!clean) return
    setState('working')
    setError(null)
    setSubmitting(true)
    try {
      await api.post('/api/auth/verify-email', { token: clean })
      setState('ok')
      await refresh()
    } catch (err: unknown) {
      setError(err)
      setState('error')
    } finally {
      setSubmitting(false)
    }
  }, [refresh])

  useEffect(() => {
    if (token) {
      verifyWithCode(token)
    }
  }, [token, verifyWithCode])

  const handleManualSubmit = async (e: FormEvent) => {
    e.preventDefault()
    await verifyWithCode(manualCode)
  }

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
        {state !== 'ok' && state !== 'working' && (
          <div>
            <h1>Enter verification code</h1>
            <p className="muted">Enter the 6-digit verification code sent to your campus email.</p>
            {error !== null && (
              <Alert tone="danger">
                {error instanceof ApiError && error.status === 410
                  ? 'Verification code has expired or has already been used.'
                  : 'Invalid verification code. Please check and try again.'}
              </Alert>
            )}
            <form onSubmit={handleManualSubmit}>
              <TextField
                label="Verification code"
                placeholder="e.g. 123456"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                required
                maxLength={64}
              />
              <Button type="submit" busy={submitting} className="btn-block">
                Verify Code
              </Button>
            </form>
            <p className="auth-switch">
              Need to sign in? <Link to="/login">Sign in</Link>
            </p>
          </div>
        )}
      </Card>
    </div>
  )
}
