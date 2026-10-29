import { useState, type FormEvent } from 'react'
import { api, ApiError, type Claim, type ClaimForm, type Report } from '../api'
import { categoryLabel, errorMessage, formatDateTime, groupCode, timeAgo } from '../format'
import { Link, navigate } from '../router'
import {
  Alert,
  AsyncView,
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
  toast,
  useAsync,
} from '../ui'

const EVIDENCE_MIN = 20
const EVIDENCE_MAX = 2000

function AnswersFields({
  prompts,
  answers,
  onChange,
  errors,
}: {
  prompts: string[]
  answers: Record<string, string>
  onChange: (a: Record<string, string>) => void
  errors: Record<string, string>
}) {
  if (prompts.length === 0) return null
  return (
    <fieldset className="fieldset">
      <legend className="field-label">The finder’s questions</legend>
      {prompts.map((p, i) => (
        <TextArea
          key={p}
          label={p}
          required
          rows={2}
          max={500}
          error={errors[`answer_${i}`]}
          value={answers[p] ?? ''}
          onChange={(e) => onChange({ ...answers, [p]: e.target.value })}
        />
      ))}
    </fieldset>
  )
}

export function ClaimFormPage({ foundId, lostId }: { foundId: string; lostId: string | null }) {
  const form = useAsync(() => api.get<ClaimForm>(`/api/found/${foundId}/claim-form`), [foundId])
  const mine = useAsync(() => api.get<Report[]>('/api/reports/mine'), [])
  const [evidence, setEvidence] = useState('')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [linkLost, setLinkLost] = useState(lostId ?? '')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const openLost = (mine.data ?? []).filter((r) => r.type === 'lost' && r.status === 'open')

  const submit = async (e: FormEvent, prompts: string[]) => {
    e.preventDefault()
    const f: Record<string, string> = {}
    const len = evidence.trim().length
    if (len < EVIDENCE_MIN || len > EVIDENCE_MAX) f.evidence = `Use ${EVIDENCE_MIN} to ${EVIDENCE_MAX} characters.`
    prompts.forEach((p, i) => {
      if (!(answers[p] ?? '').trim()) f[`answer_${i}`] = 'Please answer this question.'
    })
    setErrors(f)
    if (Object.keys(f).length) return
    setBusy(true)
    setError(null)
    try {
      const claim = await api.post<Claim>('/api/claims', {
        found_id: foundId,
        lost_id: linkLost || null,
        evidence: evidence.trim(),
        answers: Object.fromEntries(prompts.map((p) => [p, answers[p].trim()])),
      })
      toast('Claim submitted. A moderator will review it.')
      navigate(`/claims/${claim.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.fields.evidence) setErrors({ evidence: err.fields.evidence })
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AsyncView state={form} label="Loading claim form">
      {(cf) => (
        <>
          <PageHeader
            title="Claim this item"
            subtitle={`${cf.title} · ${categoryLabel(cf.category)} · ${cf.building ?? 'On campus'}`}
            back={{ to: `/found/${foundId}`, label: 'Back to item' }}
          />
          <Card>
            <form onSubmit={(e) => submit(e, cf.verification_prompts)} noValidate className="form">
              <Alert tone="info">
                Only you and moderators can read your evidence — the finder never sees it. You can have at most 3
                active claims.
              </Alert>
              <FormError error={error} />
              <TextArea
                label="Why is this yours?"
                required
                rows={5}
                max={EVIDENCE_MAX}
                hint="Details only the owner would know: marks, contents, serial number, where you left it."
                error={errors.evidence}
                value={evidence}
                onChange={(e) => setEvidence(e.target.value)}
              />
              <AnswersFields prompts={cf.verification_prompts} answers={answers} onChange={setAnswers} errors={errors} />
              {openLost.length > 0 && (
                <SelectField
                  label="Link to your lost report"
                  hint="Optional. Helps the moderator compare."
                  value={linkLost}
                  onChange={(e) => setLinkLost(e.target.value)}
                >
                  <option value="">Don’t link</option>
                  {openLost.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title}
                    </option>
                  ))}
                </SelectField>
              )}
              <div className="form-actions">
                <Button variant="ghost" onClick={() => navigate(`/found/${foundId}`)}>
                  Cancel
                </Button>
                <Button type="submit" busy={busy}>
                  Submit claim
                </Button>
              </div>
            </form>
          </Card>
        </>
      )}
    </AsyncView>
  )
}

export function MyClaimsPage() {
  const state = useAsync(() => api.get<Claim[]>('/api/claims/my'), [])
  return (
    <>
      <PageHeader title="My claims" subtitle="Claims you made on found items, and their review status." />
      <AsyncView
        state={state}
        isEmpty={(d) => d.length === 0}
        empty={
          <EmptyState icon="hand" title="No claims yet" action={<Button onClick={() => navigate('/')}>Browse found items</Button>}>
            When you spot your item, open it and choose “This is mine”.
          </EmptyState>
        }
      >
        {(claims) => (
          <div className="list">
            {claims.map((c) => (
              <Link key={c.id} to={`/claims/${c.id}`} className="list-row">
                <div className="list-main">
                  <div className="list-title">{c.found_title ?? 'Found item'}</div>
                  <div className="muted small">Submitted {timeAgo(c.submitted_at)}</div>
                </div>
                <div className="list-side">
                  {c.status === 'approved' && c.handover_code && <span className="code-hint">Code ready</span>}
                  <StatusBadge status={c.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </AsyncView>
    </>
  )
}

const STEPS = ['submitted', 'under_review', 'approved', 'completed'] as const

function ClaimTimeline({ status }: { status: string }) {
  const terminalBad = ['rejected', 'withdrawn', 'expired'].includes(status)
  const position = status === 'needs_more_info' ? 1 : STEPS.indexOf(status as (typeof STEPS)[number])
  const labels = ['Submitted', 'Under review', 'Approved', 'Collected']
  return (
    <ol className="timeline" aria-label="Claim progress">
      {labels.map((label, i) => {
        const state = terminalBad ? 'todo' : i < position ? 'done' : i === position ? 'current' : 'todo'
        return (
          <li key={label} className={`timeline-step timeline-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
            <span className="timeline-dot" aria-hidden="true" />
            <span>{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

function MoreInfoForm({ claim, prompts, onDone }: { claim: Claim; prompts: string[]; onDone: () => void }) {
  const [evidence, setEvidence] = useState(claim.evidence)
  const [answers, setAnswers] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(claim.answers ?? {}).map(([k, v]) => [k, String(v)])),
  )
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  return (
    <form
      className="form"
      noValidate
      onSubmit={async (e) => {
        e.preventDefault()
        const len = evidence.trim().length
        if (len < EVIDENCE_MIN || len > EVIDENCE_MAX) {
          setErrors({ evidence: `Use ${EVIDENCE_MIN} to ${EVIDENCE_MAX} characters.` })
          return
        }
        setBusy(true)
        setError(null)
        try {
          await api.patch(`/api/claims/${claim.id}/evidence`, { evidence: evidence.trim(), answers })
          toast('Thanks — your claim is back in the review queue.')
          onDone()
        } catch (err) {
          setError(err)
        } finally {
          setBusy(false)
        }
      }}
    >
      <FormError error={error} />
      <TextArea
        label="Updated evidence"
        required
        rows={5}
        max={EVIDENCE_MAX}
        error={errors.evidence}
        value={evidence}
        onChange={(e) => setEvidence(e.target.value)}
      />
      <AnswersFields prompts={prompts} answers={answers} onChange={setAnswers} errors={{}} />
      <div className="form-actions">
        <Button type="submit" busy={busy}>
          Send to moderator
        </Button>
      </div>
    </form>
  )
}

export function ClaimDetailPage({ id }: { id: string }) {
  const state = useAsync(() => api.get<Claim>(`/api/claims/${id}`), [id])
  return (
    <AsyncView state={state} label="Loading claim">
      {(c) => {
        const active = ['submitted', 'under_review', 'needs_more_info', 'approved'].includes(c.status)
        return (
          <>
            <PageHeader
              title={c.found_title ?? 'Your claim'}
              back={{ to: '/claims', label: 'My claims' }}
              subtitle={<StatusBadge status={c.status} />}
              actions={
                active ? (
                  <ConfirmButton
                    label="Withdraw claim"
                    question={c.status === 'approved' ? 'Withdraw and cancel the handover?' : 'Withdraw this claim?'}
                    confirmLabel="Withdraw"
                    onConfirm={async () => {
                      try {
                        await api.post(`/api/claims/${c.id}/withdraw`)
                        toast('Claim withdrawn.')
                        state.reload()
                      } catch (err) {
                        toast(errorMessage(err), 'danger')
                      }
                    }}
                  />
                ) : undefined
              }
            />
            <ClaimTimeline status={c.status} />

            {c.status === 'approved' && c.handover_code && (
              <Card className="code-card">
                <p className="eyebrow">Your one-time handover code</p>
                <p className="handover-code" aria-label={`Code: ${c.handover_code.split('').join(' ')}`}>
                  {groupCode(c.handover_code)}
                </p>
                <p>
                  Show this code at the campus lost-and-found desk with your campus ID. It works once and expires
                  48 hours after approval. Staff type it in — they never see it in the system.
                </p>
              </Card>
            )}
            {c.status === 'completed' && (
              <Alert tone="success" title="Collected">
                The handover is complete. We hope you enjoy having it back!
              </Alert>
            )}
            {c.status === 'rejected' && (
              <Alert tone="danger" title="Claim not approved">
                {c.decision_note ?? 'The moderator could not confirm ownership.'}
              </Alert>
            )}
            {c.status === 'expired' && (
              <Alert tone="warning" title="Code expired">
                The handover code was not used within 48 hours, so the item is available again.
              </Alert>
            )}

            {c.status === 'needs_more_info' && (
              <Card>
                <h2>The moderator needs more information</h2>
                {c.decision_note && <Alert tone="warning">{c.decision_note}</Alert>}
                <MoreInfoForm claim={c} prompts={Object.keys(c.answers ?? {})} onDone={state.reload} />
              </Card>
            )}

            <Card>
              <h2>What you submitted</h2>
              <p className="pre">{c.evidence}</p>
              {Object.keys(c.answers ?? {}).length > 0 && (
                <KeyValue items={Object.entries(c.answers ?? {}).map(([q, a]) => [q, String(a)])} />
              )}
              <p className="muted small">
                Submitted {formatDateTime(c.submitted_at)}
                {c.reviewed_at ? ` · reviewed ${formatDateTime(c.reviewed_at)}` : ''}
              </p>
            </Card>
          </>
        )
      }}
    </AsyncView>
  )
}
