import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, qs, type FoundList, type FoundSummary, type PublicReport, type StaffReport } from '../api'
import { isStaff, useAuth } from '../auth'
import { CATEGORIES, categoryIcon, categoryLabel, formatDate, SENSITIVE_CATEGORIES } from '../format'
import { buildingOptions, indexLocations, pathLabel, useLocations } from '../locations'
import { Link, navigate } from '../router'
import {
  Alert,
  AsyncView,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  SelectField,
  StatusBadge,
  TextField,
  useAsync,
} from '../ui'

export function ItemPhoto({
  url,
  category,
  alt,
  size = 'card',
}: {
  url: string | null | undefined
  category: string
  alt: string
  size?: 'card' | 'large' | 'thumb'
}) {
  if (url) {
    return <img className={`photo photo-${size}`} src={url} alt={alt} loading="lazy" />
  }
  const hidden = SENSITIVE_CATEGORIES.has(category)
  return (
    <div className={`photo photo-${size} photo-placeholder`} aria-label={hidden ? 'Photo hidden for privacy' : 'No photo'} role="img">
      <span className="photo-icon" aria-hidden="true">
        {categoryIcon(category)}
      </span>
      {size !== 'thumb' && <span className="photo-note">{hidden ? 'Photo hidden for privacy' : 'No photo'}</span>}
    </div>
  )
}

function SearchIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  )
}

function GiftIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 12v8H4v-8" />
      <path d="M2 7h20v5H2z" />
      <path d="M12 22V7" />
      <path d="M12 7C10 3 7 3 7 5s5 2 5 2 5 0 5-2-3-2-5 2" />
    </svg>
  )
}

function PinIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </svg>
  )
}

export function ItemCard({ item }: { item: FoundSummary }) {
  return (
    <article className="item-card">
      <Link to={`/found/${item.id}`} className="item-card-link" aria-label={`${item.title}, found ${formatDate(item.date)}`}>
        <ItemPhoto url={item.thumbnail_url} category={item.category} alt="" />
        <div className="item-card-body">
          <div className="item-card-meta">
            <Badge>{categoryLabel(item.category)}</Badge>
            <span className="muted small">{formatDate(item.date)}</span>
          </div>
          <h3 className="item-card-title">{item.title}</h3>
          <p className="item-card-desc">{item.description}</p>
          <p className="item-card-place">
            <PinIcon />
            {item.building ?? 'On campus'}
          </p>
        </div>
      </Link>
    </article>
  )
}

type Filters = { q: string; category: string; building_id: string; date_from: string; date_to: string }
const EMPTY: Filters = { q: '', category: '', building_id: '', date_from: '', date_to: '' }

export function BrowsePage() {
  const locations = useLocations()
  const buildings = useMemo(
    () => (locations.data ? buildingOptions(indexLocations(locations.data)) : []),
    [locations.data],
  )
  const [draft, setDraft] = useState<Filters>(EMPTY)
  const [filters, setFilters] = useState<Filters>(EMPTY)
  const [items, setItems] = useState<FoundSummary[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [tick, setTick] = useState(0)

  const fetchPage = async (f: Filters, after: string | null) => {
    return api.get<FoundList>(`/api/found${qs({ ...f, limit: 24, cursor: after })}`)
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchPage(filters, null)
      .then((res) => {
        if (cancelled) return
        setItems(res.items)
        setCursor(res.next_cursor)
      })
      .catch((e: unknown) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [filters, tick])

  const loadMore = async () => {
    if (!cursor) return
    setLoading(true)
    try {
      const res = await fetchPage(filters, cursor)
      setItems((xs) => [...xs, ...res.items])
      setCursor(res.next_cursor)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
    }
  }

  const apply = (e: FormEvent) => {
    e.preventDefault()
    setFilters(draft)
  }
  const active = Object.values(filters).some(Boolean)

  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <h1 id="hero-title" className="hero-title">
          Lost it? <em>Someone</em> probably found it.
        </h1>
        <div className="action-tiles">
          <button
            type="button"
            className="action-tile action-tile-lost"
            aria-labelledby="tile-lost"
            aria-describedby="tile-lost-text"
            onClick={() => navigate('/report/new?type=lost')}
          >
            <SearchIcon />
            <span>
              <span id="tile-lost" className="action-tile-title">I lost something</span>
              <span id="tile-lost-text" className="action-tile-text">
                Report it and we’ll match it against every found item, automatically.
              </span>
            </span>
          </button>
          <button
            type="button"
            className="action-tile action-tile-found"
            aria-labelledby="tile-found"
            aria-describedby="tile-found-text"
            onClick={() => navigate('/report/new?type=found')}
          >
            <GiftIcon />
            <span>
              <span id="tile-found" className="action-tile-title">I found something</span>
              <span id="tile-found-text" className="action-tile-text">
                Hand it in online in under a minute. Owners prove it’s theirs.
              </span>
            </span>
          </button>
        </div>
      </section>

      <div className="listing-head">
        <h2>Found on campus</h2>
        <p className="muted small">Private details and exact spots are never shown here.</p>
      </div>

      <div className="chips" role="group" aria-label="Quick filter by category">
        {[{ id: '', label: 'All' }, ...CATEGORIES].map((c) => (
          <button
            key={c.id || 'all'}
            type="button"
            className="chip"
            aria-pressed={filters.category === c.id}
            onClick={() => {
              setDraft({ ...draft, category: c.id })
              setFilters({ ...filters, category: c.id })
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      <Card className="filters">
        <form onSubmit={apply} className="filters-form" role="search" aria-label="Search found items">
          <div className="filters-search">
            <TextField
              label="Search"
              type="search"
              placeholder="e.g. blue bottle, black backpack"
              value={draft.q}
              onChange={(e) => setDraft({ ...draft, q: e.target.value })}
            />
          </div>
          <SelectField label="Category" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </SelectField>
          <SelectField label="Building" value={draft.building_id} onChange={(e) => setDraft({ ...draft, building_id: e.target.value })}>
            <option value="">Anywhere</option>
            {buildings.map((b) => (
              <option key={b.id} value={b.id}>
                {b.label}
              </option>
            ))}
          </SelectField>
          <TextField label="From" type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })} />
          <TextField label="To" type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })} />
          <div className="filters-actions">
            <Button type="submit">Search</Button>
            {active && (
              <Button
                variant="ghost"
                onClick={() => {
                  setDraft(EMPTY)
                  setFilters(EMPTY)
                }}
              >
                Clear
              </Button>
            )}
          </div>
        </form>
      </Card>

      {error !== null && items.length === 0 ? (
        <ErrorState error={error} onRetry={() => setTick((t) => t + 1)} />
      ) : loading && items.length === 0 ? (
        <Loading label="Loading found items" />
      ) : items.length === 0 ? (
        <EmptyState
          icon="🧭"
          title={active ? 'No items match those filters' : 'Nothing has been handed in yet'}
          action={
            <Button variant="secondary" onClick={() => navigate('/report/new?type=lost')}>
              Report what you lost
            </Button>
          }
        >
          {active
            ? 'Try fewer words or a wider date range.'
            : 'Report your lost item and we will suggest matches as found items arrive.'}
        </EmptyState>
      ) : (
        <>
          <p className="muted small results-count" aria-live="polite">
            Showing {items.length} item{items.length === 1 ? '' : 's'}
          </p>
          <div className="item-grid">
            {items.map((it) => (
              <ItemCard key={it.id} item={it} />
            ))}
          </div>
          {cursor && (
            <div className="center">
              <Button variant="secondary" busy={loading} onClick={loadMore}>
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </>
  )
}

function isStaffView(r: PublicReport | StaffReport): r is StaffReport {
  return 'reporter_id' in r
}

export function FoundDetailPage({ id }: { id: string }) {
  const { user } = useAuth()
  const state = useAsync(() => api.get<PublicReport | StaffReport>(`/api/reports/${id}`), [id])
  const locations = useLocations()

  return (
    <AsyncView state={state} label="Loading item">
      {(report) => {
        const staffView = isStaffView(report)
        const own = staffView && report.reporter_id === user?.id
        const photos = staffView
          ? (report.images ?? []).map((i) => ({ id: i.id, url: `/api/images/${i.storage_key}` }))
          : report.images.map((i) => ({ id: i.id, url: i.image_url }))
        const place = staffView
          ? locations.data
            ? pathLabel(indexLocations(locations.data), report.location_id)
            : '…'
          : report.building ?? 'On campus'
        return (
          <>
            <PageHeader title={report.title} back={{ to: '/', label: 'All found items' }} />
            <div className="detail-layout">
              <div className="detail-media">
                {photos.length ? (
                  <div className="gallery">
                    {photos.map((p) => (
                      <img key={p.id} src={p.url} alt={`Photo of ${report.title}`} className="photo photo-large" />
                    ))}
                  </div>
                ) : (
                  <ItemPhoto url={null} category={report.category} alt="" size="large" />
                )}
              </div>
              <Card className="detail-info">
                <div className="item-card-meta">
                  <Badge>{categoryLabel(report.category)}</Badge>
                  <StatusBadge status={report.status} />
                </div>
                <p className="detail-desc">{report.description}</p>
                <dl className="kv">
                  <div className="kv-row">
                    <dt>Found</dt>
                    <dd>{formatDate(staffView ? report.window_start : report.date)}</dd>
                  </div>
                  <div className="kv-row">
                    <dt>Where</dt>
                    <dd>{place}</dd>
                  </div>
                </dl>

                {own && (
                  <Alert tone="info" title="You reported this item">
                    {report.status === 'pending_review'
                      ? 'A moderator will review it before it appears in the listing.'
                      : 'Claims are reviewed by a moderator; you never see a claimant’s evidence.'}{' '}
                    <Link to={`/reports/${report.id}`}>Manage your report</Link>
                  </Alert>
                )}
                {staffView && !own && isStaff(user) && (
                  <Alert tone="warning" title="Staff view">
                    You can see private details because you are a moderator.{' '}
                    <Link to={`/mod/reports/${report.id}`}>Open the review page</Link>
                  </Alert>
                )}
                {!own && report.status === 'open' && report.type === 'found' && (
                  <div className="claim-cta">
                    <p className="muted">
                      Is this yours? Tell us something only the owner would know. A moderator checks every
                      claim before the item is handed over.
                    </p>
                    <Button onClick={() => navigate(`/claim/${report.id}`)} className="btn-block">
                      This is mine — start a claim
                    </Button>
                  </div>
                )}
              </Card>
            </div>
          </>
        )
      }}
    </AsyncView>
  )
}
