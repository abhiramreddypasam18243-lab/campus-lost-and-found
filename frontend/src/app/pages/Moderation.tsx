import { useMemo, useState, type FormEvent } from 'react'
import {
  api,
  type Claim,
  type DeskItem,
  type HandoverStatus,
  type HandoverVerify,
  type QueueItem,
  type QueueResponse,
  type StaffReport,
} from '../api'
import { useAuth } from '../auth'
import { categoryLabel, errorMessage, formatDateTime, timeAgo } from '../format'
import { indexLocations, placeLabel, useLocations } from '../locations'
import { Link, navigate } from '../router'
import {
  Alert,
  AsyncView,
  Badge,
  Button,
  Card,
  EmptyState,
  FormError,
  KeyValue,
  PageHeader,
  StatusBadge,
  Tabs,
  TextArea,
  TextField,
  toast,
  useAsync,
} from '../ui'

/* ---------------- queue ---------------- */

type QueueTab = 'claims' | 'reports' | 'duplicates'

function LockBadge({ item, me }: { item: QueueItem; me: string | undefined }) {
  if (!item.is_locked) return null
  const mine = item.locked_by_id === me
  return (
    <Badge tone={mine ? 'info' : 'warning'}>
      🔒 {mine ? 'Locked by you' : 'Locked by another moderator'}
      {item.lock_expires_at ? ` until ${formatDateTime(item.lock_expires_at)}` : ''}
    </Badge>
  )
}

export function QueuePage() {
  const { user } = useAuth()
  const state = useAsync(() => api.get<QueueResponse>('/api/mod/queue'), [])
  const [tab, setTab] = useState<QueueTab>('claims')
  const groups = useMemo(() => {
    const items = state.data?.items ?? []
    return {
      claims: items.filter((i) => i.item_type === 'claim'),
      reports: items.filter((i) => i.item_type === 'report'),
      duplicates: items.filter((i) => i.item_type === 'duplicate_image'),
    }
  }, [state.data])

  return (
    <>
      <PageHeader
        title="Moderation queue"
        subtitle="Oldest first; escalated claims (waiting over 14 days) are at the top."
        actions={
          <Button variant="secondary" onClick={state.reload} busy={state.loading}>
            Refresh
          </Button>
        }
      />
      <Tabs
        label="Queue sections"
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'claims', label: 'Claims', count: groups.claims.length },
          { id: 'reports', label: 'Found reports', count: groups.reports.length },
          { id: 'duplicates', label: 'Duplicate photos', count: groups.duplicates.length },
        ]}
      />
      <AsyncView state={state} label="Loading queue">
        {() => {
          const list = groups[tab]
          if (list.length === 0) {
            return (
              <EmptyState icon="check" title="Nothing waiting here">
                New {tab === 'claims' ? 'claims' : tab === 'reports' ? 'found reports' : 'duplicate-photo flags'} will
                appear automatically.
              </EmptyState>
            )
          }
          return (
            <div className="list">
              {list.map((item) => {
                const to =
                  item.item_type === 'claim'
                    ? `/mod/claims/${item.id}`
                    : item.item_type === 'report'
                      ? `/mod/reports/${item.id}`
                      : `/mod/reports/${String((item.extra_data as Record<string, unknown>)?.report_id ?? '')}`
                return (
                  <Link key={item.id} to={to} className="list-row">
                    <div className="list-main">
                      <div className="list-title">{item.title}</div>
                      <div className="muted small">Waiting {timeAgo(item.submitted_at)}</div>
                    </div>
                    <div className="list-side wrap">
                      {item.escalated && <Badge tone="danger">Escalated</Badge>}
                      {item.claimant_flagged && <Badge tone="warning">Claimant flagged</Badge>}
                      <LockBadge item={item} me={user?.id} />
                      <StatusBadge status={item.status} />
                    </div>
                  </Link>
                )
              })}
            </div>
          )
        }}
      </AsyncView>
    </>
  )
}

/* ---------------- report review ---------------- */

function StaffReportPanel({ r }: { r: StaffReport }) {
  const locations = useLocations()
  const index = useMemo(() => (locations.data ? indexLocations(locations.data) : null), [locations.data])
  return (
    <Card>
      <div className="item-card-meta">
        <Badge>{categoryLabel(r.category)}</Badge>
        <StatusBadge status={r.status} />
        <Badge tone="neutral">{r.type === 'lost' ? 'Lost report' : 'Found report'}</Badge>
      </div>
      <h2>{r.title}</h2>
      <p className="detail-desc">{r.description}</p>
      {(r.images ?? []).length > 0 && (
        <div className="gallery gallery-sm">
          {(r.images ?? []).map((img) => (
            <figure key={img.id}>
              <img src={`/api/images/${img.storage_key}`} alt={`Photo of ${r.title}`} className="photo photo-card" />
              <figcaption className="muted small">{img.is_public ? 'Public' : 'Private'} photo</figcaption>
            </figure>
          ))}
        </div>
      )}
      <KeyValue
        items={[
          ['Exact location', index ? placeLabel(index, r.location_id, r.location_text) : '…'],
          ['When', `${formatDateTime(r.window_start)} – ${formatDateTime(r.window_end)}`],
          ['Reporter', r.reporter ? `${r.reporter.display_name ?? '—'} (${r.reporter.email})` : '—'],
          ['Reported', formatDateTime(r.created_at)],
        ]}
      />
      <div className="private-box">
        <p className="field-label">🔒 Private details</p>
        <p className="pre">{r.private_details || <span className="muted">None</span>}</p>
        {(r.verification_prompts ?? []).length > 0 && (
          <>
            <p className="field-label">Verification questions</p>
            <ul>
              {(r.verification_prompts ?? []).map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </Card>
  )
}

export function ModReportPage({ id }: { id: string }) {
  const state = useAsync(() => api.get<StaffReport>(`/api/reports/${id}`), [id])
  const [busy, setBusy] = useState<string | null>(null)
  const act = async (action: 'approve' | 'remove') => {
    setBusy(action)
    try {
      await api.post(`/api/mod/reports/${id}/${action}`)
      toast(action === 'approve' ? 'Approved — the item is now listed.' : 'Report removed.')
      navigate('/mod/queue')
    } catch (err) {
      toast(errorMessage(err), 'danger')
    } finally {
      setBusy(null)
    }
  }
  return (
    <AsyncView state={state} label="Loading report">
      {(r) => (
        <>
          <PageHeader title="Review report" back={{ to: '/mod/queue', label: 'Queue' }} />
          <StaffReportPanel r={r} />
          {r.status === 'pending_review' ? (
            <div className="sticky-actions">
              <Button variant="danger" busy={busy === 'remove'} disabled={busy !== null} onClick={() => act('remove')}>
                Remove
              </Button>
              <Button busy={busy === 'approve'} disabled={busy !== null} onClick={() => act('approve')}>
                Approve and list
              </Button>
            </div>
          ) : (
            <Alert tone="info">This report is {r.status.replace(/_/g, ' ')}; no review action is needed.</Alert>
          )}
        </>
      )}
    </AsyncView>
  )
}

/* ---------------- claim review ---------------- */

type Decision = 'approve' | 'reject' | 'request-info'

export function ModClaimPage({ id }: { id: string }) {
  const { user } = useAuth()
  const claim = useAsync(() => api.get<Claim>(`/api/claims/${id}`), [id])
  const found = useAsync(
    () => (claim.data ? api.get<StaffReport>(`/api/reports/${claim.data.found_id}`) : Promise.resolve(null)),
    [claim.data?.found_id],
  )
  const [note, setNote] = useState('')
  const [noteError, setNoteError] = useState<string | undefined>()
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const openLock = async () => {
    setBusy('open')
    setError(null)
    try {
      await api.post(`/api/mod/claims/${id}/open`)
      toast('You have the review lock for 30 minutes.')
      claim.reload()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  const decide = async (decision: Decision) => {
    if (note.trim().length < 10) {
      setNoteError('Write a decision note of at least 10 characters.')
      return
    }
    setNoteError(undefined)
    setBusy(decision)
    setError(null)
    try {
      await api.post(`/api/mod/claims/${id}/${decision}`, { decision_note: note.trim() })
      toast(
        decision === 'approve'
          ? 'Approved. The item is reserved and the claimant received their handover code.'
          : decision === 'reject'
            ? 'Claim rejected.'
            : 'More information requested from the claimant.',
      )
      navigate('/mod/queue')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  return (
    <AsyncView state={claim} label="Loading claim">
      {(c) => {
        const lockedByMe = c.locked_by_id === user?.id && c.lock_expires_at && new Date(c.lock_expires_at) > new Date()
        const lockedByOther =
          c.locked_by_id && c.locked_by_id !== user?.id && c.lock_expires_at && new Date(c.lock_expires_at) > new Date()
        return (
          <>
            <PageHeader
              title={`Claim on “${c.found_title ?? 'item'}”`}
              back={{ to: '/mod/queue', label: 'Queue' }}
              subtitle={
                <>
                  <StatusBadge status={c.status} /> · submitted {formatDateTime(c.submitted_at)}
                </>
              }
            />
            <Alert tone="info">
              Compare the claimant’s evidence with the finder’s private details. The match score is only a
              suggestion — your decision is what counts.
            </Alert>
            <div className="grid-2">
              <Card>
                <h2>Claimant’s evidence</h2>
                <p className="pre">{c.evidence}</p>
                {Object.keys(c.answers ?? {}).length > 0 && (
                  <>
                    <h3>Answers</h3>
                    <KeyValue items={Object.entries(c.answers ?? {}).map(([q, a]) => [q, String(a)])} />
                  </>
                )}
              </Card>
              {found.loading && !found.data ? (
                <Card>
                  <p className="muted">Loading the found report…</p>
                </Card>
              ) : found.data ? (
                <StaffReportPanel r={found.data} />
              ) : (
                <Card>
                  <p className="muted">The found report could not be loaded.</p>
                </Card>
              )}
            </div>

            <Card>
              <h2>Decision</h2>
              <FormError error={error} />
              {c.status === 'submitted' && (
                <>
                  <p className="muted">Open the review to take a 30-minute lock so no one else decides it at the same time.</p>
                  <Button onClick={openLock} busy={busy === 'open'}>
                    Open review
                  </Button>
                </>
              )}
              {c.status === 'under_review' && lockedByOther && (
                <Alert tone="warning">Another moderator holds the lock until {formatDateTime(c.lock_expires_at)}.</Alert>
              )}
              {c.status === 'under_review' && !lockedByOther && (
                <>
                  {!lockedByMe && (
                    <Alert tone="warning">
                      Your lock has expired.{' '}
                      <button type="button" className="link-btn" onClick={openLock}>
                        Take the lock again
                      </button>
                    </Alert>
                  )}
                  <TextArea
                    label="Decision note"
                    required
                    rows={3}
                    max={2000}
                    hint="At least 10 characters. Recorded in the audit log; shown to the claimant if you reject or ask for more."
                    error={noteError}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                  <div className="form-actions">
                    <Button variant="secondary" busy={busy === 'request-info'} disabled={busy !== null} onClick={() => decide('request-info')}>
                      Ask for more info
                    </Button>
                    <Button variant="danger" busy={busy === 'reject'} disabled={busy !== null} onClick={() => decide('reject')}>
                      Reject
                    </Button>
                    <Button busy={busy === 'approve'} disabled={busy !== null} onClick={() => decide('approve')}>
                      Approve
                    </Button>
                  </div>
                </>
              )}
              {!['submitted', 'under_review'].includes(c.status) && (
                <p className="muted">No decision is pending ({c.status.replace(/_/g, ' ')}).</p>
              )}
            </Card>
          </>
        )
      }}
    </AsyncView>
  )
}

/* ---------------- handover desk ---------------- */

function DeskPanel({
  item,
  onChanged,
  onCompleted,
}: {
  item: DeskItem
  onChanged: () => void
  onCompleted: (title: string) => void
}) {
  const status = useAsync(() => api.get<HandoverStatus>(`/api/mod/handovers/${item.claim_id}`), [item.claim_id])
  const [code, setCode] = useState('')
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)
  const [fields, setFields] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [reissueError, setReissueError] = useState<unknown>(null)

  const verify = async (e: FormEvent) => {
    e.preventDefault()
    const f: Record<string, string> = {}
    if (code.replace(/[\s-]/g, '').length !== 8) f.code = 'Codes have 8 characters.'
    if (note.trim().length < 10) f.note = 'Record how you checked identity (at least 10 characters).'
    setFields(f)
    if (Object.keys(f).length) return
    setBusy(true)
    setResult(null)
    try {
      const res = await api.post<HandoverVerify>(`/api/mod/handovers/${item.claim_id}/verify`, {
        code,
        identity_note: note.trim(),
      })
      if (res.success) {
        onCompleted(item.found_title)
        return
      }
      setResult({ ok: false, text: 'Wrong code.' })
    } catch (err) {
      setResult({ ok: false, text: errorMessage(err) })
    } finally {
      // The code is never kept on screen after an attempt (AC-129).
      setCode('')
      setBusy(false)
      status.reload()
    }
  }

  return (
    <Card className="desk-panel">
      <h2>{item.found_title}</h2>
      <AsyncView state={status} label="Loading handover">
        {(s) => (
          <>
            <KeyValue
              items={[
                ['Status', <StatusBadge key="s" status={s.is_locked ? 'locked' : s.is_expired ? 'expired' : s.status} />],
                ['Attempts left', `${s.attempts_left} of ${s.max_attempts}`],
                ['Expires', formatDateTime(s.expires_at)],
                ['Reissues used', `${s.reissue_count} of ${s.max_reissues}`],
              ]}
            />
            {result && (
              <Alert tone={result.ok ? 'success' : 'danger'} title={result.ok ? 'Verified' : 'Not verified'}>
                {result.text} {!result.ok && !s.is_locked && `${s.attempts_left} attempt(s) left.`}
              </Alert>
            )}
            {!s.is_locked && !s.is_expired && s.status === 'issued' && (
              <form onSubmit={verify} noValidate className="form">
                <TextField
                  label="Code shown by the claimant"
                  autoComplete="off"
                  spellCheck={false}
                  className="input code-input"
                  inputMode="text"
                  maxLength={12}
                  placeholder="XXXX-XXXX"
                  hint="Case and dashes don’t matter. O is read as 0, I and L as 1."
                  error={fields.code}
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                />
                <TextArea
                  label="Identity check note"
                  required
                  rows={2}
                  hint="e.g. Checked campus ID card, name matches the account."
                  error={fields.note}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <Button type="submit" busy={busy} className="btn-block">
                  Verify and complete handover
                </Button>
              </form>
            )}
            {(s.is_locked || s.is_expired) && s.reissue_count < s.max_reissues && (
              <form
                className="form"
                onSubmit={async (e) => {
                  e.preventDefault()
                  setReissueError(null)
                  try {
                    await api.post(`/api/mod/handovers/${item.claim_id}/reissue`, { reason: reason.trim() })
                    toast('A new code was sent to the claimant. The old one no longer works.')
                    setReason('')
                    setResult(null)
                    status.reload()
                    onChanged()
                  } catch (err) {
                    setReissueError(err)
                  }
                }}
              >
                <Alert tone="warning">
                  {s.is_locked ? 'Locked after too many wrong codes.' : 'This code has expired.'} You can issue a new code to the claimant.
                </Alert>
                <FormError error={reissueError} />
                <TextField label="Reason for reissue" required value={reason} onChange={(e) => setReason(e.target.value)} />
                <Button type="submit" variant="secondary">
                  Reissue code
                </Button>
              </form>
            )}
          </>
        )}
      </AsyncView>
    </Card>
  )
}

export function DeskPage() {
  const list = useAsync(() => api.get<DeskItem[]>('/api/mod/handovers'), [])
  const [selected, setSelected] = useState<string | null>(null)
  const [completed, setCompleted] = useState<string | null>(null)
  const current = list.data?.find((d) => d.claim_id === selected) ?? null
  return (
    <>
      <PageHeader
        title="Handover desk"
        subtitle="Type the claimant’s code. You only see whether it is right — never the code itself."
      />
      {completed && (
        <Alert tone="success" title="Handover complete">
          Code accepted for “{completed}”. Hand the item over — the return, claim and lost report are now recorded as
          completed.
        </Alert>
      )}
      <div className="desk-layout">
        <div>
          <AsyncView
            state={list}
            label="Loading handovers"
            isEmpty={(d) => d.length === 0}
            empty={<EmptyState icon="inbox" title="No items waiting for collection" />}
          >
            {(items) => (
              <div className="list" role="list">
                {items.map((d) => (
                  <button
                    key={d.claim_id}
                    type="button"
                    role="listitem"
                    className={`list-row list-button ${selected === d.claim_id ? 'list-row-active' : ''}`}
                    aria-pressed={selected === d.claim_id}
                    onClick={() => {
                      setSelected(d.claim_id)
                      setCompleted(null)
                    }}
                  >
                    <div className="list-main">
                      <div className="list-title">{d.found_title}</div>
                      <div className="muted small">Expires {formatDateTime(d.expires_at)}</div>
                    </div>
                    <div className="list-side">
                      <StatusBadge status={d.is_locked ? 'locked' : d.is_expired ? 'expired' : d.status} />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </AsyncView>
        </div>
        <div>
          {current ? (
            <DeskPanel
              key={current.claim_id}
              item={current}
              onChanged={list.reload}
              onCompleted={(title) => {
                setCompleted(title)
                setSelected(null)
                list.reload()
              }}
            />
          ) : (
            <EmptyState icon="pointer" title="Choose a handover">
              Select the claimant’s item to enter their code.
            </EmptyState>
          )}
        </div>
      </div>
    </>
  )
}
