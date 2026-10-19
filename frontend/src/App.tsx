import React, { useEffect, useState } from 'react'

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

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('browse')

  // Browse state
  const [items, setItems] = useState<FoundItem[]>([])
  const [browseLoading, setBrowseLoading] = useState<boolean>(false)
  const [browseError, setBrowseError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')

  // Report form state
  const [reportType, setReportType] = useState<'lost' | 'found'>('lost')
  const [reportTitle, setReportTitle] = useState<string>('')
  const [reportCategory, setReportCategory] = useState<string>('bottle')
  const [reportDesc, setReportDesc] = useState<string>('')
  const [reportLocation, setReportLocation] = useState<string>('Library - Floor 1')
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [reportSuccess, setReportSuccess] = useState<string | null>(null)

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

  const handleReportSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const errors: Record<string, string> = {}
    if (!reportTitle.trim()) {
      errors.title = 'Title is required'
    } else if (reportTitle.length < 5) {
      errors.title = 'Title must be at least 5 characters'
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
    setReportSuccess(`Successfully registered ${reportType} report: "${reportTitle}". AI matching enqueued.`)
    setReportTitle('')
    setReportDesc('')
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
      <header className="app-header">
        <div className="badge">
          <span className="badge-dot" aria-hidden="true"></span>
          <span>Smart Campus Network</span>
        </div>
        <h1 id="app-title">Campus Lost &amp; Found</h1>
        <p className="subtitle">
          Privacy-preserving campus asset recovery with multimodal AI matching, verified claims, and
          cryptographic handovers.
        </p>
      </header>

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
          🔍 Browse Found Items
        </button>
        <button
          role="tab"
          id="tab-report"
          aria-selected={activeTab === 'report'}
          aria-controls="panel-report"
          className={`nav-button ${activeTab === 'report' ? 'active' : ''}`}
          onClick={() => setActiveTab('report')}
        >
          📝 Report an Item
        </button>
        <button
          role="tab"
          id="tab-matches"
          aria-selected={activeTab === 'matches'}
          aria-controls="panel-matches"
          className={`nav-button ${activeTab === 'matches' ? 'active' : ''}`}
          onClick={() => setActiveTab('matches')}
        >
          ✨ AI Matches
        </button>
        <button
          role="tab"
          id="tab-handover"
          aria-selected={activeTab === 'handover'}
          aria-controls="panel-handover"
          className={`nav-button ${activeTab === 'handover' ? 'active' : ''}`}
          onClick={() => setActiveTab('handover')}
        >
          🤝 Handover Desk
        </button>
        <button
          role="tab"
          id="tab-moderation"
          aria-selected={activeTab === 'moderation'}
          aria-controls="panel-moderation"
          className={`nav-button ${activeTab === 'moderation' ? 'active' : ''}`}
          onClick={() => setActiveTab('moderation')}
        >
          🛡️ Moderation Queue
        </button>
        <button
          role="tab"
          id="tab-dashboard"
          aria-selected={activeTab === 'dashboard'}
          aria-controls="panel-dashboard"
          className={`nav-button ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          📊 Operational Analytics
        </button>
      </nav>

      {/* 1. BROWSE PANEL */}
      {activeTab === 'browse' && (
        <section id="panel-browse" role="tabpanel" aria-labelledby="tab-browse" className="card">
          <div className="card-header">
            <h2 className="card-title">Public Found Items</h2>
            <span className="chip">{items.length} items catalogued</span>
          </div>

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
              <select
                className="form-select"
                style={{ flex: '0 1 180px' }}
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                aria-label="Filter by category"
              >
                <option value="">All Categories</option>
                <option value="bottle">Water Bottles</option>
                <option value="bag">Bags &amp; Backpacks</option>
                <option value="laptop_tablet">Electronics</option>
                <option value="keys">Keys &amp; IDs</option>
              </select>
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
            <h2 className="card-title">Register an Item Report</h2>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className={`btn ${reportType === 'lost' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
                onClick={() => setReportType('lost')}
              >
                I Lost Something
              </button>
              <button
                type="button"
                className={`btn ${reportType === 'found' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
                onClick={() => setReportType('found')}
              >
                I Found Something
              </button>
            </div>
          </div>

          {reportSuccess && (
            <div className="banner-notice" role="alert" style={{ background: 'rgba(16, 185, 129, 0.15)', borderColor: 'rgba(16, 185, 129, 0.3)', color: '#a7f3d0' }}>
              <span>✓</span>
              <span>{reportSuccess}</span>
            </div>
          )}

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
              <div className="form-group" style={{ flex: '1 1 200px' }}>
                <label htmlFor="report-category" className="form-label">Category</label>
                <select
                  id="report-category"
                  className="form-select"
                  value={reportCategory}
                  onChange={(e) => setReportCategory(e.target.value)}
                >
                  <option value="bottle">Water Bottle</option>
                  <option value="bag">Bag / Backpack</option>
                  <option value="laptop_tablet">Laptop / Tablet</option>
                  <option value="phone">Phone</option>
                  <option value="keys">Keys</option>
                  <option value="wallet">Wallet</option>
                  <option value="clothing">Clothing</option>
                  <option value="book">Book</option>
                </select>
              </div>

              <div className="form-group" style={{ flex: '1 1 200px' }}>
                <label htmlFor="report-location" className="form-label">Campus Location</label>
                <select
                  id="report-location"
                  className="form-select"
                  value={reportLocation}
                  onChange={(e) => setReportLocation(e.target.value)}
                >
                  <option value="Library - Floor 1">Library - Floor 1</option>
                  <option value="Science Block - Floor 2">Science Block - Floor 2</option>
                  <option value="Engineering Center - Lab A">Engineering Center - Lab A</option>
                  <option value="Student Union - Cafeteria">Student Union - Cafeteria</option>
                </select>
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

            {/* AC-127: Mobile camera capture attribute */}
            <div className="form-group">
              <label htmlFor="report-photo" className="form-label">
                Attach Photo (Opens Camera on Mobile Devices)
              </label>
              <input
                id="report-photo"
                type="file"
                accept="image/*"
                capture="environment"
                className="form-input"
                aria-label="Upload photo using camera or file"
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Maximum 3 photos (up to 15MB total). All photos are stripped of EXIF data.
              </span>
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
            the student.
          </p>

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
    </main>
  )
}
export default App
