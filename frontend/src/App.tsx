import React, { useEffect, useState } from 'react'

interface HealthData {
  status: string
  database: string
  worker: string
  version: string
  environment: string
}

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<string>('')

  const fetchHealth = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/health')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const data: HealthData = await res.json()
      setHealth(data)
      setLastChecked(new Date().toLocaleTimeString())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reach API')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
  }, [])

  return (
    <main className="app-container" id="main-content">
      <header className="app-header">
        <div className="badge">
          <span className="badge-dot" aria-hidden="true"></span>
          <span>Step 1: Walking Skeleton</span>
        </div>
        <h1 id="app-title">Smart Campus Lost-and-Found</h1>
        <p className="subtitle">
          AI-assisted, privacy-preserving item retrieval network with explainable multimodal matching,
          verified handovers, and rigorous statistical benchmarking.
        </p>
      </header>

      <section className="grid-status" aria-label="System Infrastructure Status">
        {/* Backend API Card */}
        <article className="card" id="card-backend">
          <div className="card-header">
            <h2 className="card-title">
              <span aria-hidden="true">⚡</span> FastAPI Backend
            </h2>
            <span
              className={`status-indicator ${
                loading ? 'status-loading' : health ? 'status-ok' : 'status-err'
              }`}
            >
              {loading ? 'Checking...' : health?.status === 'ok' ? 'Online' : 'Degraded'}
            </span>
          </div>
          <div className="card-body">
            <div className="property-row">
              <span className="property-key">Endpoint</span>
              <span className="property-value">/api/health</span>
            </div>
            <div className="property-row">
              <span className="property-key">API Version</span>
              <span className="property-value">{health?.version || '1.0.0'}</span>
            </div>
            <div className="property-row">
              <span className="property-key">Environment</span>
              <span className="property-value">{health?.environment || 'development'}</span>
            </div>
          </div>
        </article>

        {/* PostgreSQL Database Card */}
        <article className="card" id="card-database">
          <div className="card-header">
            <h2 className="card-title">
              <span aria-hidden="true">🗄️</span> PostgreSQL + pgvector
            </h2>
            <span
              className={`status-indicator ${
                loading
                  ? 'status-loading'
                  : health?.database === 'ok'
                  ? 'status-ok'
                  : 'status-err'
              }`}
            >
              {loading ? 'Checking...' : health?.database === 'ok' ? 'Connected' : 'Unhealthy'}
            </span>
          </div>
          <div className="card-body">
            <div className="property-row">
              <span className="property-key">Engine</span>
              <span className="property-value">PostgreSQL 16</span>
            </div>
            <div className="property-row">
              <span className="property-key">Extension</span>
              <span className="property-value">pgvector 0.7+</span>
            </div>
            <div className="property-row">
              <span className="property-key">Migrations</span>
              <span className="property-value">Alembic (Head)</span>
            </div>
          </div>
        </article>

        {/* Background Worker Card */}
        <article className="card" id="card-worker">
          <div className="card-header">
            <h2 className="card-title">
              <span aria-hidden="true">⚙️</span> Background Worker
            </h2>
            <span
              className={`status-indicator ${
                loading ? 'status-loading' : health ? 'status-ok' : 'status-err'
              }`}
            >
              {loading ? 'Checking...' : health?.worker === 'ok' ? 'Active' : 'Offline'}
            </span>
          </div>
          <div className="card-body">
            <div className="property-row">
              <span className="property-key">Queue Mode</span>
              <span className="property-value">FOR UPDATE SKIP LOCKED</span>
            </div>
            <div className="property-row">
              <span className="property-key">Models</span>
              <span className="property-value">all-MiniLM / CLIP</span>
            </div>
            <div className="property-row">
              <span className="property-key">Dispatch</span>
              <span className="property-value">Transactional Outbox</span>
            </div>
          </div>
        </article>
      </section>

      {error && (
        <div
          role="alert"
          style={{
            padding: '1rem',
            background: 'rgba(244, 63, 94, 0.1)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: '12px',
            color: '#fb7185',
            textAlign: 'center',
            fontSize: '0.9rem',
          }}
        >
          <strong>Notice:</strong> {error} (Check backend connection or local proxy).
        </div>
      )}

      <div className="actions-container">
        <button
          type="button"
          id="btn-refresh-health"
          className="btn btn-primary"
          onClick={fetchHealth}
          disabled={loading}
        >
          {loading ? 'Checking...' : 'Check System Health'}
        </button>
        {lastChecked && (
          <span style={{ alignSelf: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Last checked: {lastChecked}
          </span>
        )}
      </div>

      <footer className="app-footer">
        <p>Smart Campus Lost-and-Found Network &bull; Spec-Driven Development &bull; Step 1 Walking Skeleton</p>
      </footer>
    </main>
  )
}

export default App
