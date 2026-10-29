import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  api,
  ApiError,
  qs,
  type Adjacency,
  type AdminJob,
  type AdminUser,
  type Dashboard,
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
  PageHeader,
  SelectField,
  StatusBadge,
  Tabs,
  TextField,
  toast,
  useAsync,
} from '../ui'

/* ---------------- dashboard ---------------- */

function Stat({ label, value, note, feature = false }: { label: string; value: ReactNode; note?: string; feature?: boolean }) {
  return (
    <div className={`stat ${feature ? 'stat-feature' : ''}`}>
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
              <Stat feature label="Recovery rate" value={percent(d.recovery_rate)} note="returned ÷ (returned + unclaimed)" />
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

const ADMIN_TABS = ['users', 'jobs', 'models', 'locations'] as const
type AdminTab = (typeof ADMIN_TABS)[number]

/** Old links such as #/admin/evaluation (removed, D-23) open Users. */
export const toAdminTab = (s: string): AdminTab => (ADMIN_TABS as readonly string[]).includes(s) ? (s as AdminTab) : 'users'

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
        ]}
      />
      {tab === 'users' && <UsersTab />}
      {tab === 'jobs' && <JobsTab />}
      {tab === 'models' && <ModelsTab />}
      {tab === 'locations' && <LocationsTab />}
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
        empty={<EmptyState icon="gear" title="No jobs in this state" />}
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
    <AsyncView state={state} isEmpty={(d) => d.length === 0} empty={<EmptyState icon="chip" title="No models registered" />}>
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
        <AsyncView state={locs} isEmpty={(d) => d.length === 0} empty={<EmptyState icon="building" title="No locations yet" />}>
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
