import { useState, type ReactNode } from 'react'
import { api } from './api'
import { AuthProvider, isAdmin, isStaff, useAuth } from './auth'
import { Link, navigate, useRoute, type Route } from './router'
import { Alert, Button, EmptyState, Loading, ToastHost } from './ui'
import { AccountPage, NotificationsPage, useUnreadCount } from './pages/Account'
import { AdminPage, DashboardPage, type AdminTab } from './pages/Admin'
import { LoginPage, RegisterPage, VerifyPage } from './pages/Auth'
import { BrowsePage, FoundDetailPage } from './pages/Browse'
import { ClaimDetailPage, ClaimFormPage, MyClaimsPage } from './pages/Claims'
import { DeskPage, ModClaimPage, ModReportPage, QueuePage } from './pages/Moderation'
import { MyReportDetailPage, MyReportsPage, ReportFormPage } from './pages/Reports'

type NavItem = { to: string; label: string; match: (p: string) => boolean }

function navFor(role: string | undefined): NavItem[] {
  const items: NavItem[] = [
    { to: '/', label: 'Found items', match: (p) => p === '/' || p.startsWith('/found') },
    { to: '/reports', label: 'My reports', match: (p) => p.startsWith('/reports') || p.startsWith('/report/') },
    { to: '/claims', label: 'My claims', match: (p) => p.startsWith('/claims') || p.startsWith('/claim/') },
  ]
  if (role === 'moderator' || role === 'admin') {
    items.push(
      { to: '/mod/queue', label: 'Queue', match: (p) => p.startsWith('/mod/queue') || p.startsWith('/mod/claims') || p.startsWith('/mod/reports') },
      { to: '/mod/desk', label: 'Handover desk', match: (p) => p.startsWith('/mod/desk') },
      { to: '/dashboard', label: 'Dashboard', match: (p) => p.startsWith('/dashboard') },
    )
  }
  if (role === 'admin') items.push({ to: '/admin', label: 'Admin', match: (p) => p.startsWith('/admin') })
  return items
}

function Header({ route }: { route: Route }) {
  const { user, logout } = useAuth()
  const unread = useUnreadCount(Boolean(user))
  const [menuOpen, setMenuOpen] = useState(false)
  const items = navFor(user?.role)
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="brand" aria-label="Campus Lost and Found, home">
          <span className="brand-mark" aria-hidden="true">
            ◎
          </span>
          <span className="brand-text">
            Campus <strong>Lost &amp; Found</strong>
          </span>
        </Link>
        {user && (
          <>
            <nav className="nav" aria-label="Main">
              {items.map((it) => (
                <Link key={it.to} to={it.to} className={`nav-link ${it.match(route.path) ? 'nav-active' : ''}`} aria-current={it.match(route.path) ? 'page' : undefined}>
                  {it.label}
                </Link>
              ))}
            </nav>
            <div className="topbar-actions">
              <Link to="/notifications" className="icon-btn" aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}>
                <span aria-hidden="true">🔔</span>
                {unread > 0 && (
                  <span className="dot-count" aria-hidden="true">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </Link>
              <div className="menu">
                <button
                  type="button"
                  className="avatar"
                  aria-haspopup="true"
                  aria-expanded={menuOpen}
                  onClick={() => setMenuOpen(!menuOpen)}
                  aria-label="Account menu"
                >
                  {(user.display_name || user.email).slice(0, 1).toUpperCase()}
                </button>
                {menuOpen && (
                  <div className="menu-pop" role="menu" onKeyDown={(e) => e.key === 'Escape' && setMenuOpen(false)}>
                    <div className="menu-head">
                      <strong>{user.display_name || user.email}</strong>
                      <span className="muted small">
                        {user.email} · {user.role}
                      </span>
                    </div>
                    <a role="menuitem" href="#/account" onClick={() => setMenuOpen(false)}>
                      Account &amp; privacy
                    </a>
                    <button
                      role="menuitem"
                      type="button"
                      onClick={async () => {
                        setMenuOpen(false)
                        await logout()
                        navigate('/login')
                      }}
                    >
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
        {!user && (
          <div className="topbar-actions">
            <Link to="/login" className="btn btn-ghost btn-sm">
              Sign in
            </Link>
            <Link to="/register" className="btn btn-primary btn-sm">
              Register
            </Link>
          </div>
        )}
      </div>
      {user && (
        <nav className="nav-mobile" aria-label="Main (mobile)">
          {items.map((it) => (
            <Link key={it.to} to={it.to} className={`nav-link ${it.match(route.path) ? 'nav-active' : ''}`} aria-current={it.match(route.path) ? 'page' : undefined}>
              {it.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  )
}

function Forbidden() {
  return (
    <EmptyState icon="🚫" title="You don’t have access to this page" action={<Button onClick={() => navigate('/')}>Go home</Button>}>
      This area is for campus staff.
    </EmptyState>
  )
}

function NotFoundPage() {
  return (
    <EmptyState icon="🧭" title="Page not found" action={<Button onClick={() => navigate('/')}>Go home</Button>} />
  )
}

function Routes({ route }: { route: Route }) {
  const { user, loading } = useAuth()
  const [s0, s1, s2] = route.segments
  const q = route.query

  if (loading) return <Loading label="Starting" />

  // Public routes
  if (s0 === 'register') return <RegisterPage />
  if (s0 === 'verify') return <VerifyPage token={q.get('token')} />
  if (s0 === 'login' || !user) return <LoginPage next={s0 === 'login' ? (q.get('next') ?? '/') : route.path} />

  const staffOnly = (node: ReactNode) => (isStaff(user) ? node : <Forbidden />)
  const adminOnly = (node: ReactNode) => (isAdmin(user) ? node : <Forbidden />)

  switch (s0) {
    case undefined:
      return <BrowsePage />
    case 'found':
      return s1 ? <FoundDetailPage id={s1} /> : <BrowsePage />
    case 'report':
      return <ReportFormPage initialType={q.get('type') === 'found' ? 'found' : 'lost'} />
    case 'reports':
      return s1 ? <MyReportDetailPage id={s1} /> : <MyReportsPage />
    case 'claim':
      return s1 ? <ClaimFormPage foundId={s1} lostId={q.get('lost')} /> : <NotFoundPage />
    case 'claims':
      return s1 ? <ClaimDetailPage id={s1} /> : <MyClaimsPage />
    case 'notifications':
      return <NotificationsPage />
    case 'account':
      return <AccountPage />
    case 'mod':
      if (s1 === 'queue') return staffOnly(<QueuePage />)
      if (s1 === 'reports' && s2) return staffOnly(<ModReportPage id={s2} />)
      if (s1 === 'claims' && s2) return staffOnly(<ModClaimPage id={s2} />)
      if (s1 === 'desk') return staffOnly(<DeskPage />)
      return <NotFoundPage />
    case 'dashboard':
      return staffOnly(<DashboardPage />)
    case 'admin': {
      const tab = (s1 as AdminTab) || 'users'
      return adminOnly(<AdminPage tab={tab} onTab={(t) => navigate(`/admin/${t}`)} />)
    }
    default:
      return <NotFoundPage />
  }
}

function VerifyBanner() {
  const { user, refresh } = useAuth()
  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [resending, setResending] = useState(false)
  const [statusMsg, setStatusMsg] = useState<{ tone: 'danger' | 'info' | 'success'; text: string } | null>(null)
  if (!user || user.email_verified) return null

  const handleVerifyCode = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const clean = code.trim()
    if (!clean) {
      setStatusMsg({ tone: 'danger', text: 'Please enter your verification code.' })
      return
    }
    setSubmitting(true)
    setStatusMsg(null)
    try {
      await api.post('/api/auth/verify-email', { token: clean })
      setStatusMsg({ tone: 'success', text: 'Email verified successfully!' })
      await refresh()
    } catch {
      setStatusMsg({ tone: 'danger', text: 'Invalid or expired verification code.' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleResendCode = async () => {
    setResending(true)
    setStatusMsg(null)
    try {
      await api.post('/api/auth/resend-verification')
      setStatusMsg({ tone: 'info', text: 'A new 6-digit verification code has been emailed to your Gmail.' })
    } catch {
      setStatusMsg({ tone: 'danger', text: 'Unable to send verification email. Please check your SMTP settings.' })
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="container" style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
      <Alert tone="warning" title="Confirm your campus email">
        <p style={{ margin: 0 }}>
          Enter the 6-digit verification code sent to <strong>{user.email}</strong> to report items and make claims.
        </p>
        <form
          onSubmit={handleVerifyCode}
          style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}
        >
          <input
            type="text"
            className="input"
            style={{ width: '150px', letterSpacing: '2px', fontWeight: 'bold', textAlign: 'center', padding: '0.35rem 0.5rem' }}
            placeholder="6-digit code"
            maxLength={32}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <Button type="submit" size="sm" busy={submitting}>
            Verify Code
          </Button>
          <Button type="button" variant="ghost" size="sm" busy={resending} onClick={handleResendCode}>
            Resend Code
          </Button>
        </form>
        {statusMsg && (
          <div style={{ marginTop: '0.5rem' }}>
            <span className={`small ${statusMsg.tone === 'danger' ? 'text-danger' : 'muted'}`} style={{ fontWeight: '500' }}>
              {statusMsg.text}
            </span>
          </div>
        )}
      </Alert>
    </div>
  )
}

function Shell() {
  const route = useRoute()
  return (
    <>
      <a href="#main" className="skip-link" onClick={(e) => {
        e.preventDefault()
        document.getElementById('main')?.focus()
      }}>
        Skip to content
      </a>
      <Header route={route} />
      <VerifyBanner />
      <main id="main" className="container main" tabIndex={-1}>
        <Routes route={route} />
      </main>
      <footer className="footer container">
        <p>
          Match scores are suggestions, never proof of ownership. Every claim is reviewed by campus staff.
        </p>
      </footer>
      <ToastHost />
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}
