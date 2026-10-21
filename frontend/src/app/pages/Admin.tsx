import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  api,
  ApiError,
  qs,
  type Adjacency,
  type AdminJob,
  type AdminUser,
  type Dashboard,
  type Evaluation,
  type Location,
  type ModelEntry,
} from '../api'
import { useAuth } from '../auth'
import { errorMessage, formatDateTime, percent } from '../format'
import { indexLocations, loadLocations, type LocationIndex } from '../locations'
import {
  Alert,
  AsyncView,
  Badge,
  Button,
  Card,
  ConfirmButton,
  EmptyState,
  KeyValue,
  PageHeader,
  SelectField,
  StatusBadge,
  Tabs,
  TextField,
  toast,
  useAsync,
} from '../ui'

/* ---------------- dashboard ---------------- */

function Stat({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {note && <span className="stat-note">{note}</span>}
    </div>
  )
}

function hours(h: number | null | undefined): string {
  if (h === null || h === undefined) return '—'
  return h < 48 ? `${h.toFixed(1)} h` : `${(h / 24).toFixed(1)} days`
}

export function DashboardPage() {
  const state = useAsync(() => api.get<Dashboard>('/api/dashboard'), [])
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Operational metrics for found items." />
      <AsyncView state={state} label="Loading metrics">
        {(d) => (
          <>
            <Alert tone={d.is_synthetic_demo ? 'warning' : 'info'} title={d.is_synthetic_demo ? 'Synthetic demonstration data' : undefined}>
              {d.banner_notice}
            </Alert>
            <div className="stats">
              <Stat label="Recovery rate" value={percent(d.recovery_rate)} note="returned ÷ (returned + unclaimed)" />
              <Stat label="Median time to recovery" value={hours(d.median_time_to_recovery_hours)} note="found report → handover" />
              <Stat label="Unclaimed rate" value={percent(d.unclaimed_rate)} note="unclaimed ÷ created" />
              <Stat label="Queue age (median)" value={hours(d.queue_age_median_hours)} note="claims waiting for review" />
            </div>
            <div className="stats stats-small">
              <Stat label="Found reports" value={d.total_created} />
              <Stat label="Open" value={d.open_count} />
              <Stat label="Returned" value={d.returned_count} />
              <Stat label="Unclaimed" value={d.unclaimed_expired_count} />
            </div>
          </>
        )}
      </AsyncView>
    </>
  )
}

/* ---------------- admin ---------------- */

type AdminTab = 'users' | 'jobs' | 'models' | 'locations' | 'evaluation' | 'retention'

export function AdminPage({ tab, onTab }: { tab: AdminTab; onTab: (t: AdminTab) => void }) {
  return (
    <>
      <PageHeader title="Administration" />
      <Tabs
        label="Admin sections"
        active={tab}
        onChange={onTab}
        tabs={[
          { id: 'users', label: 'Users' },
          { id: 'jobs', label: 'Jobs' },
          { id: 'models', label: 'Models' },
          { id: 'locations', label: 'Locations' },
          { id: 'evaluation', label: 'Evaluation' },
          { id: 'retention', label: 'Retention' },
        ]}
      />
      {tab === 'users' && <UsersTab />}
      {tab === 'jobs' && <JobsTab />}
      {tab === 'models' && <ModelsTab />}
      {tab === 'locations' && <LocationsTab />}
      {tab === 'evaluation' && <EvaluationTab />}
      {tab === 'retention' && <RetentionTab />}
    </>
  )
}

export type { AdminTab }

function UsersTab() {
  const { user: me } = useAuth()
  const state = useAsync(() => api.get<AdminUser[]>('/api/admin/users'), [])
  const [filter, setFilter] = useState('')
  const changeRole = async (u: AdminUser, role: string) => {
    try {
      await api.patch(`/api/admin/users/${u.id}/role`, { role })
      toast(`${u.email} is now ${role}.`)
      state.reload()
    } catch (err) {
      toast(errorMessage(err), 'danger')
      state.reload()
    }
  }
  return (
    <AsyncView state={state} label="Loading users">
      {(users) => {
        const shown = users.filter((u) => u.email.includes(filter.toLowerCase()))
        return (
          <Card>
            <TextField label="Filter by email" type="search" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <div className="table-wrap">
              <table className="table">
                <caption className="sr-only">Users and roles</caption>
                <thead>
                  <tr>
                    <th scope="col">Email</th>
                    <th scope="col">Name</th>
                    <th scope="col">Status</th>
                    <th scope="col">Role</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((u) => (
                    <tr key={u.id}>
                      <td>{u.email}</td>
                      <td>{u.display_name ?? '—'}</td>
                      <td>{u.status}</td>
                      <td>
                        <label className="sr-only" htmlFor={`role-${u.id}`}>
                          Role for {u.email}
                        </label>
                        <select
                          id={`role-${u.id}`}
                          className="input select input-sm"
                          value={u.role}
                          disabled={u.id === me?.id}
                          onChange={(e) => changeRole(u, e.target.value)}
                        >
                          <option value="user">user</option>
                          <option value="moderator">moderator</option>
                          <option value="admin">admin</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small">Role changes are audited. The last admin cannot be demoted.</p>
          </Card>
        )
      }}
    </AsyncView>
  )
}

function JobsTab() {
  const [status, setStatus] = useState('failed')
  const state = useAsync(() => api.get<{ jobs: AdminJob[] }>(`/api/admin/jobs${qs({ status })}`), [status])
  return (
    <Card>
      <SelectField label="Show jobs" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="failed">Failed</option>
        <option value="pending">Pending</option>
        <option value="running">Running</option>
        <option value="completed">Completed</option>
        <option value="">All</option>
      </SelectField>
      <AsyncView
        state={state}
        isEmpty={(d) => d.jobs.length === 0}
        empty={<EmptyState icon="🧰" title="No jobs in this state" />}
      >
        {(d) => (
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Background jobs</caption>
              <thead>
                <tr>
                  <th scope="col">Kind</th>
                  <th scope="col">Status</th>
                  <th scope="col">Attempts</th>
                  <th scope="col">Next run</th>
                  <th scope="col">Last error</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {d.jobs.map((j) => (
                  <tr key={j.id}>
                    <td>{j.kind}</td>
                    <td>
                      <StatusBadge status={j.status} />
                    </td>
                    <td>
                      {j.attempts}/{j.max_attempts}
                    </td>
                    <td>{formatDateTime(j.run_after)}</td>
                    <td className="mono">{j.last_error ?? '—'}</td>
                    <td>
                      {j.status === 'failed' && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={async () => {
                            try {
                              await api.post(`/api/admin/jobs/${j.id}/retry`)
                              toast('Job queued again.')
                              state.reload()
                            } catch (err) {
                              toast(errorMessage(err), 'danger')
                            }
                          }}
                        >
                          Retry
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AsyncView>
    </Card>
  )
}

function ModelsTab() {
  const state = useAsync(() => api.get<ModelEntry[]>('/api/admin/models'), [])
  return (
    <AsyncView state={state} isEmpty={(d) => d.length === 0} empty={<EmptyState icon="🧠" title="No models registered" />}>
      {(models) => (
        <Card>
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Embedding models</caption>
              <thead>
                <tr>
                  <th scope="col">Type</th>
                  <th scope="col">Model</th>
                  <th scope="col">Version (pinned revision)</th>
                  <th scope="col">Dimension</th>
                  <th scope="col">State</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.id}>
                    <td>{m.model_type}</td>
                    <td>{m.model_name}</td>
                    <td className="mono">{m.model_version}</td>
                    <td>{m.dimension}</td>
                    <td>{m.is_active ? <Badge tone="success">Active</Badge> : <Badge>Inactive</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Weights are baked into the worker image and verified by checksum at build time; matching compares only
            vectors of the same version.
          </p>
        </Card>
      )}
    </AsyncView>
  )
}

/* ---------------- locations ---------------- */

const CHILD_KIND: Record<string, string[]> = {
  campus: ['building', 'area'],
  building: ['floor', 'area', 'room'],
  floor: ['room', 'area'],
  room: ['area'],
  area: ['area'],
}

function LocationNodeView({
  loc,
  index,
  onChanged,
}: {
  loc: Location
  index: LocationIndex
  onChanged: () => void
}) {
  const children = index.children.get(loc.id) ?? []
  const [editing, setEditing] = useState(false)
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState(loc.name)
  const [childName, setChildName] = useState('')
  const [childKind, setChildKind] = useState(CHILD_KIND[loc.kind]?.[0] ?? 'area')

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn()
      toast(ok)
      await loadLocations(true)
      onChanged()
    } catch (err) {
      toast(err instanceof ApiError && err.status === 409 ? 'Reports use this location, so it cannot be deleted.' : errorMessage(err), 'danger')
    }
  }

  return (
    <li className="tree-node">
      <div className="tree-row">
        <Badge>{loc.kind}</Badge>
        {editing ? (
          <form
            className="inline-form"
            onSubmit={(e) => {
              e.preventDefault()
              void run(() => api.patch(`/api/locations/${loc.id}`, { name: name.trim() }), 'Renamed.').then(() => setEditing(false))
            }}
          >
            <label className="sr-only" htmlFor={`rename-${loc.id}`}>
              New name
            </label>
            <input id={`rename-${loc.id}`} className="input input-sm" value={name} onChange={(e) => setName(e.target.value)} />
            <Button size="sm" type="submit">
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </form>
        ) : (
          <span className="tree-name">{loc.name}</span>
        )}
        {!editing && (
          <span className="tree-actions">
            <Button size="sm" variant="ghost" onClick={() => setAdding(!adding)}>
              + Child
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              Rename
            </Button>
            <ConfirmButton
              size="sm"
              variant="ghost"
              label="Delete"
              question={`Delete ${loc.name}?`}
              confirmLabel="Delete"
              onConfirm={() => run(() => api.del(`/api/locations/${loc.id}`), 'Deleted.')}
            />
          </span>
        )}
      </div>
      {adding && (
        <form
          className="inline-form tree-add"
          onSubmit={(e) => {
            e.preventDefault()
            if (!childName.trim()) return
            void run(
              () => api.post('/api/locations', { name: childName.trim(), kind: childKind, parent_id: loc.id }),
              'Location added.',
            ).then(() => {
              setChildName('')
              setAdding(false)
            })
          }}
        >
          <label className="sr-only" htmlFor={`kind-${loc.id}`}>
            Kind
          </label>
          <select id={`kind-${loc.id}`} className="input select input-sm" value={childKind} onChange={(e) => setChildKind(e.target.value)}>
            {(CHILD_KIND[loc.kind] ?? ['area']).map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <label className="sr-only" htmlFor={`child-${loc.id}`}>
            Name
          </label>
          <input
            id={`child-${loc.id}`}
            className="input input-sm"
            placeholder="Name"
            value={childName}
            onChange={(e) => setChildName(e.target.value)}
          />
          <Button size="sm" type="submit">
            Add
          </Button>
        </form>
      )}
      {children.length > 0 && (
        <ul className="tree">
          {children.map((c) => (
            <LocationNodeView key={c.id} loc={c} index={index} onChanged={onChanged} />
          ))}
        </ul>
      )}
    </li>
  )
}

function LocationsTab() {
  const [tick, setTick] = useState(0)
  const locs = useAsync(() => loadLocations(tick > 0), [tick])
  const adj = useAsync(() => api.get<Adjacency[]>('/api/locations/adjacency'), [tick])
  const index = useMemo(() => (locs.data ? indexLocations(locs.data) : null), [locs.data])
  const [campusName, setCampusName] = useState('')
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const refresh = () => setTick((t) => t + 1)
  const buildings = index ? [...index.byId.values()].filter((l) => l.kind === 'building') : []
  const nameOf = (id: string) => index?.byId.get(id)?.name ?? id

  const addCampus = async (e: FormEvent) => {
    e.preventDefault()
    if (!campusName.trim()) return
    try {
      await api.post('/api/locations', { name: campusName.trim(), kind: 'campus' })
      setCampusName('')
      await loadLocations(true)
      refresh()
    } catch (err) {
      toast(errorMessage(err), 'danger')
    }
  }

  const pairs = (adj.data ?? []).filter((p) => p.building_a < p.building_b)

  return (
    <div className="grid-2 grid-wide-left">
      <Card>
        <h2>Campus tree</h2>
        <AsyncView state={locs} isEmpty={(d) => d.length === 0} empty={<EmptyState icon="🏛️" title="No locations yet" />}>
          {() =>
            index && (
              <ul className="tree tree-root">
                {(index.children.get(null) ?? []).map((root) => (
                  <LocationNodeView key={root.id} loc={root} index={index} onChanged={refresh} />
                ))}
              </ul>
            )
          }
        </AsyncView>
        <form className="inline-form" onSubmit={addCampus}>
          <TextField label="New campus" value={campusName} onChange={(e) => setCampusName(e.target.value)} />
          <Button type="submit" variant="secondary">
            Add campus
          </Button>
        </form>
      </Card>
      <Card>
        <h2>Adjacent buildings</h2>
        <p className="muted small">Adjacent buildings score 0.5 for location instead of 0.2.</p>
        {pairs.length === 0 ? (
          <p className="muted">No adjacency yet.</p>
        ) : (
          <ul className="plain-list">
            {pairs.map((p) => (
              <li key={`${p.building_a}-${p.building_b}`} className="plain-row">
                <span>
                  {nameOf(p.building_a)} ↔ {nameOf(p.building_b)}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await api.del(`/api/locations/adjacency/${p.building_a}/${p.building_b}`)
                      refresh()
                    } catch (err) {
                      toast(errorMessage(err), 'danger')
                    }
                  }}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
        <form
          className="form"
          onSubmit={async (e) => {
            e.preventDefault()
            if (!a || !b || a === b) return
            try {
              await api.post('/api/locations/adjacency', { building_a: a, building_b: b })
              setA('')
              setB('')
              refresh()
            } catch (err) {
              toast(errorMessage(err), 'danger')
            }
          }}
        >
          <SelectField label="Building" value={a} onChange={(e) => setA(e.target.value)}>
            <option value="">Choose…</option>
            {buildings.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </SelectField>
          <SelectField label="is next to" value={b} onChange={(e) => setB(e.target.value)}>
            <option value="">Choose…</option>
            {buildings
              .filter((x) => x.id !== a)
              .map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
          </SelectField>
          <Button type="submit" variant="secondary">
            Add adjacency
          </Button>
        </form>
      </Card>
    </div>
  )
}

/* ---------------- evaluation ---------------- */

type Metrics = Record<string, number>
type SystemResult = { name: string; description: string; metrics: Metrics; mrr_ci: [number, number]; n_queries: number }
type NoiseResult = { metrics: Metrics; mrr_ci: [number, number] }

const fmt = (x: unknown, d = 3) => (typeof x === 'number' ? x.toFixed(d) : '—')
const ci = (c: unknown) => (Array.isArray(c) && c.length === 2 ? `[${fmt(c[0])}, ${fmt(c[1])}]` : '—')

function MetricsTable({ rows, caption }: { rows: [string, SystemResult | NoiseResult][]; caption: string }) {
  return (
    <div className="table-wrap">
      <table className="table table-num">
        <caption className="table-caption">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">System</th>
            <th scope="col">MRR</th>
            <th scope="col">95% CI</th>
            <th scope="col">R@1</th>
            <th scope="col">R@3</th>
            <th scope="col">R@5</th>
            <th scope="col">R@10</th>
            <th scope="col">nDCG@10</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, r]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td>{fmt(r.metrics.mrr)}</td>
              <td className="mono">{ci(r.mrr_ci)}</td>
              <td>{fmt(r.metrics.recall_at_1)}</td>
              <td>{fmt(r.metrics.recall_at_3)}</td>
              <td>{fmt(r.metrics.recall_at_5)}</td>
              <td>{fmt(r.metrics.recall_at_10)}</td>
              <td>{fmt(r.metrics.ndcg_at_10)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EvaluationTab() {
  const state = useAsync(() => api.get<Evaluation>('/api/admin/evaluation'), [])
  if (state.error instanceof ApiError && state.error.code === 'no_results') {
    return (
      <EmptyState icon="🧪" title="No evaluation results yet">
        Run the frozen evaluation offline: <code>python -m eval.runner final</code>. Results are never computed on live data.
      </EmptyState>
    )
  }
  return (
    <AsyncView state={state} label="Loading results">
      {(raw) => {
        const r = raw as unknown as Record<string, unknown>
        const systems = (r.systems ?? {}) as Record<string, SystemResult>
        const h1 = (r.hypothesis_h1 ?? {}) as Record<string, unknown>
        const ablations = (r.ablations ?? {}) as Record<string, Record<string, unknown>>
        const latency = (r.latency_benchmark ?? {}) as Record<string, unknown>
        const notEvaluated = (r.not_evaluated ?? []) as { system: string; reason: string }[]
        const limitations = (r.limitations ?? []) as string[]
        const models = (r.models ?? {}) as Record<string, unknown>
        const weights = (r.weights ?? {}) as Record<string, unknown>
        const noiseRows = (key: string) =>
          Object.entries((ablations[key] ?? {}) as Record<string, NoiseResult>).filter(([, v]) => v && typeof v === 'object' && 'metrics' in v)
        const sizes = (latency.sizes ?? {}) as Record<string, Record<string, { p50: number; p95: number } | number>>

        return (
          <div className="stack">
            <Alert tone="warning" title="Synthetic benchmark">
              These are findings on a seeded synthetic benchmark, not evidence of real-world recovery rates.
            </Alert>
            <Card>
              <h2>Hypothesis H1</h2>
              <p>{String(h1.statement ?? '')}</p>
              <KeyValue
                items={[
                  ['Pre-registered in', String(h1.registered_in ?? '—')],
                  ['Compared against', String(h1.best_baseline ?? '—')],
                  ['MRR difference', fmt(h1.mean_mrr_difference, 4)],
                  ['95% CI of difference', ci(h1.difference_95_ci)],
                  [
                    'Outcome',
                    <Badge key="o" tone={h1.is_supported ? 'success' : 'danger'}>
                      {h1.is_supported ? 'Supported (CI excludes 0)' : 'Not supported'}
                    </Badge>,
                  ],
                ]}
              />
              {typeof h1.outcome === 'string' && <p className="muted">{h1.outcome}</p>}
            </Card>
            <Card>
              <h2>Systems on the test split</h2>
              <MetricsTable caption="Test-set retrieval quality (bootstrap 95% CI over queries)" rows={Object.values(systems).map((s) => [s.name, s])} />
              {notEvaluated.length > 0 && (
                <Alert tone="info" title="Not evaluated">
                  <ul>
                    {notEvaluated.map((n) => (
                      <li key={n.system}>
                        <strong>{n.system}:</strong> {n.reason}
                      </li>
                    ))}
                  </ul>
                </Alert>
              )}
            </Card>
            <Card>
              <h2>Ablations and robustness (hybrid)</h2>
              <MetricsTable caption="Remove one signal" rows={noiseRows('signal_removal')} />
              <MetricsTable caption="Location noise (found report one level off)" rows={noiseRows('location_noise')} />
              <MetricsTable caption="Time noise (found time shifted 24 h)" rows={noiseRows('time_noise')} />
              {typeof (ablations.missing_photos as Record<string, unknown> | undefined)?.reason === 'string' && (
                <p className="muted small">Missing-photo sweep: {String((ablations.missing_photos as Record<string, unknown>).reason)}</p>
              )}
            </Card>
            <Card>
              <h2>Latency</h2>
              {latency.status === 'measured' ? (
                <div className="table-wrap">
                  <table className="table table-num">
                    <caption className="table-caption">Top-10 vector search in PostgreSQL + pgvector ({String(latency.dimension ?? '')}-d)</caption>
                    <thead>
                      <tr>
                        <th scope="col">Candidates</th>
                        <th scope="col">Exact p50 / p95 (ms)</th>
                        <th scope="col">HNSW p50 / p95 (ms)</th>
                        <th scope="col">HNSW recall@10</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(sizes).map(([n, v]) => {
                        const ex = v.exact_ms as { p50: number; p95: number }
                        const hn = v.hnsw_ms as { p50: number; p95: number }
                        return (
                          <tr key={n}>
                            <th scope="row">{Number(n).toLocaleString()}</th>
                            <td>
                              {fmt(ex?.p50, 2)} / {fmt(ex?.p95, 2)}
                            </td>
                            <td>
                              {fmt(hn?.p50, 2)} / {fmt(hn?.p95, 2)}
                            </td>
                            <td>{fmt(v.hnsw_recall_at_10, 3)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">{String(latency.reason ?? 'Not measured.')}</p>
              )}
            </Card>
            <Card>
              <h2>Run record</h2>
              <KeyValue
                items={[
                  ['Run at', formatDateTime(String(r.timestamp ?? ''))],
                  ['Text model', String(models.text_embedding ?? '—')],
                  ['Weights', Object.entries(weights).map(([k, v]) => `${k} ${String(v)}`).join(' · ') || '—'],
                  ['Seed', String(r.seed ?? '—')],
                  ['Test-set hash', <span key="h" className="mono">{String(r.dataset_hash ?? '—').slice(0, 16)}…</span>],
                  ['Frozen config hash', <span key="c" className="mono">{String(r.config_hash ?? '—').slice(0, 16)}…</span>],
                  ['Git commit', <span key="g" className="mono">{String(r.git_commit ?? '—').slice(0, 10)}</span>],
                ]}
              />
              {limitations.length > 0 && (
                <>
                  <h3>Limitations</h3>
                  <ul>
                    {limitations.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </>
              )}
            </Card>
          </div>
        )
      }}
    </AsyncView>
  )
}

function RetentionTab() {
  const [result, setResult] = useState<Record<string, number> | null>(null)
  const [busy, setBusy] = useState(false)
  return (
    <Card>
      <h2>Retention</h2>
      <p className="muted">
        The worker runs retention hourly: found items expire after 90 days unclaimed, and photos and claim evidence
        are deleted 30 days after closure. You can also run it now.
      </p>
      <Button
        variant="secondary"
        busy={busy}
        onClick={async () => {
          setBusy(true)
          try {
            setResult(await api.post<Record<string, number>>('/api/admin/retention/run'))
          } catch (err) {
            toast(errorMessage(err), 'danger')
          } finally {
            setBusy(false)
          }
        }}
      >
        Run retention now
      </Button>
      {result && (
        <KeyValue
          items={[
            ['Reports expired', result.expired_reports],
            ['Images purged', result.purged_images],
            ['Audit rows purged', result.purged_audit_logs],
          ]}
        />
      )}
    </Card>
  )
}
