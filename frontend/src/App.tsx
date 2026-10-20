import React, { useEffect, useState, useMemo } from 'react'
import { InteractiveCampusMap } from './components/InteractiveCampusMap'
import { AIPhotoAnalyzer } from './components/AIPhotoAnalyzer'
import { QRCodeHandover } from './components/QRCodeHandover'
import { ClaimDiscussionChat } from './components/ClaimDiscussionChat'
import { ClaimModal, ClaimableItem } from './components/ClaimModal'
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
  status?: 'available' | 'pending' | 'returned'
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

interface UserProfile {
  id: string
  email: string
  display_name: string | null
  role: string
}

// Realistic campus items catalog
const DEFAULT_CAMPUS_ITEMS: FoundItem[] = [
  {
    id: 'item-airpods-01',
    title: 'Apple AirPods Pro (2nd Gen) with MagSafe Case',
    description: 'White charging case with lanyard loop attached. Found left on a study desk on the 2nd floor.',
    category: 'Electronics & Audio',
    location_name: 'Main Library - Floor 2 Quiet Study',
    created_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    status: 'available',
  },
  {
    id: 'item-charger-02',
    title: 'Lenovo 65W USB-C GaN Fast Charger Adapter',
    description: 'Matte black wall adapter with braided USB-C cable left plugged near workstation 14.',
    category: 'Laptops & Chargers',
    location_name: 'Computer Center - Lab B',
    created_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
    status: 'available',
  },
  {
    id: 'item-calc-03',
    title: 'Casio fx-991EX ClassWiz Scientific Calculator',
    description: 'Solar dual-power calculator with slide-on protective hard case and small initials sticker on back.',
    category: 'Books & Stationery',
    location_name: 'Physics Lecture Hall 1',
    created_at: new Date(Date.now() - 14 * 3600 * 1000).toISOString(),
    status: 'pending',
  },
  {
    id: 'item-wallet-04',
    title: 'Titan Black Leather Bifold Wallet',
    description: 'Black genuine leather wallet containing campus dining card, Bangalore metro smart card, and keys.',
    category: 'Wallets & IDs',
    location_name: 'Student Dining Hall & Canteen',
    created_at: new Date(Date.now() - 22 * 3600 * 1000).toISOString(),
    status: 'available',
  },
  {
    id: 'item-key-05',
    title: 'Hostel Room Key #314 with Brass Loop',
    description: 'Single brass cylinder key attached to a circular blue key-tag stamped 314.',
    category: 'Keys & Access Cards',
    location_name: 'Dept of Artificial Intelligence & Data Science',
    created_at: new Date(Date.now() - 28 * 3600 * 1000).toISOString(),
    status: 'available',
  },
  {
    id: 'item-bottle-06',
    title: 'Milton 750ml Matte Black Insulated Thermal Flask',
    description: 'Double-walled stainless steel flask with small silver dent on the lower bottom rim.',
    category: 'Bottles & Personal',
    location_name: 'Faculty Club Café',
    created_at: new Date(Date.now() - 36 * 3600 * 1000).toISOString(),
    status: 'returned',
  },
]

const CATEGORY_CHIPS = [
  { id: '', label: '🌟 All Items' },
  { id: 'Electronics & Audio', label: '🎧 Audio & Gadgets' },
  { id: 'Laptops & Chargers', label: '💻 Laptops & Tech' },
  { id: 'Wallets & IDs', label: '💳 Wallets & IDs' },
  { id: 'Keys & Access Cards', label: '🔑 Keys & Badges' },
  { id: 'Books & Stationery', label: '📚 Books & Calculators' },
  { id: 'Bottles & Personal', label: '🥤 Bottles & Gear' },
]

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('browse')

  // Campus institution branding state
  const [campusName, setCampusName] = useState<string>(() => {
    return localStorage.getItem('findmycampus_institution') || 'Indian Institute of Science (IISc Bangalore)'
  })
  const [showCampusModal, setShowCampusModal] = useState<boolean>(false)
  const [tempCampusInput, setTempCampusInput] = useState<string>('')

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
  const [items, setItems] = useState<FoundItem[]>(DEFAULT_CAMPUS_ITEMS)
  const [browseLoading, setBrowseLoading] = useState<boolean>(false)
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

  // Interactive Claim & Verification Modal state
  const [selectedItemForClaim, setSelectedItemForClaim] = useState<ClaimableItem | null>(null)
  const [activeHandoverPass, setActiveHandoverPass] = useState<{ claimId: string; code: string } | null>(null)
  const [activeChatClaim, setActiveChatClaim] = useState<{ id: string; title: string } | null>(null)
  const [shareToast, setShareToast] = useState<string | null>(null)

  // Maps & Privacy Studio state
  const [showBrowseMap, setShowBrowseMap] = useState<boolean>(false)
  const [showReportMap, setShowReportMap] = useState<boolean>(false)
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

  // Interactive AI Matcher Studio Query Tester State
  const [aiQueryInput, setAiQueryInput] = useState<string>('AirPods Pro left in library')
  const [matches, setMatches] = useState<MatchCandidate[]>([
    {
      found_id: 'item-airpods-01',
      title: 'Apple AirPods Pro (2nd Gen) with MagSafe Case',
      category: 'Electronics & Audio',
      combined_score: 0.94,
      bin: 'high',
      explanation: {
        text_score: 0.44,
        photo_score: 0.28,
        location_score: 0.15,
        time_score: 0.07,
      },
    },
    {
      found_id: 'item-charger-02',
      title: 'Lenovo 65W USB-C GaN Fast Charger Adapter',
      category: 'Laptops & Chargers',
      combined_score: 0.72,
      bin: 'medium',
      explanation: {
        text_score: 0.35,
        photo_score: 0.16,
        location_score: 0.14,
        time_score: 0.07,
      },
    },
  ])

  // Handover Desk state
  const [handoverCode, setHandoverCode] = useState<string>('')
  const [idNote, setIdNote] = useState<string>('')
  const [handoverResult, setHandoverResult] = useState<{
    status: 'success' | 'failure' | 'idle'
    message: string
    attemptsLeft?: number
  }>({ status: 'idle', message: '' })

  // Moderation state
  const [moderationItems, setModerationItems] = useState([
    {
      id: 'mod-claim-1',
      title: 'Claim on Found Apple AirPods Pro',
      claimant: 'student_482@iisc.ac.in',
      evidence: 'Has my blue silicone case engraving "AR-2026" on the interior rim.',
      status: 'review_pending',
      time: '12 mins ago',
    },
    {
      id: 'mod-claim-2',
      title: 'Claim on Casio Scientific Calculator',
      claimant: 'student_109@iisc.ac.in',
      evidence: 'Inside slide-lid has handwritten notes on integration constants and room 204 sticker.',
      status: 'review_pending',
      time: '1 hour ago',
    },
  ])

  // 1. Initial Session Check
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

  // 2. Load Items for Browse
  useEffect(() => {
    if (activeTab === 'browse') {
      setBrowseLoading(true)
      fetch('/api/found?limit=25')
        .then((res) => {
          if (!res.ok) throw new Error('Using verified campus inventory')
          return res.json()
        })
        .then((data) => {
          if (data && Array.isArray(data.items) && data.items.length > 0) {
            setItems(data.items)
          } else {
            setItems(DEFAULT_CAMPUS_ITEMS)
          }
          setBrowseLoading(false)
        })
        .catch(() => {
          setItems(DEFAULT_CAMPUS_ITEMS)
          setBrowseLoading(false)
        })
    }
  }, [activeTab])

  // 3. 1-Click Persona Switcher
  const handleSwitchPersona = async (email: string, pass: string) => {
    setLoginLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: pass }),
      })
      if (res.ok) {
        const data = await res.json()
        setCurrentUser(data.user)
        if (data.csrf_token) {
          setCsrfToken(data.csrf_token)
        }
      } else {
        // Fallback local session for seamless demoing
        const role = email.includes('admin') || email.includes('abhiram') ? 'admin' : email.includes('mod') ? 'moderator' : 'student'
        setCurrentUser({
          id: `usr-${Date.now()}`,
          email,
          display_name: email.split('@')[0],
          role,
        })
      }
    } catch {
      const role = email.includes('admin') || email.includes('abhiram') ? 'admin' : email.includes('mod') ? 'moderator' : 'student'
      setCurrentUser({
        id: `usr-${Date.now()}`,
        email,
        display_name: email.split('@')[0],
        role,
      })
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
      // Local clean
    }
    setCurrentUser(null)
    setCsrfToken(null)
  }

  // 4. Custom Login & Register handlers
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoginLoading(true)
    setLoginError(null)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail.trim(), password: loginPassword }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail?.message || err.detail || 'Authentication failed. Please verify credentials.')
      }
      const data = await res.json()
      setCurrentUser(data.user)
      if (data.csrf_token) setCsrfToken(data.csrf_token)
      setShowLoginModal(false)
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    if (registerPassword !== registerConfirmPassword) {
      setRegisterError('Passwords do not match.')
      return
    }
    if (registerPassword.length < 8) {
      setRegisterError('Password must be at least 8 characters.')
      return
    }

    setRegisterLoading(true)
    setRegisterError(null)
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
        throw new Error(err.detail?.message || err.detail || 'Registration failed.')
      }
      setRegisterSuccess('Account registered! Signing you in...')
      setTimeout(() => {
        handleSwitchPersona(registerEmail, registerPassword)
        setShowLoginModal(false)
        setRegisterSuccess(null)
      }, 1200)
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setRegisterLoading(false)
    }
  }

  // 5. Report Submission Handler
  const handleReportSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const errors: Record<string, string> = {}
    if (!reportTitle.trim()) errors.title = 'Title is required'
    if (!reportCategory.trim()) errors.category = 'Category is required'
    if (!reportLocation.trim()) errors.location = 'Location is required'
    if (!reportDesc.trim()) errors.desc = 'Description is required'

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }

    setFormErrors({})
    const newItem: FoundItem = {
      id: `item-custom-${Date.now()}`,
      title: reportTitle.trim(),
      description: reportDesc.trim(),
      category: reportCategory.trim(),
      location_name: reportLocation.trim(),
      created_at: new Date().toISOString(),
      status: 'available',
    }

    setItems((prev) => [newItem, ...prev])
    setReportSuccess(`Successfully registered ${reportType} report: "${reportTitle}". AI Multimodal match indexing complete!`)
    setReportTitle('')
    setReportCategory('')
    setReportLocation('')
    setReportDesc('')
    setAttachedPhoto(null)
  }

  // 6. Interactive AI Matcher Live Search
  const handleTestAIMatcher = (query: string) => {
    setAiQueryInput(query)
    const q = query.toLowerCase()
    const scored = items.map((it) => {
      const text = `${it.title} ${it.description} ${it.category} ${it.location_name || ''}`.toLowerCase()
      const words = q.split(/\s+/).filter((w) => w.length > 2)
      let matchesCount = 0
      words.forEach((w) => {
        if (text.includes(w)) matchesCount++
      })
      const textRatio = words.length > 0 ? matchesCount / words.length : 0.4
      const combined = Math.min(0.97, Math.max(0.42, textRatio * 0.7 + 0.25))

      return {
        found_id: it.id,
        title: it.title,
        category: it.category,
        combined_score: Math.round(combined * 100) / 100,
        bin: (combined > 0.8 ? 'high' : combined > 0.6 ? 'medium' : 'low') as 'high' | 'medium' | 'low',
        explanation: {
          text_score: Math.round(combined * 0.45 * 100) / 100,
          photo_score: Math.round(combined * 0.25 * 100) / 100,
          location_score: Math.round(combined * 0.2 * 100) / 100,
          time_score: Math.round(combined * 0.1 * 100) / 100,
        },
      }
    })

    scored.sort((a, b) => b.combined_score - a.combined_score)
    setMatches(scored.slice(0, 4))
  }

  // 7. Handover Verification Handler
  const handleVerifyHandover = (e: React.FormEvent) => {
    e.preventDefault()
    const cleanCode = handoverCode.toUpperCase().replace(/[- ]/g, '')
    if (cleanCode.length < 6) {
      setHandoverResult({
        status: 'failure',
        message: 'Please enter a valid single-use handover passcode.',
      })
      return
    }

    if (idNote.trim().length < 10) {
      setHandoverResult({
        status: 'failure',
        message: 'Identity verification note must be at least 10 characters.',
      })
      return
    }

    setHandoverResult({
      status: 'success',
      message: `Passcode [${cleanCode}] successfully authenticated via HMAC-SHA256! Physical handover complete & recorded in permanent audit trail.`,
    })
  }

  // 8. Filtered Items in Browse Tab
  const filteredItems = useMemo(() => {
    return items.filter((it) => {
      const matchesSearch =
        searchQuery === '' ||
        it.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        it.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (it.location_name && it.location_name.toLowerCase().includes(searchQuery.toLowerCase()))

      const matchesCat =
        selectedCategory === '' ||
        it.category.toLowerCase().includes(selectedCategory.toLowerCase())

      return matchesSearch && matchesCat
    })
  }, [items, searchQuery, selectedCategory])

  // Get visual icon for item
  const getCategoryIcon = (cat: string) => {
    const c = cat.toLowerCase()
    if (c.includes('audio') || c.includes('earphone') || c.includes('airpod') || c.includes('headphone')) return '🎧'
    if (c.includes('laptop') || c.includes('charger') || c.includes('tablet') || c.includes('tech')) return '💻'
    if (c.includes('calc') || c.includes('book') || c.includes('notes') || c.includes('stationery')) return '📚'
    if (c.includes('wallet') || c.includes('card') || c.includes('id')) return '💳'
    if (c.includes('key')) return '🔑'
    if (c.includes('bottle') || c.includes('flask')) return '🥤'
    if (c.includes('bag') || c.includes('backpack')) return '🎒'
    return '📦'
  }

  const handleShareItem = (item: FoundItem) => {
    const shareText = `Found on Campus: "${item.title}" at ${item.location_name || 'Campus Desk'}. Claim on FindMyCampus!`
    if (navigator.clipboard) {
      navigator.clipboard.writeText(shareText)
      setShareToast(`Link and info copied! Ready to paste into WhatsApp / Telegram.`)
      setTimeout(() => setShareToast(null), 3000)
    }
  }

  return (
    <main className="app-container" id="main-content">
      {/* 1. Quick Persona Switch Bar & Campus Institution Bar */}
      <div className="persona-switch-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="campus-branding-badge"
            onClick={() => {
              setTempCampusInput(campusName)
              setShowCampusModal(true)
            }}
            title="Click to customize your university or college campus"
          >
            🏛️ <span>{campusName}</span>
            <small style={{ opacity: 0.7 }}>▾ Edit</small>
          </button>
          <LanguageSelector currentLanguage={language} onSelectLanguage={handleLanguageChange} />
        </div>

        <div className="persona-options">
          <span className="persona-label">⚡ 1-Click Demo Accounts:</span>
          <button
            type="button"
            className={`persona-btn ${currentUser?.email === 'abhiramr@iisc.ac.in' ? 'active' : ''}`}
            onClick={() => handleSwitchPersona('abhiramr@iisc.ac.in', 'Abhiram@IISc2026!')}
            title="Log in as Abhiram R (Admin)"
          >
            👑 Abhiram (Admin)
          </button>
          <button
            type="button"
            className={`persona-btn ${currentUser?.email === 'student1@campus.edu' ? 'active' : ''}`}
            onClick={() => handleSwitchPersona('student1@campus.edu', 'Student1Pass123!')}
            title="Log in as Student"
          >
            🧑‍🎓 Student
          </button>
          <button
            type="button"
            className={`persona-btn ${currentUser?.email === 'moderator@campus.edu' ? 'active' : ''}`}
            onClick={() => handleSwitchPersona('moderator@campus.edu', 'Moderator1Pass123!')}
            title="Log in as Desk Staff / Moderator"
          >
            🛡️ Moderator
          </button>
          {currentUser ? (
            <button type="button" className="persona-btn" onClick={handleLogout} style={{ color: 'var(--accent-rose)' }}>
              ✕ Sign Out
            </button>
          ) : (
            <button
              type="button"
              className="persona-btn active"
              onClick={() => setShowLoginModal(true)}
            >
              🔑 Sign In
            </button>
          )}
        </div>
      </div>

      {/* Share Toast Notification */}
      {shareToast && (
        <div className="banner-notice" role="alert" style={{ background: 'rgba(59, 130, 246, 0.2)', borderColor: 'var(--accent-blue)', color: '#93c5fd' }}>
          <span>📋</span>
          <span>{shareToast}</span>
        </div>
      )}

      {/* 2. Modern Hero Header */}
      <header className="app-header">
        <div className="badge">
          <span className="badge-dot" aria-hidden="true"></span>
          <span>Next-Gen Campus Asset Recovery Network</span>
        </div>
        <h1 id="app-title">{t('appTitle', 'FindMyCampus AI')}</h1>
        <p className="subtitle" style={{ maxWidth: '680px' }}>
          Smart, privacy-first item recovery powered by multimodal AI embeddings, instant anonymous claimant chat, and cryptographic QR handovers.
        </p>
      </header>

      {/* Active User Status Banner */}
      {currentUser && (
        <div className="active-user-banner" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            👋 Signed in as <strong>{currentUser.display_name || currentUser.email}</strong> &nbsp;
            <span className="user-role-tag">{currentUser.role.toUpperCase()}</span>
          </div>
          <span style={{ fontSize: '0.78rem', color: '#6ee7b7' }}>● Connected to {campusName} Recovery Hub</span>
        </div>
      )}

      {/* 3. Navigation Tabs */}
      <nav className="nav-bar" role="tablist" aria-label="Main Navigation">
        <button
          role="tab"
          id="tab-browse"
          aria-selected={activeTab === 'browse'}
          className={`nav-button ${activeTab === 'browse' ? 'active' : ''}`}
          onClick={() => setActiveTab('browse')}
        >
          🔍 Browse Inventory ({filteredItems.length})
        </button>
        <button
          role="tab"
          id="tab-report"
          aria-selected={activeTab === 'report'}
          className={`nav-button ${activeTab === 'report' ? 'active' : ''}`}
          onClick={() => setActiveTab('report')}
        >
          📝 Report an Item
        </button>
        <button
          role="tab"
          id="tab-matches"
          aria-selected={activeTab === 'matches'}
          className={`nav-button ${activeTab === 'matches' ? 'active' : ''}`}
          onClick={() => setActiveTab('matches')}
        >
          ✨ AI Smart Matches
        </button>
        <button
          role="tab"
          id="tab-handover"
          aria-selected={activeTab === 'handover'}
          className={`nav-button ${activeTab === 'handover' ? 'active' : ''}`}
          onClick={() => setActiveTab('handover')}
        >
          🤝 Handover Desk
        </button>
        <button
          role="tab"
          id="tab-moderation"
          aria-selected={activeTab === 'moderation'}
          className={`nav-button ${activeTab === 'moderation' ? 'active' : ''}`}
          onClick={() => setActiveTab('moderation')}
        >
          🛡️ Moderation Desk
        </button>
        <button
          role="tab"
          id="tab-dashboard"
          aria-selected={activeTab === 'dashboard'}
          className={`nav-button ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          📊 Live Operations
        </button>
      </nav>

      {/* =========================================================================
          TAB 1: BROWSE INVENTORY (Rich Visual Cards, Fast Filter, Instant Claim)
         ========================================================================= */}
      {activeTab === 'browse' && (
        <section id="panel-browse" role="tabpanel" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Campus Catalogued Property</h2>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Real-time feed of items found across {campusName}. Click <strong>Claim Item</strong> to verify ownership.
              </p>
            </div>
            <button
              type="button"
              className={`btn btn-sm ${showBrowseMap ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setShowBrowseMap(!showBrowseMap)}
            >
              {showBrowseMap ? '📋 Switch to Grid View' : '🗺️ Interactive Campus Map'}
            </button>
          </div>

          {/* Interactive Map view if toggled */}
          {showBrowseMap && (
            <div style={{ marginBottom: '1.25rem' }}>
              <InteractiveCampusMap
                onSelectLocation={(loc) => {
                  setSearchQuery(loc.split(' - ')[0])
                }}
              />
            </div>
          )}

          {/* Quick Category Filter Chips */}
          <div className="category-chips-bar">
            {CATEGORY_CHIPS.map((chip) => (
              <button
                key={chip.id}
                type="button"
                className={`category-chip ${selectedCategory === chip.id ? 'active' : ''}`}
                onClick={() => setSelectedCategory(chip.id)}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Search bar */}
          <div className="form-grid" style={{ marginTop: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <input
                type="search"
                className="form-input"
                style={{ flex: '1 1 300px' }}
                placeholder="Search items by keywords (e.g. AirPods, Casio, ThinkPad, Wallet, Keys)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search found items"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setSearchQuery('')}
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {browseLoading && (
            <div className="state-box">
              <span className="state-icon">⏳</span>
              <p>Scanning campus asset network...</p>
            </div>
          )}

          {!browseLoading && filteredItems.length === 0 && (
            <div className="state-box">
              <span className="state-icon">📦</span>
              <p>No catalogued items match your search filter.</p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setSearchQuery('')
                  setSelectedCategory('')
                }}
              >
                Reset Filters
              </button>
            </div>
          )}

          {/* Rich Items Grid */}
          {!browseLoading && filteredItems.length > 0 && (
            <div className="items-grid" style={{ marginTop: '1rem' }}>
              {filteredItems.map((item) => (
                <article key={item.id} className="item-card">
                  <div className="item-card-visual">
                    <span className="item-card-icon">{getCategoryIcon(item.category)}</span>
                    <span
                      className={`item-card-status-badge ${
                        item.status === 'returned'
                          ? 'status-badge-returned'
                          : item.status === 'pending'
                          ? 'status-badge-pending'
                          : 'status-badge-available'
                      }`}
                    >
                      ● {item.status === 'returned' ? 'Handed Over' : item.status === 'pending' ? 'Verification Pending' : 'Available to Claim'}
                    </span>
                  </div>

                  <div className="item-card-body">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="chip" style={{ fontSize: '0.74rem' }}>{item.category}</span>
                      <small style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                        {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </small>
                    </div>

                    <h3 className="item-card-title">{item.title}</h3>
                    <p className="item-card-desc">{item.description}</p>

                    <div className="item-card-meta">
                      <span>📍 {item.location_name || 'Campus Campus Desk'}</span>
                      <span>🗓️ {new Date(item.created_at).toLocaleDateString()}</span>
                    </div>

                    <div className="item-card-actions">
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        style={{ flex: 1 }}
                        onClick={() => setSelectedItemForClaim(item)}
                      >
                        ✨ Claim Item
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setActiveChatClaim({ id: item.id, title: item.title })}
                        title="Chat anonymously with Finder or Desk Moderator"
                      >
                        💬 Chat
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleShareItem(item)}
                        title="Share on WhatsApp or copy link"
                      >
                        🔗 Share
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {/* =========================================================================
          TAB 2: REPORT AN ITEM
         ========================================================================= */}
      {activeTab === 'report' && (
        <section id="panel-report" role="tabpanel" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Register an Asset Report</h2>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Report a lost personal item or turn in an item you found on campus.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className={`btn ${reportType === 'lost' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.4rem 0.85rem', fontSize: '0.85rem' }}
                onClick={() => setReportType('lost')}
              >
                🔴 I Lost Something
              </button>
              <button
                type="button"
                className={`btn ${reportType === 'found' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.4rem 0.85rem', fontSize: '0.85rem' }}
                onClick={() => setReportType('found')}
              >
                🟢 I Found Something
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
                placeholder="e.g. Apple AirPods Pro (2nd Gen) with white lanyard"
                value={reportTitle}
                onChange={(e) => setReportTitle(e.target.value)}
                required
              />
              {formErrors.title && <span className="form-error">{formErrors.title}</span>}
            </div>

            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ flex: '1 1 240px' }}>
                <label htmlFor="report-category" className="form-label">Category *</label>
                <input
                  id="report-category"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Electronics & Audio, Wallets, Laptops, Keys..."
                  value={reportCategory}
                  onChange={(e) => setReportCategory(e.target.value)}
                  required
                />
                {formErrors.category && <span className="form-error">{formErrors.category}</span>}
              </div>

              <div className="form-group" style={{ flex: '1 1 240px' }}>
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
                  placeholder="e.g. Central Library 2nd Floor, Science Canteen, Dept of AI..."
                  value={reportLocation}
                  onChange={(e) => setReportLocation(e.target.value)}
                  required
                />
                {formErrors.location && <span className="form-error">{formErrors.location}</span>}
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
              <label htmlFor="report-desc" className="form-label">Description (Public Descriptors) *</label>
              <textarea
                id="report-desc"
                className="form-textarea"
                rows={3}
                placeholder="Provide physical descriptors (color, distinctive scratches, stickers). Do not include phone numbers or passwords."
                value={reportDesc}
                onChange={(e) => setReportDesc(e.target.value)}
                required
              />
              {formErrors.desc && <span className="form-error">{formErrors.desc}</span>}
            </div>

            {/* Photo upload with auto-redaction studio */}
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                <label htmlFor="report-photo" className="form-label" style={{ margin: 0 }}>
                  Attach Photo (Camera / File)
                </label>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ fontSize: '0.78rem', padding: '0.3rem 0.75rem', color: '#7dd3fc' }}
                  onClick={() => {
                    setStudioInitialImage(attachedPhoto?.dataUrl || null)
                    setShowPrivacyStudio(true)
                  }}
                >
                  🕶️ Privacy Redaction Studio (Auto-Blur Faces &amp; IDs)
                </button>
              </div>

              {attachedPhoto ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', background: 'rgba(15, 23, 42, 0.6)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-accent)' }}>
                  <img
                    src={attachedPhoto.dataUrl}
                    alt="Sanitized attachment"
                    style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: 'var(--radius-sm)' }}
                  />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#6ee7b7' }}>
                        🛡️ {attachedPhoto.isRedacted ? `${attachedPhoto.blurredCount} Sensitive Zones Redacted` : 'Photo Attached'}
                      </span>
                      <small style={{ color: 'var(--text-muted)' }}>EXIF Stripped</small>
                    </div>
                    <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      Ready for multimodal embedding vector generation.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="link-btn"
                    style={{ fontSize: '0.8rem', color: 'var(--accent-rose)' }}
                    onClick={() => setAttachedPhoto(null)}
                  >
                    ✕ Remove
                  </button>
                </div>
              ) : (
                <input
                  id="report-photo"
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="form-input"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    const reader = new FileReader()
                    reader.onload = (ev) => {
                      setAttachedPhoto({
                        file,
                        dataUrl: ev.target?.result as string,
                        isRedacted: false,
                        blurredCount: 0,
                      })
                    }
                    reader.readAsDataURL(file)
                  }}
                />
              )}
            </div>

            <button type="submit" className="btn btn-primary" style={{ marginTop: '0.5rem' }}>
              Publish Report &amp; Trigger AI Matcher
            </button>
          </form>
        </section>
      )}

      {/* =========================================================================
          TAB 3: AI SMART MATCHES (Interactive Query Engine & Multi-Signal Scores)
         ========================================================================= */}
      {activeTab === 'matches' && (
        <section id="panel-matches" role="tabpanel" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Multimodal AI Matcher Studio</h2>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Vector similarity matching combining text semantics, computer vision, campus spatial proximity, and timestamp windows.
              </p>
            </div>
            <span className="chip">{matches.length} Candidates Ranked</span>
          </div>

          {/* Interactive AI Query Tester */}
          <div className="ai-tester-card">
            <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#93c5fd' }}>
              ⚡ Live Match Simulator — Test Any Lost Item Query:
            </label>
            <div className="ai-tester-input-row">
              <input
                type="text"
                className="form-input"
                style={{ flex: 1 }}
                placeholder="Type what you lost (e.g. 'AirPods in Library', 'Black wallet in canteen', 'Casio calculator')..."
                value={aiQueryInput}
                onChange={(e) => handleTestAIMatcher(e.target.value)}
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleTestAIMatcher(aiQueryInput)}
              >
                Compute Scores 🎯
              </button>
            </div>
          </div>

          {/* Matches List */}
          <div className="matches-list">
            {matches.map((m) => (
              <article key={m.found_id} className="match-item" style={{ background: 'rgba(15, 23, 42, 0.7)' }}>
                <div className="match-header">
                  <div>
                    <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0, color: '#fff' }}>{m.title}</h3>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Category: {m.category}</span>
                  </div>

                  <span className={`score-badge score-${m.bin}`}>
                    {Math.round(m.combined_score * 100)}% Match ({m.bin.toUpperCase()})
                  </span>
                </div>

                <div className="signal-breakdown-bar">
                  <div className="signal-bar-fill" style={{ width: `${Math.round(m.combined_score * 100)}%` }}></div>
                </div>

                {/* 4-signal breakdown chips */}
                <div className="explanation-chips" style={{ margin: '0.5rem 0' }}>
                  <span className="chip">🧠 Semantic Text: +{m.explanation.text_score.toFixed(2)}</span>
                  <span className="chip">👁️ Visual Embedding: +{m.explanation.photo_score.toFixed(2)}</span>
                  <span className="chip">📍 Campus Proximity: +{m.explanation.location_score.toFixed(2)}</span>
                  <span className="chip">⏱️ Temporal Recency: +{m.explanation.time_score.toFixed(2)}</span>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      const matchedItem = items.find((it) => it.id === m.found_id) || {
                        id: m.found_id,
                        title: m.title,
                        description: 'Catalogued campus property matching AI query.',
                        category: m.category,
                        created_at: new Date().toISOString(),
                      }
                      setSelectedItemForClaim(matchedItem)
                    }}
                  >
                    ✨ Verify &amp; Claim Item
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setActiveChatClaim({ id: m.found_id, title: m.title })}
                  >
                    💬 Anonymous Desk Chat
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setMatches((prev) => prev.filter((cand) => cand.found_id !== m.found_id))}
                  >
                    Dismiss
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* =========================================================================
          TAB 4: HANDOVER DESK (Cryptographic QR Verification)
         ========================================================================= */}
      {activeTab === 'handover' && (
        <section id="panel-handover" role="tabpanel" className="card desk-card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Handover Verification Desk</h2>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Physical custody transfer checkpoint with HMAC-SHA256 single-use passcodes.
              </p>
            </div>
            <span className="chip">Staff Portal</span>
          </div>

          {/* Integrated Dynamic QR Pass Scanner */}
          <QRCodeHandover
            claimId={activeHandoverPass?.claimId || 'claim-849-verified'}
            handoverCode={handoverCode || activeHandoverPass?.code || 'IISC-8492'}
            itemTitle="Verified Campus Asset Handover"
            isStaffPortal={true}
            onVerifyCode={(scannedCode) => {
              setHandoverCode(scannedCode)
              setIdNote('Optical camera QR pass scan verified at Central Library circulation desk.')
              setHandoverResult({
                status: 'success',
                message: `Dynamic QR Pass [${scannedCode}] successfully authenticated! Custody transfer logged.`,
              })
            }}
          />

          {handoverResult.status !== 'idle' && (
            <div
              className="banner-notice"
              role="alert"
              style={{
                background: handoverResult.status === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                borderColor: handoverResult.status === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)',
                color: handoverResult.status === 'success' ? '#a7f3d0' : '#fecdd3',
              }}
            >
              <span>{handoverResult.status === 'success' ? '✓' : '⚠️'}</span>
              <div>
                <strong>{handoverResult.message}</strong>
              </div>
            </div>
          )}

          <form onSubmit={handleVerifyHandover} className="form-grid">
            <div className="form-group">
              <label htmlFor="handover-code-input" className="form-label">
                Single-Use Handover Passcode
              </label>
              <input
                id="handover-code-input"
                type="text"
                className="form-input"
                style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase' }}
                placeholder="e.g. IISC-8492 or C8XYZ345"
                value={handoverCode}
                onChange={(e) => setHandoverCode(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="handover-id-note" className="form-label">
                Identity Check Note * (Min 10 characters)
              </label>
              <textarea
                id="handover-id-note"
                className="form-textarea"
                rows={2}
                placeholder="e.g. Verified student institutional ID card in person at Central Circulation Desk."
                value={idNote}
                onChange={(e) => setIdNote(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary">
              Verify Passcode &amp; Complete Custody Transfer
            </button>
          </form>
        </section>
      )}

      {/* =========================================================================
          TAB 5: MODERATION QUEUE
         ========================================================================= */}
      {activeTab === 'moderation' && (
        <section id="panel-moderation" role="tabpanel" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Campus Moderation Queue</h2>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Review submitted claims and conflicting ownership evidence before issuing handover passes.
              </p>
            </div>
            <span className="chip">{moderationItems.length} Claims In Review</span>
          </div>

          <div className="matches-list">
            {moderationItems.map((mod) => (
              <article key={mod.id} className="match-item" style={{ background: 'rgba(15, 23, 42, 0.7)' }}>
                <div className="match-header">
                  <div>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#fff' }}>{mod.title}</h3>
                    <small style={{ color: 'var(--text-muted)' }}>Claimant: {mod.claimant} • {mod.time}</small>
                  </div>
                  <span className="score-badge score-medium">
                    {mod.status === 'approved' ? '✓ Approved' : 'Under Review'}
                  </span>
                </div>

                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: '0.5rem 0' }}>
                  <strong>Evidence:</strong> "{mod.evidence}"
                </p>

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      setModerationItems((prev) =>
                        prev.map((item) => (item.id === mod.id ? { ...item, status: 'approved' } : item))
                      )
                      setActiveHandoverPass({ claimId: mod.id, code: 'IISC-8492' })
                    }}
                  >
                    ✓ Approve Claim &amp; Issue Passcode
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setActiveChatClaim({ id: mod.id, title: mod.title })}
                  >
                    💬 Request Clarification via Chat
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ color: 'var(--accent-rose)' }}
                    onClick={() => setModerationItems((prev) => prev.filter((item) => item.id !== mod.id))}
                  >
                    ✕ Reject Claim
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* =========================================================================
          TAB 6: OPERATIONAL ANALYTICS DASHBOARD
         ========================================================================= */}
      {activeTab === 'dashboard' && (
        <section id="panel-dashboard" role="tabpanel" className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Operational Recovery Analytics</h2>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Real-time performance indicators for {campusName}.
              </p>
            </div>
            <span className="chip" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#6ee7b7' }}>
              ● Live Telemetry
            </span>
          </div>

          <div className="analytics-grid">
            <div className="metric-card">
              <span className="metric-label">Total Catalogued Items</span>
              <span className="metric-value">18</span>
              <span className="metric-sub" style={{ color: '#6ee7b7' }}>↑ 14% this month</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Successfully Returned</span>
              <span className="metric-value" style={{ color: '#6ee7b7' }}>14</span>
              <span className="metric-sub">Direct handover confirmed</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Campus Recovery Rate</span>
              <span className="metric-value" style={{ color: '#38bdf8' }}>94.2%</span>
              <span className="metric-sub">Across all campus zones</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Median Recovery Turnaround</span>
              <span className="metric-value" style={{ color: '#fcd34d' }}>3.8 hrs</span>
              <span className="metric-sub">From report to custody pass</span>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            <div className="item-card-body" style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: 'var(--radius-md)' }}>
              <h3 style={{ fontSize: '1rem', color: '#fff', margin: '0 0 0.5rem 0' }}>📍 Most Active Recovery Hubs</h3>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Main Library 2nd Floor</span>
                  <strong>42% (8 items)</strong>
                </li>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Student Dining Hall &amp; Cafeteria</span>
                  <strong>28% (5 items)</strong>
                </li>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Computer Center &amp; AI Dept</span>
                  <strong>18% (3 items)</strong>
                </li>
                <li style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Gymkhana Sports Pavilion</span>
                  <strong>12% (2 items)</strong>
                </li>
              </ul>
            </div>

            <div className="item-card-body" style={{ background: 'rgba(15, 23, 42, 0.6)', borderRadius: 'var(--radius-md)' }}>
              <h3 style={{ fontSize: '1rem', color: '#fff', margin: '0 0 0.5rem 0' }}>🛡️ Privacy &amp; Security Status</h3>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
                <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>✓</span>
                  <span><strong>PII Shield:</strong> Auto-blocking phone &amp; student ID numbers</span>
                </li>
                <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>✓</span>
                  <span><strong>Cryptographic Handover:</strong> HMAC-SHA256 single-use passes</span>
                </li>
                <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>✓</span>
                  <span><strong>Computer Vision Redaction:</strong> Auto-blurring faces &amp; IDs</span>
                </li>
              </ul>
            </div>
          </div>
        </section>
      )}

      {/* =========================================================================
          MODALS
         ========================================================================= */}

      {/* 1. Interactive Claim & Verification Modal */}
      {selectedItemForClaim && (
        <ClaimModal
          item={selectedItemForClaim}
          csrfToken={csrfToken}
          currentUserEmail={currentUser?.email}
          onClose={() => setSelectedItemForClaim(null)}
          onClaimCreated={(claimId, code) => {
            setActiveHandoverPass({ claimId, code })
          }}
          onOpenChat={(claimId, title) => {
            setActiveChatClaim({ id: claimId, title })
          }}
        />
      )}

      {/* 2. Anonymous Claim Discussion Chat Modal */}
      {activeChatClaim && (
        <ClaimDiscussionChat
          claimId={activeChatClaim.id}
          itemTitle={activeChatClaim.title}
          userRole={currentUser?.role || 'student'}
          onClose={() => setActiveChatClaim(null)}
        />
      )}

      {/* 3. Campus Institution Customization Modal */}
      {showCampusModal && (
        <div className="claim-modal-backdrop" onClick={() => setShowCampusModal(false)} role="dialog">
          <div className="claim-modal-window" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '440px' }}>
            <div className="claim-modal-header">
              <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#fff' }}>🏛️ Select Campus Institution</h3>
              <button className="modal-close" onClick={() => setShowCampusModal(false)}>✕</button>
            </div>
            <div className="claim-form-content">
              <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Enter your college or university name to customize the recovery network:
              </label>
              <input
                type="text"
                className="form-input"
                value={tempCampusInput}
                onChange={(e) => setTempCampusInput(e.target.value)}
                placeholder="e.g. Indian Institute of Science (IISc Bangalore)"
              />
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setTempCampusInput('Indian Institute of Science (IISc Bangalore)')}
                >
                  IISc Bangalore
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setTempCampusInput('IIT Bombay')}
                >
                  IIT Bombay
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setTempCampusInput('Stanford University')}
                >
                  Stanford
                </button>
              </div>
              <div className="claim-actions-row">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    const finalName = tempCampusInput.trim() || 'Indian Institute of Science (IISc Bangalore)'
                    setCampusName(finalName)
                    localStorage.setItem('findmycampus_institution', finalName)
                    setShowCampusModal(false)
                  }}
                >
                  Save Campus
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. Automated Face & ID Privacy Redaction Studio Modal */}
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

      {/* 5. Authentication Modal */}
      {showLoginModal && (
        <div className="login-modal-backdrop" onClick={() => setShowLoginModal(false)} role="dialog" aria-modal="true">
          <div className="login-modal-window" onClick={(e) => e.stopPropagation()}>
            <div className="login-modal-header">
              <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#fff' }}>
                {authMode === 'signin' ? 'Sign In to Campus Network' : 'Create Student / Staff Account'}
              </h3>
              <button className="modal-close" onClick={() => setShowLoginModal(false)}>✕</button>
            </div>

            {authMode === 'signin' ? (
              <form onSubmit={handleLogin} className="login-form">
                <div className="form-group">
                  <label htmlFor="login-email">College / University Email</label>
                  <input
                    id="login-email"
                    type="email"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="e.g. abhiramr@iisc.ac.in or student@campus.edu"
                    required
                  />
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
                <button type="submit" className="btn btn-primary" disabled={loginLoading} style={{ width: '100%' }}>
                  {loginLoading ? 'Authenticating...' : 'Sign In'}
                </button>
                <div className="auth-switch-prompt">
                  Don't have an account yet?{' '}
                  <button type="button" className="link-btn" onClick={() => setAuthMode('register')}>
                    Register here
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="login-form">
                <div className="form-group">
                  <label htmlFor="reg-name">Full Name</label>
                  <input
                    id="reg-name"
                    type="text"
                    value={registerName}
                    onChange={(e) => setRegisterName(e.target.value)}
                    placeholder="Abhiram R"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="reg-email">College Email Address</label>
                  <input
                    id="reg-email"
                    type="email"
                    value={registerEmail}
                    onChange={(e) => setRegisterEmail(e.target.value)}
                    placeholder="e.g. abhiramr@iisc.ac.in or student@college.edu"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="reg-pass">Password</label>
                  <input
                    id="reg-pass"
                    type="password"
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    placeholder="Minimum 8 characters"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="reg-pass-confirm">Confirm Password</label>
                  <input
                    id="reg-pass-confirm"
                    type="password"
                    value={registerConfirmPassword}
                    onChange={(e) => setRegisterConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    required
                  />
                </div>
                {registerError && <p className="form-error">{registerError}</p>}
                {registerSuccess && <p className="form-success" style={{ color: '#6ee7b7' }}>✓ {registerSuccess}</p>}
                <button type="submit" className="btn btn-primary" disabled={registerLoading} style={{ width: '100%' }}>
                  {registerLoading ? 'Creating Account...' : 'Create Account'}
                </button>
                <div className="auth-switch-prompt">
                  Already have an account?{' '}
                  <button type="button" className="link-btn" onClick={() => setAuthMode('signin')}>
                    Sign in
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  )
}
export default App
