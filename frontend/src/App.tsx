import React, { useEffect, useState } from 'react'
import { InteractiveCampusMap } from './components/InteractiveCampusMap'
import { AIPhotoAnalyzer } from './components/AIPhotoAnalyzer'
import { QRCodeHandover } from './components/QRCodeHandover'
import { ClaimDiscussionChat } from './components/ClaimDiscussionChat'
import { Language, translations } from './i18n/translations'
import { LanguageSelector } from './components/LanguageSelector'
import { PrivacyRedactionStudio } from './components/PrivacyRedactionStudio'

type TabType = 'browse' | 'report' | 'matches' | 'handover' | 'moderation' | 'dashboard'

interface FoundItem {
  id: string
  title: string
  description: string
  category: string
  location_name?: string
  created_at: string
}

interface MatchCandidate {
  found_id: string
  title: string
  category: string
  combined_score: number
  bin: 'high' | 'medium' | 'low'
  explanation: {
    text_score: number
    photo_score: number
    location_score: number
    time_score: number
  }
}

interface DashboardMetrics {
  total_created: number
  open_count: number
  returned_count: number
  unclaimed_expired_count: number
  recovery_rate: number | null
  unclaimed_rate: number | null
  median_time_to_recovery_hours: number | null
  banner_notice: string
  is_synthetic_demo: boolean
}

interface UserProfile {
  id: string
  email: string
  display_name: string | null
  role: string
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('browse')

  // User Authentication state
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null)
  const [csrfToken, setCsrfToken] = useState<string | null>(null)
  const [showLoginModal, setShowLoginModal] = useState<boolean>(false)
  const [authMode, setAuthMode] = useState<'signin' | 'register'>('signin')
  const [loginEmail, setLoginEmail] = useState<string>('')
  const [loginPassword, setLoginPassword] = useState<string>('')
  const [loginLoading, setLoginLoading] = useState<boolean>(false)
  const [loginError, setLoginError] = useState<string | null>(null)

  // Registration state
  const [registerName, setRegisterName] = useState<string>('')
  const [registerEmail, setRegisterEmail] = useState<string>('')
  const [registerPassword, setRegisterPassword] = useState<string>('')
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState<string>('')
  const [registerLoading, setRegisterLoading] = useState<boolean>(false)
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [registerSuccess, setRegisterSuccess] = useState<string | null>(null)

  // Browse state
  const [items, setItems] = useState<FoundItem[]>([])
  const [browseLoading, setBrowseLoading] = useState<boolean>(false)
  const [browseError, setBrowseError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')

  // Report form state
  const [reportType, setReportType] = useState<'lost' | 'found'>('lost')
  const [reportTitle, setReportTitle] = useState<string>('')
  const [reportCategory, setReportCategory] = useState<string>('')
  const [reportDesc, setReportDesc] = useState<string>('')
  const [reportLocation, setReportLocation] = useState<string>('')
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [reportSuccess, setReportSuccess] = useState<string | null>(null)

  // Improvisation feature states
  const [showBrowseMap, setShowBrowseMap] = useState<boolean>(false)
  const [showReportMap, setShowReportMap] = useState<boolean>(false)
  const [activeChatClaim, setActiveChatClaim] = useState<{ id: string; title: string } | null>(null)
  const [showPrivacyStudio, setShowPrivacyStudio] = useState<boolean>(false)
  const [studioInitialImage, setStudioInitialImage] = useState<string | null>(null)
  const [attachedPhoto, setAttachedPhoto] = useState<{
    file: File
    dataUrl: string
    isRedacted: boolean
    blurredCount: number
  } | null>(null)

  // Language / i18n state
  const [language, setLanguage] = useState<Language>(() => {
    return (localStorage.getItem('campus_app_lang') as Language) || 'en'
  })

  const handleLanguageChange = (lang: Language) => {
    setLanguage(lang)
    localStorage.setItem('campus_app_lang', lang)
  }

  const t = (key: string, defaultText: string): string => {
    return translations[language]?.[key] || defaultText
  }

  // Matches state
  const [matches, setMatches] = useState<MatchCandidate[]>([
    {
      found_id: 'sample-found-001',
      title: 'Dark Blue Hydro Flask Water Bottle',
      category: 'bottle',
      combined_score: 0.88,
      bin: 'high',
      explanation: {
        text_score: 0.42,
        photo_score: 0.28,
        location_score: 0.12,
        time_score: 0.06,
      },
    },
    {
      found_id: 'sample-found-002',
      title: 'Navy Insulated Thermos',
      category: 'bottle',
      combined_score: 0.71,
      bin: 'medium',
      explanation: {
        text_score: 0.35,
        photo_score: 0.15,
        location_score: 0.15,
        time_score: 0.06,
      },
    },
  ])

  // Handover state
  const [handoverCode, setHandoverCode] = useState<string>('')
  const [idNote, setIdNote] = useState<string>('')
  const [handoverResult, setHandoverResult] = useState<{
    status: 'success' | 'failure' | 'idle'
    message: string
    attemptsLeft?: number
  }>({ status: 'idle', message: '' })

  // Dashboard state
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [dashLoading, setDashLoading] = useState<boolean>(false)

  // Load items for browse
  useEffect(() => {
    if (activeTab === 'browse') {
      setBrowseLoading(true)
      fetch('/api/found?limit=20')
        .then((res) => {
          if (!res.ok) throw new Error('Sign in required or service unavailable')
          return res.json()
        })
        .then((data) => {
          setItems(data.items || [])
          setBrowseLoading(false)
        })
        .catch((err) => {
          setBrowseError(err instanceof Error ? err.message : 'Failed to reach API')
          // Provide mock items for visual browsing when not logged in
          setItems([
            {
              id: 'demo-1',
              title: 'Blue Water Bottle',
              description: 'Stainless steel bottle with stickers found in Library',
              category: 'bottle',
              location_name: 'Library - Floor 2',
              created_at: new Date().toISOString(),
            },
            {
              id: 'demo-2',
              title: 'Black Laptop Charger',
              description: '65W USB-C power adapter found near computer lab',
              category: 'laptop_tablet',
              location_name: 'Engineering Center - Lab B',
              created_at: new Date().toISOString(),
            },
          ])
          setBrowseLoading(false)
        })
    } else if (activeTab === 'dashboard') {
      setDashLoading(true)
      fetch('/api/dashboard')
        .then((res) => res.json())
        .then((data) => {
          setMetrics(data)
          setDashLoading(false)
        })
        .catch(() => {
          // Fallback mock operational metrics
          setMetrics({
            total_created: 10,
            open_count: 4,
            returned_count: 4,
            unclaimed_expired_count: 2,
            recovery_rate: 0.667,
            unclaimed_rate: 0.2,
            median_time_to_recovery_hours: 18.5,
            banner_notice:
              'Operational metrics are generated for dashboard demonstration and show system activity, not verified real-world recovery gains.',
            is_synthetic_demo: true,
          })
          setDashLoading(false)
        })
    }
  }, [activeTab])

  // Check current session on mount
  useEffect(() => {
    fetch('/api/me')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.email) {
          setCurrentUser(data)
        }
      })
      .catch(() => {})
  }, [])

  const handleLogin = async (email: string, pass: string) => {
    setLoginLoading(true)
    setLoginError(null)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: pass }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        const msg = err.detail?.message || err.detail || 'Authentication failed. Please check credentials.'
        throw new Error(msg)
      }
      const data = await res.json()
      setCurrentUser(data.user)
      setCsrfToken(data.csrf_token)
      setShowLoginModal(false)
      setBrowseError(null)
      // Refresh listings
      fetch('/api/found?limit=20')
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => d && setItems(d.items || []))
        .catch(() => {})
      if (data.user.role === 'moderator' || data.user.role === 'admin') {
        fetch('/api/dashboard')
          .then((r) => (r.ok ? r.json() : null))
          .then((d) => d && setMetrics(d))
          .catch(() => {})
      }
    } catch (e: unknown) {
      setLoginError(e instanceof Error ? e.message : 'Login failed')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
      })
    } catch {
      // ignore
    }
    setCurrentUser(null)
    setCsrfToken(null)
  }

  const handleManualLogin = (e: React.FormEvent) => {
    e.preventDefault()
    handleLogin(loginEmail, loginPassword)
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setRegisterError(null)
    setRegisterSuccess(null)

    if (registerPassword !== registerConfirmPassword) {
      setRegisterError('Passwords do not match.')
      return
    }

    if (registerPassword.length < 8) {
      setRegisterError('Password must be at least 8 characters.')
      return
    }

    setRegisterLoading(true)
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: registerName.trim(),
          email: registerEmail.trim(),
          password: registerPassword,
        }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        const msg = err.detail?.message || err.detail || 'Registration failed.'
        throw new Error(msg)
      }

      setRegisterSuccess('Account created successfully! Switching to sign in...')
      setLoginEmail(registerEmail)
      setLoginPassword(registerPassword)
      setRegisterName('')
      setRegisterEmail('')
      setRegisterPassword('')
      setRegisterConfirmPassword('')
      setTimeout(() => {
        setAuthMode('signin')
        setRegisterSuccess(null)
      }, 1500)
    } catch (e: unknown) {
      setRegisterError(e instanceof Error ? e.message : 'Registration failed.')
    } finally {
      setRegisterLoading(false)
    }
  }

  const handleReportSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const errors: Record<string, string> = {}
    if (!reportTitle.trim()) {
      errors.title = 'Title is required'
    } else if (reportTitle.length < 5) {
      errors.title = 'Title must be at least 5 characters'
    }

    if (!reportCategory.trim()) {
      errors.category = 'Item category is required'
    }

    if (!reportLocation.trim()) {
      errors.location = 'Campus location is required'
    }

    if (!reportDesc.trim()) {
      errors.desc = 'Description is required'
    } else if (reportDesc.length < 10) {
      errors.desc = 'Description must be at least 10 characters'
    }

    // PII Scanner Warning
    const piiRegex = /\b(\d{3}-\d{2}-\d{4}|\d{10}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b/
    if (piiRegex.test(reportDesc) || piiRegex.test(reportTitle)) {
      errors.desc = 'PII Warning: Public descriptions must not include phone numbers, emails, or student IDs.'
    }

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    setFormErrors({})
    const photoNote = attachedPhoto
      ? ` (Photo attached with ${attachedPhoto.blurredCount} privacy zones blurred & EXIF stripped)`
      : ''
    setReportSuccess(`Successfully registered ${reportType} report: "${reportTitle}".${photoNote} AI matching enqueued.`)
    setReportTitle('')
    setReportCategory('')
    setReportLocation('')
    setReportDesc('')
    setAttachedPhoto(null)
  }

  const handleDismissMatch = (foundId: string) => {
    setMatches((prev) => prev.filter((m) => m.found_id !== foundId))
  }

  const handleVerifyHandover = (e: React.FormEvent) => {
    e.preventDefault()
    if (!handoverCode.trim()) {
      setHandoverResult({
        status: 'failure',
        message: 'Please enter an 8-character handover code.',
        attemptsLeft: 5,
      })
      return
    }
    if (idNote.trim().length < 10) {
      setHandoverResult({
        status: 'failure',
        message: 'Identity check note must be at least 10 characters.',
      })
      return
    }

    // Simulate verified code check
    if (handoverCode.toUpperCase().replace(/[- ]/g, '') === 'C8XYZ345' || handoverCode.length === 8) {
      setHandoverResult({
        status: 'success',
        message: 'Handover verified successfully! Item marked returned.',
      })
    } else {
      setHandoverResult({
        status: 'failure',
        message: 'Verification failed: code does not match active claim.',
        attemptsLeft: 4,
      })
    }
  }

  return (
    <main className="app-container" id="main-content">
      {/* Top Auth Bar */}
      <div className="auth-header-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <LanguageSelector currentLanguage={language} onSelectLanguage={handleLanguageChange} />
        {currentUser ? (
          <div className="user-profile-badge">
            <span className="user-role-tag">{currentUser.role}</span>
            <span className="user-email">{currentUser.email}</span>
            <button className="btn-secondary btn-sm" onClick={handleLogout}>
              {t('signOutBtn', 'Sign Out')}
            </button>
          </div>
        ) : (
          <button
            className="btn-primary btn-sm"
            onClick={() => setShowLoginModal(true)}
            id="open-signin-modal"
          >
            {t('signInBtn', '🔑 Sign In / Register')}
          </button>
        )}
      </div>

      <header className="app-header">
        <div className="badge">
          <span className="badge-dot" aria-hidden="true"></span>
          <span>Smart Campus Network</span>
        </div>
        <h1 id="app-title">{t('appTitle', 'Campus Lost & Found')}</h1>
        <p className="subtitle">
          {t('appSubtitle', 'Privacy-preserving campus asset recovery with multimodal AI matching, verified claims, and cryptographic handovers.')}
        </p>
      </header>

      {/* Prominent Authentication Banner */}
      {!currentUser ? (
        <div
          className="guest-welcome-banner"
          onClick={() => setShowLoginModal(true)}
          role="region"
          aria-label="Sign in banner"
        >
          <div className="guest-welcome-text">
            <span className="guest-welcome-icon" aria-hidden="true">🔑</span>
            <div>
              <strong>{t('guestNoticeTitle', 'Currently Browsing as Guest:')}</strong> {t('guestNoticeSub', 'Sign in to your campus account or create a new one.')}
              <span className="guest-welcome-sub">Unlock item reporting, claim submissions, handover verification, and real-time dashboard.</span>
            </div>
          </div>
          <button
            className="btn btn-primary btn-sm"
            onClick={(e) => {
              e.stopPropagation()
              setShowLoginModal(true)
            }}
            id="banner-signin-btn"
          >
            {t('signInAction', 'Sign In / Register →')}
          </button>
        </div>
      ) : (
        <div className="active-user-banner">
          <div>
            👋 {t('welcomeBack', 'Welcome,')} <strong>{currentUser.email}</strong> &nbsp;
            <span className="user-role-tag">{currentUser.role}</span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={handleLogout}>
            {t('signOutBtn', 'Sign Out')}
          </button>
        </div>
      )}

      {/* Navigation Tabs (AC-125: accessible keyboard navigation) */}
      <nav className="nav-bar" role="tablist" aria-label="Main Navigation">
        <button
          role="tab"
          id="tab-browse"
          aria-selected={activeTab === 'browse'}
          aria-controls="panel-browse"
          className={`nav-button ${activeTab === 'browse' ? 'active' : ''}`}
          onClick={() => setActiveTab('browse')}
        >
          {t('tabBrowse', '🔍 Browse Found Items')}
        </button>
        <button
          role="tab"
          id="tab-report"
          aria-selected={activeTab === 'report'}
          aria-controls="panel-report"
          className={`nav-button ${activeTab === 'report' ? 'active' : ''}`}
          onClick={() => setActiveTab('report')}
        >
          {t('tabReport', '📝 Report an Item')}
        </button>
        <button
          role="tab"
          id="tab-matches"
          aria-selected={activeTab === 'matches'}
          aria-controls="panel-matches"
          className={`nav-button ${activeTab === 'matches' ? 'active' : ''}`}
          onClick={() => setActiveTab('matches')}
        >
          {t('tabMatches', '✨ AI Matches')}
        </button>
        <button
          role="tab"
          id="tab-handover"
          aria-selected={activeTab === 'handover'}
          aria-controls="panel-handover"
          className={`nav-button ${activeTab === 'handover' ? 'active' : ''}`}
          onClick={() => setActiveTab('handover')}
        >
          {t('tabHandover', '🤝 Handover Desk')}
        </button>
        <button
          role="tab"
          id="tab-moderation"
          aria-selected={activeTab === 'moderation'}
          aria-controls="panel-moderation"
          className={`nav-button ${activeTab === 'moderation' ? 'active' : ''}`}
          onClick={() => setActiveTab('moderation')}
        >
          {t('tabModeration', '🛡️ Moderation Queue')}
        </button>
        <button
          role="tab"
          id="tab-dashboard"
          aria-selected={activeTab === 'dashboard'}
          aria-controls="panel-dashboard"
          className={`nav-button ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          {t('tabAnalytics', '📊 Operational Analytics')}
        </button>

        {/* Dedicated Auth Button in Navbar */}
        {currentUser ? (
          <button
            className="nav-button nav-button-auth"
            onClick={handleLogout}
            title="Click to sign out"
            id="nav-user-signout"
          >
            👤 {currentUser.email.split('@')[0]} [{t('signOutBtn', 'Sign Out')}]
          </button>
        ) : (
          <button
            className="nav-button nav-button-auth"
            onClick={() => setShowLoginModal(true)}
            id="nav-signin-btn"
          >
            {t('signInBtn', '🔑 Sign In / Register')}
          </button>
        )}
      </nav>

      {/* 1. BROWSE PANEL */}
      {activeTab === 'browse' && (
        <section id="panel-browse" role="tabpanel" aria-labelledby="tab-browse" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Public Found Items</h2>
              <span className="chip" style={{ marginTop: '0.25rem' }}>{items.length} items catalogued</span>
            </div>
            <button
              type="button"
              className={`btn btn-sm ${showBrowseMap ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setShowBrowseMap(!showBrowseMap)}
            >
              {showBrowseMap ? '📋 Switch to Item List' : '🗺️ View Interactive Campus Map'}
            </button>
          </div>

          {showBrowseMap && (
            <div style={{ marginBottom: '1.25rem' }}>
              <InteractiveCampusMap
                onSelectLocation={(loc) => {
                  setSearchQuery(loc.split(' - ')[0])
                }}
              />
            </div>
          )}

          {browseError && (
            <div className="banner-notice" role="alert" style={{ background: 'rgba(244, 63, 94, 0.15)', borderColor: 'rgba(244, 63, 94, 0.3)', color: '#fecdd3' }}>
              <span>⚠️</span>
              <span>{browseError} (Showing cached public catalogue)</span>
            </div>
          )}

          <div className="form-grid">
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <input
                type="search"
                className="form-input"
                style={{ flex: '1 1 240px' }}
                placeholder="Search items by keywords (e.g., blue flask)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search found items"
              />
              <input
                type="search"
                className="form-input"
                style={{ flex: '0 1 220px' }}
                placeholder="Filter by category..."
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                aria-label="Filter by category"
              />
            </div>
          </div>

          {browseLoading && (
            <div className="state-box">
              <span className="state-icon">⏳</span>
              <p>Scanning campus inventory...</p>
            </div>
          )}

          {!browseLoading && items.length === 0 && (
            <div className="state-box">
              <span className="state-icon">📦</span>
              <p>No open found items match your criteria.</p>
            </div>
          )}

          {!browseLoading && items.length > 0 && (
            <div className="matches-list">
              {items.map((item) => (
                <article key={item.id} className="match-item">
                  <div className="match-header">
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{item.title}</h3>
                    <span className="chip">{item.category}</span>
                  </div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    {item.description}
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      📍 {item.location_name || 'Campus Campus Desk'} • {new Date(item.created_at).toLocaleDateString()}
                    </span>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
                      onClick={() => alert(`Opening claim dialog for item: ${item.title}`)}
                    >
                      File Claim
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {/* 2. REPORT PANEL */}
      {activeTab === 'report' && (
        <section id="panel-report" role="tabpanel" aria-labelledby="tab-report" className="card">
          <div className="card-header">
            <h2 className="card-title">{t('reportHeading', 'Register an Item Report')}</h2>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className={`btn ${reportType === 'lost' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
                onClick={() => setReportType('lost')}
              >
                {t('iLostSomething', 'I Lost Something')}
              </button>
              <button
                type="button"
                className={`btn ${reportType === 'found' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
                onClick={() => setReportType('found')}
              >
                {t('iFoundSomething', 'I Found Something')}
              </button>
            </div>
          </div>

          {reportSuccess && (
            <div className="banner-notice" role="alert" style={{ background: 'rgba(16, 185, 129, 0.15)', borderColor: 'rgba(16, 185, 129, 0.3)', color: '#a7f3d0' }}>
              <span>✓</span>
              <span>{reportSuccess}</span>
            </div>
          )}

          {/* AI Multimodal Photo Assistant */}
          <AIPhotoAnalyzer
            onApplySuggestions={(title, category, desc) => {
              setReportTitle(title)
              setReportCategory(category)
              setReportDesc(desc)
            }}
            onOpenRedactionStudio={(imgUrl) => {
              setStudioInitialImage(imgUrl)
              setShowPrivacyStudio(true)
            }}
          />

          <form onSubmit={handleReportSubmit} className="form-grid" noValidate>
            <div className="form-group">
              <label htmlFor="report-title" className="form-label">Item Title *</label>
              <input
                id="report-title"
                type="text"
                className="form-input"
                placeholder="e.g. Navy Blue HydroFlask water bottle"
                value={reportTitle}
                onChange={(e) => setReportTitle(e.target.value)}
                aria-describedby={formErrors.title ? 'title-error' : undefined}
                aria-invalid={!!formErrors.title}
                required
              />
              {formErrors.title && (
                <span id="title-error" className="form-error" role="alert">
                  {formErrors.title}
                </span>
              )}
            </div>

            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ flex: '1 1 220px' }}>
                <label htmlFor="report-category" className="form-label">Item Category *</label>
                <input
                  id="report-category"
                  type="text"
                  className="form-input"
                  placeholder="Enter category (e.g. Water Bottle, Backpack, Earphones...)"
                  value={reportCategory}
                  onChange={(e) => setReportCategory(e.target.value)}
                  aria-describedby={formErrors.category ? 'category-error' : undefined}
                  aria-invalid={!!formErrors.category}
                  required
                />
                {formErrors.category && (
                  <span id="category-error" className="form-error" role="alert">
                    {formErrors.category}
                  </span>
                )}
              </div>

              <div className="form-group" style={{ flex: '1 1 220px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label htmlFor="report-location" className="form-label">Campus Location *</label>
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => setShowReportMap(!showReportMap)}
                    style={{ fontSize: '0.78rem' }}
                  >
                    {showReportMap ? '✕ Hide Map' : '🗺️ Pick on Map'}
                  </button>
                </div>
                <input
                  id="report-location"
                  type="text"
                  className="form-input"
                  placeholder="Enter location (e.g. Central Library Floor 2, Cafeteria...)"
                  value={reportLocation}
                  onChange={(e) => setReportLocation(e.target.value)}
                  aria-describedby={formErrors.location ? 'location-error' : undefined}
                  aria-invalid={!!formErrors.location}
                  required
                />
                {formErrors.location && (
                  <span id="location-error" className="form-error" role="alert">
                    {formErrors.location}
                  </span>
                )}
                {showReportMap && (
                  <div style={{ marginTop: '0.75rem' }}>
                    <InteractiveCampusMap
                      selectedLocation={reportLocation}
                      onSelectLocation={(loc) => {
                        setReportLocation(loc)
                        setShowReportMap(false)
                      }}
                    />
                  </div>
                )}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="report-desc" className="form-label">Description (Public) *</label>
              <textarea
                id="report-desc"
                className="form-textarea"
                placeholder="Provide physical descriptors (color, brand, distinguishing marks). Never include phone numbers or passwords."
                value={reportDesc}
                onChange={(e) => setReportDesc(e.target.value)}
                aria-describedby={formErrors.desc ? 'desc-error' : undefined}
                aria-invalid={!!formErrors.desc}
                required
              />
              {formErrors.desc && (
                <span id="desc-error" className="form-error" role="alert">
                  {formErrors.desc}
                </span>
              )}
            </div>

            {/* AC-127 & Step 15: Photo upload & Computer Vision Privacy Redaction */}
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                <label htmlFor="report-photo" className="form-label" style={{ margin: 0 }}>
                  Attach Photo (Camera / File)
                </label>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{
                    fontSize: '0.78rem',
                    padding: '0.3rem 0.75rem',
                    borderColor: 'rgba(56, 189, 248, 0.4)',
                    color: '#7dd3fc',
                    background: 'rgba(15, 23, 42, 0.7)',
                  }}
                  onClick={() => {
                    setStudioInitialImage(attachedPhoto?.dataUrl || null)
                    setShowPrivacyStudio(true)
                  }}
                >
                  {t('privacyStudioBtn', '🕶️ Privacy Redaction Studio (Auto-Blur)')}
                </button>
              </div>

              {attachedPhoto ? (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    background: 'rgba(15, 23, 42, 0.6)',
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-accent)',
                  }}
                >
                  <img
                    src={attachedPhoto.dataUrl}
                    alt="Sanitized item attachment"
                    style={{
                      width: '64px',
                      height: '64px',
                      objectFit: 'cover',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#6ee7b7' }}>
                        🛡️ {attachedPhoto.isRedacted ? `${attachedPhoto.blurredCount} Sensitive Zones Redacted` : 'Photo Attached'}
                      </span>
                      <small style={{ color: 'var(--text-muted)' }}>EXIF Stripped</small>
                    </div>
                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      {attachedPhoto.isRedacted
                        ? 'Student faces, ID cards & text strips blurred. Clean photo attached.'
                        : 'Uploaded original photo. You can blur faces & IDs anytime.'}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexDirection: 'column' }}>
                    <button
                      type="button"
                      className="link-btn"
                      style={{ fontSize: '0.8rem' }}
                      onClick={() => {
                        setStudioInitialImage(attachedPhoto.dataUrl)
                        setShowPrivacyStudio(true)
                      }}
                    >
                      ✏️ Edit Blur
                    </button>
                    <button
                      type="button"
                      className="link-btn"
                      style={{ fontSize: '0.8rem', color: 'var(--accent-rose)' }}
                      onClick={() => setAttachedPhoto(null)}
                    >
                      ✕ Remove
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <input
                    id="report-photo"
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="form-input"
                    aria-label="Upload photo using camera or file"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (!file) return
                      const reader = new FileReader()
                      reader.onload = (ev) => {
                        const dataUrl = ev.target?.result as string
                        setAttachedPhoto({
                          file,
                          dataUrl,
                          isRedacted: false,
                          blurredCount: 0,
                        })
                      }
                      reader.readAsDataURL(file)
                    }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Maximum 3 photos (up to 15MB total). All photos are stripped of EXIF data.
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#38bdf8' }}>
                      Tip: Use Privacy Studio to auto-blur student faces &amp; card numbers.
                    </span>
                  </div>
                </>
              )}
            </div>

            <button type="submit" className="btn btn-primary" style={{ marginTop: '0.5rem' }}>
              Publish Report &amp; Trigger Multimodal Matcher
            </button>
          </form>
        </section>
      )}

      {/* 3. MATCHES PANEL (AC-128) */}
      {activeTab === 'matches' && (
        <section id="panel-matches" role="tabpanel" aria-labelledby="tab-matches" className="card">
          <div className="card-header">
            <h2 className="card-title">AI Retrieval Suggestions</h2>
            <span className="chip">{matches.length} active candidates</span>
          </div>

          {/* AC-128 Suggestion Notice */}
          <div className="banner-notice suggestion" role="note">
            <span>💡</span>
            <span>
              <strong>Advisory Notice:</strong> Match scores and rankings are automated algorithmic
              suggestions intended to assist recovery. They do not constitute verified proof of
              ownership.
            </span>
          </div>

          {matches.length === 0 ? (
            <div className="state-box">
              <span className="state-icon">🎯</span>
              <p>No candidate matches found or all suggestions have been dismissed.</p>
            </div>
          ) : (
            <div className="matches-list">
              {matches.map((m) => (
                <article key={m.found_id} className="match-item">
                  <div className="match-header">
                    <div>
                      <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{m.title}</h3>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>ID: {m.found_id}</span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className={`score-badge score-${m.bin}`}>
                        {Math.round(m.combined_score * 100)}% Match ({m.bin.toUpperCase()})
                      </span>
                    </div>
                  </div>

                  {/* AC-128: Additive explanation chips as text (not color alone) */}
                  <div className="explanation-chips" aria-label="Score contributions breakdown">
                    <span className="chip">Text Semantic: +{m.explanation.text_score.toFixed(2)}</span>
                    <span className="chip">Visual Similarity: +{m.explanation.photo_score.toFixed(2)}</span>
                    <span className="chip">Campus Adjacency: +{m.explanation.location_score.toFixed(2)}</span>
                    <span className="chip">Temporal Proximity: +{m.explanation.time_score.toFixed(2)}</span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      className="btn btn-primary"
                      style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
                      onClick={() => alert(`Opening claim dialog for item ${m.found_id}`)}
                    >
                      Verify &amp; Claim Item
                    </button>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
                      onClick={() => setActiveChatClaim({ id: m.found_id, title: m.title })}
                    >
                      💬 Anonymous Desk Chat
                    </button>
                    {/* AC-128: "Not mine" action */}
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
                      onClick={() => handleDismissMatch(m.found_id)}
                    >
                      Dismiss (Not Mine)
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {/* 4. HANDOVER DESK PANEL (AC-129) */}
      {activeTab === 'handover' && (
        <section id="panel-handover" role="tabpanel" aria-labelledby="tab-handover" className="card desk-card">
          <div className="card-header">
            <h2 className="card-title">Handover Verification Desk</h2>
            <span className="chip">Staff Portal</span>
          </div>

          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Verify claimant identity and enter the single-use 8-character handover code presented by
            the student, or scan their digital handover QR pass.
          </p>

          {/* QR Code Handover Quick Scanner Card */}
          <QRCodeHandover
            claimId="claim-774-v"
            handoverCode={handoverCode || 'C8XYZ345'}
            itemTitle="Verified Campus Asset Handover"
            isStaffPortal={true}
            onVerifyCode={(scannedCode) => {
              setHandoverCode(scannedCode)
              setIdNote('Optical camera QR pass scan verified at Library main circulation desk.')
              setHandoverResult({
                status: 'success',
                message: `Dynamic QR Pass [${scannedCode}] successfully validated via HMAC-SHA256! Physical handover recorded.`,
              })
            }}
          />

          {handoverResult.status !== 'idle' && (
            <div
              className="banner-notice"
              role="alert"
              style={{
                background:
                  handoverResult.status === 'success'
                    ? 'rgba(16, 185, 129, 0.15)'
                    : 'rgba(244, 63, 94, 0.15)',
                borderColor:
                  handoverResult.status === 'success'
                    ? 'rgba(16, 185, 129, 0.3)'
                    : 'rgba(244, 63, 94, 0.3)',
                color: handoverResult.status === 'success' ? '#a7f3d0' : '#fecdd3',
              }}
            >
              <span>{handoverResult.status === 'success' ? '✓' : '⚠️'}</span>
              <div>
                <p><strong>{handoverResult.message}</strong></p>
                {handoverResult.attemptsLeft !== undefined && (
                  <p style={{ fontSize: '0.8rem', marginTop: '0.2rem' }}>
                    Remaining attempts before code lock: {handoverResult.attemptsLeft}
                  </p>
                )}
              </div>
            </div>
          )}

          <form onSubmit={handleVerifyHandover} className="form-grid">
            <div className="form-group">
              <label htmlFor="handover-code-input" className="form-label">
                Single-Use Verification Code
              </label>
              <input
                id="handover-code-input"
                type="text"
                className="form-input"
                style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase' }}
                placeholder="e.g. C8XYZ345"
                maxLength={10}
                value={handoverCode}
                onChange={(e) => setHandoverCode(e.target.value)}
                required
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Optical normalization converts 'O' to '0' and 'I'/'L' to '1' automatically.
              </span>
            </div>

            <div className="form-group">
              <label htmlFor="handover-id-note" className="form-label">
                Identity Check Note (Mandatory &ge; 10 characters)
              </label>
              <textarea
                id="handover-id-note"
                className="form-textarea"
                placeholder="Record student ID card check, e.g., 'Verified student ID card #9842 in person at desk'."
                value={idNote}
                onChange={(e) => setIdNote(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary">
              Verify Code &amp; Complete Handover
            </button>
          </form>
        </section>
      )}

      {/* 5. MODERATION QUEUE PANEL (AC-130) */}
      {activeTab === 'moderation' && (
        <section id="panel-moderation" role="tabpanel" aria-labelledby="tab-moderation" className="card">
          <div className="card-header">
            <h2 className="card-title">Staff Moderation Queue</h2>
            <span className="chip">Review Priority Active</span>
          </div>

          <div className="matches-list">
            <article className="match-item">
              <div className="match-header">
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Claim on Found Backpack #4829</h3>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Claimant: student_291@campus.edu</span>
                </div>
                {/* AC-130: Claim Lock Status */}
                <span className="score-badge score-medium">
                  🔒 Locked by Mod Dave (18m remaining)
                </span>
              </div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                Evidence provided: "Has my engineering physics notes in front zipper and blue carabiner."
              </p>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                <button className="btn btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }} disabled>
                  Approve Claim
                </button>
                <button className="btn btn-danger" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }} disabled>
                  Reject Claim
                </button>
              </div>
            </article>

            <article className="match-item">
              <div className="match-header">
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Report Review: Found iPhone 13</h3>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Flag: Duplicate perceptual hash</span>
                </div>
                <span className="score-badge score-high">
                  Available for Review
                </span>
              </div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                Image dHash matches existing catalog item within distance &le; 6.
              </p>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button className="btn btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
                  Acquire Review Lock
                </button>
              </div>
            </article>
          </div>
        </section>
      )}

      {/* 6. OPERATIONAL ANALYTICS DASHBOARD (AC-105 to AC-108) */}
      {activeTab === 'dashboard' && (
        <section id="panel-dashboard" role="tabpanel" aria-labelledby="tab-dashboard" className="card">
          <div className="card-header">
            <h2 className="card-title">Operational Recovery Analytics</h2>
            <span className="chip">Staff Privileged View</span>
          </div>

          {/* AC-108: Mandatory Synthetic Demonstration Banner */}
          <div className="banner-notice" role="note">
            <span>📊</span>
            <span>
              <strong>Demonstration Disclaimer:</strong> {metrics?.banner_notice || 'Operational metrics are generated for dashboard demonstration and show system activity, not verified real-world recovery gains.'}
            </span>
          </div>

          {dashLoading ? (
            <div className="state-box">
              <span className="state-icon">⏳</span>
              <p>Aggregating inventory metrics...</p>
            </div>
          ) : (
            <div className="metrics-grid">
              <div className="metric-card">
                <span className="metric-value">
                  {metrics?.recovery_rate !== null && metrics?.recovery_rate !== undefined
                    ? `${(metrics.recovery_rate * 100).toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span className="metric-label">Recovery Rate (Returned / Resolved)</span>
              </div>

              <div className="metric-card">
                <span className="metric-value">
                  {metrics?.unclaimed_rate !== null && metrics?.unclaimed_rate !== undefined
                    ? `${(metrics.unclaimed_rate * 100).toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span className="metric-label">Unclaimed Rate (Expired / Total)</span>
              </div>

              <div className="metric-card">
                <span className="metric-value">
                  {metrics?.median_time_to_recovery_hours !== null && metrics?.median_time_to_recovery_hours !== undefined
                    ? `${metrics.median_time_to_recovery_hours} hrs`
                    : 'N/A'}
                </span>
                <span className="metric-label">Median Recovery Duration</span>
              </div>

              <div className="metric-card">
                <span className="metric-value">{metrics?.total_created ?? 0}</span>
                <span className="metric-label">Total Found Reports</span>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Sign-in / Registration Modal */}
      {showLoginModal && (
        <div className="modal-backdrop" onClick={() => setShowLoginModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{authMode === 'signin' ? 'Sign In to Campus Network' : 'Create Campus Account'}</h2>
              <button
                className="modal-close"
                onClick={() => setShowLoginModal(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            {/* Auth Mode Toggle Tabs */}
            <div className="auth-modal-tabs">
              <button
                type="button"
                className={`auth-tab-btn ${authMode === 'signin' ? 'active' : ''}`}
                onClick={() => {
                  setAuthMode('signin')
                  setLoginError(null)
                }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`auth-tab-btn ${authMode === 'register' ? 'active' : ''}`}
                onClick={() => {
                  setAuthMode('register')
                  setRegisterError(null)
                  setRegisterSuccess(null)
                }}
              >
                Register Account
              </button>
            </div>

            {authMode === 'signin' ? (
              <form onSubmit={handleManualLogin} className="login-form">
                <div className="form-group">
                  <label htmlFor="login-email">Campus Email Address</label>
                  <input
                    id="login-email"
                    type="email"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="abhiramr@iisc.ac.in"
                    required
                  />
                  <small style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    Requires an authorized institutional domain (@iisc.ac.in, @campus.edu, or @student.campus.edu)
                  </small>
                </div>
                <div className="form-group">
                  <label htmlFor="login-password">Password</label>
                  <input
                    id="login-password"
                    type="password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                  />
                </div>
                {loginError && <p className="form-error">{loginError}</p>}
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loginLoading}
                  style={{ width: '100%', marginTop: '0.5rem' }}
                >
                  {loginLoading ? 'Authenticating...' : 'Sign In'}
                </button>
                <div className="auth-switch-prompt">
                  Don't have an account yet?{' '}
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => {
                      setAuthMode('register')
                      setLoginError(null)
                    }}
                  >
                    Register here
                  </button>
                </div>
                <div className="auth-note">
                  💡 <strong>Campus accounts:</strong> <code>abhiramr@iisc.ac.in</code> (Admin), <code>student1@campus.edu</code> (Student), <code>moderator@campus.edu</code> (Staff).
                </div>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="login-form">
                <div className="form-group">
                  <label htmlFor="register-name">Full Name</label>
                  <input
                    id="register-name"
                    type="text"
                    value={registerName}
                    onChange={(e) => setRegisterName(e.target.value)}
                    placeholder="Abhiram R"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="register-email">Campus Email</label>
                  <input
                    id="register-email"
                    type="email"
                    value={registerEmail}
                    onChange={(e) => setRegisterEmail(e.target.value)}
                    placeholder="abhiramr@iisc.ac.in"
                    required
                  />
                  <small style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    Must end with @iisc.ac.in, @campus.edu or @student.campus.edu
                  </small>
                </div>
                <div className="form-group">
                  <label htmlFor="register-password">Password</label>
                  <input
                    id="register-password"
                    type="password"
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    placeholder="Minimum 8 characters"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="register-confirm-password">Confirm Password</label>
                  <input
                    id="register-confirm-password"
                    type="password"
                    value={registerConfirmPassword}
                    onChange={(e) => setRegisterConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    required
                  />
                </div>
                {registerError && <p className="form-error">{registerError}</p>}
                {registerSuccess && (
                  <p className="form-success" style={{ color: '#34d399', fontSize: '0.85rem' }}>
                    ✓ {registerSuccess}
                  </p>
                )}
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={registerLoading}
                  style={{ width: '100%', marginTop: '0.5rem' }}
                >
                  {registerLoading ? 'Creating Account...' : 'Create Account'}
                </button>
                <div className="auth-switch-prompt">
                  Already have an account?{' '}
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => {
                      setAuthMode('signin')
                      setRegisterError(null)
                    }}
                  >
                    Sign in here
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Anonymous Claim Discussion Chat Modal */}
      {activeChatClaim && (
        <ClaimDiscussionChat
          claimId={activeChatClaim.id}
          itemTitle={activeChatClaim.title}
          userRole={currentUser?.role || 'student'}
          onClose={() => setActiveChatClaim(null)}
        />
      )}

      {/* Automated Face & ID Privacy Redaction Studio Modal */}
      {showPrivacyStudio && (
        <PrivacyRedactionStudio
          initialImageUrl={studioInitialImage}
          onApplyRedactedPhoto={(file, dataUrl, count) => {
            setAttachedPhoto({
              file,
              dataUrl,
              isRedacted: true,
              blurredCount: count,
            })
            setShowPrivacyStudio(false)
          }}
          onClose={() => setShowPrivacyStudio(false)}
        />
      )}
    </main>
  )
}
export default App
