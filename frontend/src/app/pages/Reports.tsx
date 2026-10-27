import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  api,
  ApiError,
  qs,
  type ImageInfo,
  type Match,
  type MatchList,
  type Report,
  type StaffReport,
  type TimePrecision,
} from '../api'
import { useAuth } from '../auth'
import { CATEGORIES, binTone, categoryLabel, errorMessage, formatDate, formatDateTime, PRECISIONS, todayISO } from '../format'
import { indexLocations, PlaceField, placeLabel, useLocations, type PlaceValue } from '../locations'
import { Link, navigate } from '../router'
import {
  Alert,
  AsyncView,
  Badge,
  Button,
  Card,
  ConfirmButton,
  EmptyState,
  FormError,
  KeyValue,
  PageHeader,
  SelectField,
  StatusBadge,
  TextArea,
  TextField,
  toast,
  useAsync,
} from '../ui'
import { ItemPhoto } from './Browse'

const MAX_PHOTOS = 3
const MAX_BYTES = 5 * 1024 * 1024

type PhotoDraft = { file: File; url: string; error?: string }

function PhotoInput({ photos, onChange }: { photos: PhotoDraft[]; onChange: (p: PhotoDraft[]) => void }) {
  const add = (files: FileList | null) => {
    if (!files) return
    const next = [...photos]
    for (const file of Array.from(files)) {
      if (next.length >= MAX_PHOTOS) break
      const error =
        file.size > MAX_BYTES
          ? 'Over 5 MB'
          : !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
            ? 'Use JPEG, PNG or WebP'
            : undefined
      next.push({ file, url: URL.createObjectURL(file), error })
    }
    onChange(next)
  }
  return (
    <div className="field">
      <span className="field-label" id="photos-label">
        Photos <span className="muted small">(optional, up to {MAX_PHOTOS})</span>
      </span>
      <div className="photo-picker" aria-labelledby="photos-label">
        {photos.map((p, i) => (
          <div key={p.url} className={`photo-chip ${p.error ? 'photo-chip-bad' : ''}`}>
            <img src={p.url} alt={`Selected photo ${i + 1}`} />
            {p.error && <span className="photo-chip-error">{p.error}</span>}
            <button
              type="button"
              className="photo-chip-remove"
              aria-label={`Remove photo ${i + 1}`}
              onClick={() => {
                URL.revokeObjectURL(p.url)
                onChange(photos.filter((x) => x !== p))
              }}
            >
              ×
            </button>
          </div>
        ))}
        {photos.length < MAX_PHOTOS && (
          <label className="photo-add">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              multiple
              className="sr-only"
              onChange={(e) => {
                add(e.target.files)
                e.target.value = ''
              }}
            />
            <span aria-hidden="true">📷</span>
            <span>Add photo</span>
          </label>
        )}
      </div>
      <span className="field-hint">
        Photos are stripped of location data and re-encoded. Avoid faces and ID numbers.
      </span>
    </div>
  )
}

/** What to store as typed (D-22): nothing when the text is just the linked place's own label. */
function placeText(place: PlaceValue): string | null {
  const text = place.text.trim()
  return text && !place.linkedLabelOnly ? text : null
}

export function ReportFormPage({ initialType }: { initialType: 'lost' | 'found' }) {
  const { user } = useAuth()
  const [type, setType] = useState<'lost' | 'found'>(initialType)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('')
  const [place, setPlace] = useState<PlaceValue>({ text: '', locationId: '' })
  const [date, setDate] = useState(todayISO())
  const [precision, setPrecision] = useState<TimePrecision>('day')
  const [exactTime, setExactTime] = useState('')
  const [privateDetails, setPrivateDetails] = useState('')
  const [prompts, setPrompts] = useState<string[]>([''])
  const [photos, setPhotos] = useState<PhotoDraft[]>([])
  const [fields, setFields] = useState<Record<string, string>>({})
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => setType(initialType), [initialType])
  const verified = user?.email_verified ?? false

  const validate = () => {
    const f: Record<string, string> = {}
    if (title.trim().length < 3 || title.trim().length > 120) f.title = 'Use 3 to 120 characters.'
    if (description.trim().length < 10 || description.trim().length > 2000) f.description = 'Use 10 to 2,000 characters.'
    if (!category) f.category = 'Choose a category.'
    if (!place.locationId && !place.text.trim()) f.location = 'Type where it was, or pick a campus place.'
    if (place.text.length > 200) f.location = 'At most 200 characters.'
    if (!date) f.date = 'Choose the date.'
    if (date > todayISO()) f.date = 'The date cannot be in the future.'
    if (precision === 'exact' && !exactTime) f.exact_time = 'Enter the time, or pick a broader period.'
    if (privateDetails.length > 1000) f.private_details = 'At most 1,000 characters.'
    prompts.forEach((p, i) => {
      if (p.length > 200) f[`prompt_${i}`] = 'At most 200 characters.'
    })
    if (photos.some((p) => p.error)) f.photos = 'Remove the photos marked in red.'
    return f
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const f = validate()
    setFields(f)
    if (Object.keys(f).length) {
      document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
      return
    }
    setBusy(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        title: title.trim(),
        description: description.trim(),
        category,
        location_id: place.locationId || null,
        location_text: placeText(place),
        date,
        time_precision: precision,
        exact_time: precision === 'exact' ? exactTime : null,
      }
      if (type === 'found') {
        body.private_details = privateDetails.trim() || null
        body.verification_prompts = prompts.map((p) => p.trim()).filter(Boolean)
      }
      const report = await api.post<Report>(`/api/reports/${type}`, body)

      const failed: string[] = []
      for (const p of photos) {
        const form = new FormData()
        form.append('file', p.file)
        try {
          await api.post(`/api/reports/${report.id}/images`, form)
        } catch (err) {
          failed.push(`${p.file.name}: ${errorMessage(err)}`)
        }
      }
      if (failed.length) toast(`Report saved, but ${failed.length} photo(s) failed: ${failed.join('; ')}`, 'warning')
      else
        toast(
          type === 'found'
            ? 'Thanks! A moderator will review it before it is listed.'
            : 'Saved. We will look for matching found items in the background.',
        )
      navigate(`/reports/${report.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'pii_detected') {
        const field = String(err.details.field ?? 'title')
        setFields({ [field]: 'Remove phone numbers, email addresses and long numbers from this field.' })
        setError(err)
      } else if (err instanceof ApiError && Object.keys(err.fields).length) {
        setFields(err.fields)
      } else {
        setError(err)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title={type === 'lost' ? 'Report a lost item' : 'Report a found item'}
        subtitle={
          type === 'lost'
            ? 'Only you and campus staff can see lost reports.'
            : 'Found items are listed after a moderator checks them. Private details stay private.'
        }
      />
      {!verified && (
        <Alert tone="warning" title="Verify your email first">
          Reporting needs a verified campus email. Open the link we emailed you.
        </Alert>
      )}
      <Card>
        <form onSubmit={submit} noValidate className="form">
          <div className="segmented" role="radiogroup" aria-label="Report type">
            {(['lost', 'found'] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={type === t}
                className={`segment ${type === t ? 'segment-on' : ''}`}
                onClick={() => setType(t)}
              >
                {t === 'lost' ? 'I lost something' : 'I found something'}
              </button>
            ))}
          </div>

          <FormError error={error} />

          <TextField
            label="Title"
            required
            maxLength={120}
            showCount
            placeholder={type === 'lost' ? 'e.g. Navy blue water bottle' : 'e.g. Blue steel bottle'}
            hint="Short and descriptive. No names, phone numbers or ID numbers."
            error={fields.title}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <TextArea
            label="Description"
            required
            max={2000}
            rows={4}
            placeholder="Colour, brand, size, stickers, damage…"
            hint="Describe what anyone could see. Keep identifying details for the claim."
            error={fields.description}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="form-row">
            <SelectField label="Category" required error={fields.category} value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Choose…</option>
              {CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </SelectField>
            <TextField
              label={type === 'lost' ? 'Date lost' : 'Date found'}
              type="date"
              required
              max={todayISO()}
              error={fields.date}
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="form-row">
            <SelectField
              label="Time"
              value={precision}
              onChange={(e) => setPrecision(e.target.value as TimePrecision)}
              hint="Approximate is fine."
            >
              {PRECISIONS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </SelectField>
            {precision === 'exact' && (
              <TextField
                label="At"
                type="time"
                required
                error={fields.exact_time}
                value={exactTime}
                onChange={(e) => setExactTime(e.target.value)}
              />
            )}
          </div>
          <PlaceField
            label={type === 'lost' ? 'Where did you lose it?' : 'Where did you find it?'}
            value={place}
            onChange={setPlace}
            error={fields.location}
          />

          {type === 'found' && (
            <fieldset className="fieldset private-box">
              <legend className="field-label">🔒 Private — seen only by moderators and you</legend>
              <TextArea
                label="Private details"
                max={1000}
                rows={3}
                placeholder="e.g. Sticker with the letters RIA inside the lid; serial ending 4471"
                hint="Used to check claims. Never shown in listings or to claimants."
                error={fields.private_details}
                value={privateDetails}
                onChange={(e) => setPrivateDetails(e.target.value)}
              />
              <div className="field">
                <span className="field-label">Questions for the owner (up to 3)</span>
                <span className="field-hint">
                  A claimant must answer these, e.g. “What sticker is inside the lid?” Ask about things not visible in photos.
                </span>
                {prompts.map((p, i) => (
                  <div key={i} className="prompt-row">
                    <TextField
                      label={`Question ${i + 1}`}
                      maxLength={200}
                      error={fields[`prompt_${i}`]}
                      value={p}
                      onChange={(e) => setPrompts(prompts.map((x, j) => (j === i ? e.target.value : x)))}
                    />
                    {prompts.length > 1 && (
                      <Button variant="ghost" size="sm" onClick={() => setPrompts(prompts.filter((_, j) => j !== i))}>
                        Remove
                      </Button>
                    )}
                  </div>
                ))}
                {prompts.length < 3 && (
                  <Button variant="ghost" size="sm" onClick={() => setPrompts([...prompts, ''])}>
                    + Add a question
                  </Button>
                )}
              </div>
            </fieldset>
          )}

          <PhotoInput photos={photos} onChange={setPhotos} />
          {fields.photos && <p className="field-error">{fields.photos}</p>}

          <div className="form-actions">
            <Button variant="ghost" onClick={() => navigate('/reports')}>
              Cancel
            </Button>
            <Button type="submit" busy={busy} disabled={!verified}>
              {type === 'lost' ? 'Save lost report' : 'Submit found item'}
            </Button>
          </div>
        </form>
      </Card>
    </>
  )
}

export function MyReportsPage() {
  const state = useAsync(() => api.get<Report[]>('/api/reports/mine'), [])
  return (
    <>
      <PageHeader
        title="My reports"
        actions={<Button onClick={() => navigate('/report/new?type=lost')}>New report</Button>}
      />
      <AsyncView
        state={state}
        isEmpty={(d) => d.length === 0}
        empty={
          <EmptyState icon="note" title="You haven’t reported anything yet" action={<Button onClick={() => navigate('/report/new?type=lost')}>Report an item</Button>}>
            Lost reports get match suggestions as found items come in.
          </EmptyState>
        }
      >
        {(reports) => (
          <div className="list">
            {reports.map((r) => (
              <Link key={r.id} to={`/reports/${r.id}`} className="list-row">
                <ItemPhoto
                  url={r.images?.[0] ? `/api/images/${r.images[0].storage_key}` : null}
                  category={r.category}
                  alt=""
                  size="thumb"
                />
                <div className="list-main">
                  <div className="list-title">{r.title}</div>
                  <div className="muted small">
                    {r.type === 'lost' ? 'Lost' : 'Found'} · {categoryLabel(r.category)} · {formatDate(r.window_start)}
                  </div>
                </div>
                <div className="list-side">
                  <Badge tone={r.type === 'lost' ? 'info' : 'neutral'}>{r.type === 'lost' ? 'Lost' : 'Found'}</Badge>
                  <StatusBadge status={r.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </AsyncView>
    </>
  )
}

function SignalBar({ label, value }: { label: string; value: number | null }) {
  const pct = value === null ? 0 : Math.round(value * 100)
  return (
    <div className="signal">
      <span className="signal-label">{label}</span>
      <span className="signal-track" aria-hidden="true">
        <span className="signal-fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="signal-value">{value === null ? 'n/a' : `${pct}%`}</span>
    </div>
  )
}

function MatchCard({ match, lostId, onDismiss }: { match: Match; lostId: string; onDismiss: () => void }) {
  const f = match.found_report
  return (
    <Card as="article" className="match-card">
      <div className="match-head">
        <ItemPhoto url={f.thumbnail_url} category={f.category} alt="" size="thumb" />
        <div className="match-title">
          <h3>{f.title}</h3>
          <p className="muted small">
            {categoryLabel(f.category)} · {f.building ?? 'On campus'} · found {formatDate(f.date)}
          </p>
        </div>
        <div className="match-score">
          <span className="match-score-num">{Math.round(match.score * 100)}%</span>
          <Badge tone={binTone(match.bin)}>{match.bin} match</Badge>
        </div>
      </div>
      {match.explanation.length > 0 && (
        <ul className="why">
          {match.explanation.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <div className="signals" aria-label="Signal breakdown">
        <SignalBar label="Description" value={match.text_score} />
        <SignalBar label="Photo" value={match.image_score} />
        <SignalBar label="Place" value={match.location_score} />
        <SignalBar label="Time" value={match.time_score} />
      </div>
      <div className="match-actions">
        <Button variant="secondary" size="sm" onClick={() => navigate(`/found/${f.id}`)}>
          View item
        </Button>
        <Button size="sm" onClick={() => navigate(`/claim/${f.id}?lost=${lostId}`)}>
          This is mine — claim
        </Button>
        <ConfirmButton
          label="Not mine"
          question="Hide this suggestion for good?"
          confirmLabel="Hide it"
          variant="ghost"
          size="sm"
          onConfirm={async () => {
            try {
              await api.post(`/api/matches/${match.id}/dismiss`)
              toast('Suggestion hidden.')
              onDismiss()
            } catch (err) {
              toast(errorMessage(err), 'danger')
            }
          }}
        />
      </div>
    </Card>
  )
}

function MatchesPanel({ lostId }: { lostId: string }) {
  const state = useAsync(() => api.get<MatchList>(`/api/reports/${lostId}/matches${qs({ limit: 10 })}`), [lostId])
  return (
    <section aria-labelledby="matches-h" className="section">
      <div className="section-head">
        <h2 id="matches-h">Possible matches</h2>
        <Button variant="ghost" size="sm" onClick={state.reload} busy={state.loading}>
          Refresh
        </Button>
      </div>
      <Alert tone="info">
        <strong>Suggestions only.</strong> A match score is not proof of ownership — a moderator verifies every claim.
      </Alert>
      <AsyncView
        state={state}
        label="Finding matches"
        isEmpty={(d) => d.matches.length === 0}
        empty={
          <EmptyState icon="clock" title="No suggestions yet">
            Matching runs in the background a few seconds after each new report. New found items are checked
            against your report automatically — come back later or browse the listing.
          </EmptyState>
        }
      >
        {(d) => (
          <div className="stack">
            {d.matches.map((m) => (
              <MatchCard key={m.id} match={m} lostId={lostId} onDismiss={state.reload} />
            ))}
          </div>
        )}
      </AsyncView>
    </section>
  )
}

export function MyReportDetailPage({ id }: { id: string }) {
  const state = useAsync(() => api.get<StaffReport>(`/api/reports/${id}`), [id])
  const locations = useLocations()
  const index = useMemo(() => (locations.data ? indexLocations(locations.data) : null), [locations.data])

  return (
    <AsyncView state={state} label="Loading report">
      {(r) => (
        <>
          <PageHeader
            title={r.title}
            back={{ to: '/reports', label: 'My reports' }}
            subtitle={
              <>
                {r.type === 'lost' ? 'Lost' : 'Found'} report · <StatusBadge status={r.status} />
              </>
            }
            actions={
              r.status === 'open' || r.status === 'pending_review' ? (
                <ConfirmButton
                  label="Close report"
                  question={r.type === 'lost' ? 'Close it (e.g. you found it yourself)?' : 'Close this report?'}
                  confirmLabel="Close"
                  onConfirm={async () => {
                    try {
                      await api.patch(`/api/reports/${r.id}/close`)
                      toast('Report closed.')
                      state.reload()
                    } catch (err) {
                      toast(errorMessage(err), 'danger')
                    }
                  }}
                />
              ) : undefined
            }
          />
          <div className="detail-layout">
            <div className="detail-media">
              {(r.images ?? []).length ? (
                <div className="gallery">
                  {(r.images ?? []).map((img: ImageInfo) => (
                    <img key={img.id} src={`/api/images/${img.storage_key}`} alt={`Photo of ${r.title}`} className="photo photo-large" />
                  ))}
                </div>
              ) : (
                <ItemPhoto url={null} category={r.category} alt="" size="large" />
              )}
            </div>
            <Card className="detail-info">
              <p className="detail-desc">{r.description}</p>
              <KeyValue
                items={[
                  ['Category', categoryLabel(r.category)],
                  ['Where', index ? placeLabel(index, r.location_id, r.location_text) : '…'],
                  ['When', `${formatDateTime(r.window_start)} – ${formatDateTime(r.window_end)}`],
                  ['Reported', formatDate(r.created_at)],
                ]}
              />
              {r.type === 'found' && (
                <div className="private-box">
                  <p className="field-label">🔒 Private details</p>
                  <p>{r.private_details || <span className="muted">None</span>}</p>
                  {(r.verification_prompts ?? []).length > 0 && (
                    <>
                      <p className="field-label">Questions for claimants</p>
                      <ul>
                        {(r.verification_prompts ?? []).map((p) => (
                          <li key={p}>{p}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}
              {r.type === 'found' && r.status === 'pending_review' && (
                <Alert tone="warning">Waiting for a moderator before it appears in the listing.</Alert>
              )}
            </Card>
          </div>
          {r.type === 'lost' && r.status === 'open' && <MatchesPanel lostId={r.id} />}
        </>
      )}
    </AsyncView>
  )
}
