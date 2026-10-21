import { useCallback, useEffect, useState } from 'react'
import { api, qs, type Notification, type NotificationList, type User } from '../api'
import { useAuth } from '../auth'
import { errorMessage, statusInfo, timeAgo } from '../format'
import { navigate } from '../router'
import {
  Alert,
  Button,
  Card,
  ConfirmButton,
  EmptyState,
  ErrorState,
  FormError,
  KeyValue,
  Loading,
  PageHeader,
  Tabs,
  TextField,
  toast,
} from '../ui'

/** Plain-language text for a notification. Uses only the whitelisted payload fields (AC-71). */
export function describeNotification(n: Notification): { text: string; to: string | null } {
  const p = n.payload as Record<string, unknown>
  const title = String(p.found_title ?? p.title ?? 'an item')
  switch (n.event_type) {
    case 'match_suggested':
      return {
        text: `Possible match for your lost item: “${title}”.`,
        to: p.lost_id ? `/reports/${String(p.lost_id)}` : '/reports',
      }
    case 'claim_update': {
      const s = String(p.claim_status ?? 'updated')
      return { text: `Your claim on “${title}” is now: ${statusInfo(s).label.toLowerCase()}.`, to: '/claims' }
    }
    case 'handover_ready':
      return {
        text: `Your claim on “${title}” was approved. Open the claim to see your handover code.`,
        to: p.claim_id ? `/claims/${String(p.claim_id)}` : '/claims',
      }
    default:
      return { text: 'You have an update.', to: null }
  }
}

let unreadListeners: ((n: number) => void)[] = []

export function useUnreadCount(enabled: boolean): number {
  const [count, setCount] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let stop = false
    const load = () =>
      api
        .get<NotificationList>(`/api/notifications${qs({ status: 'unread', limit: 100 })}`)
        .then((r) => !stop && setCount(r.items.length))
        .catch(() => {})
    void load()
    const timer = window.setInterval(load, 30000)
    unreadListeners.push(setCount)
    return () => {
      stop = true
      window.clearInterval(timer)
      unreadListeners = unreadListeners.filter((l) => l !== setCount)
    }
  }, [enabled])
  return count
}

function announceUnread(n: number) {
  unreadListeners.forEach((l) => l(n))
}

type Filter = 'all' | 'unread'

export function NotificationsPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const [items, setItems] = useState<Notification[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)

  const load = useCallback(
    async (after: string | null) => {
      setLoading(true)
      setError(null)
      try {
        const res = await api.get<NotificationList>(`/api/notifications${qs({ status: filter, limit: 20, cursor: after })}`)
        setItems((xs) => (after ? [...xs, ...res.items] : res.items))
        setCursor(res.next_cursor)
      } catch (err) {
        setError(err)
      } finally {
        setLoading(false)
      }
    },
    [filter],
  )

  useEffect(() => {
    void load(null)
  }, [load])

  const markRead = async (n: Notification) => {
    if (n.read_at) return
    try {
      const updated = await api.post<Notification>(`/api/notifications/${n.id}/read`)
      const next = items.map((x) => (x.id === n.id ? updated : x))
      setItems(filter === 'unread' ? next.filter((x) => !x.read_at) : next)
      announceUnread(next.filter((x) => !x.read_at).length)
    } catch (err) {
      toast(errorMessage(err), 'danger')
    }
  }

  return (
    <>
      <PageHeader title="Notifications" />
      <Tabs
        label="Filter notifications"
        tabs={[
          { id: 'all', label: 'All' },
          { id: 'unread', label: 'Unread' },
        ]}
        active={filter}
        onChange={setFilter}
      />
      {error !== null && items.length === 0 ? (
        <ErrorState error={error} onRetry={() => load(null)} />
      ) : loading && items.length === 0 ? (
        <Loading label="Loading notifications" />
      ) : items.length === 0 ? (
        <EmptyState icon="🔔" title={filter === 'unread' ? 'You’re all caught up' : 'No notifications yet'}>
          Match suggestions and claim updates appear here.
        </EmptyState>
      ) : (
        <div className="list">
          {items.map((n) => {
            const d = describeNotification(n)
            return (
              <div key={n.id} className={`list-row notif ${n.read_at ? '' : 'notif-unread'}`}>
                <span className="notif-dot" aria-hidden="true" />
                <div className="list-main">
                  <div>
                    {!n.read_at && <span className="sr-only">Unread: </span>}
                    {d.text}
                  </div>
                  <div className="muted small">{timeAgo(n.created_at)}</div>
                </div>
                <div className="list-side">
                  {d.to && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={async () => {
                        await markRead(n)
                        navigate(d.to as string)
                      }}
                    >
                      Open
                    </Button>
                  )}
                  {!n.read_at && (
                    <Button variant="ghost" size="sm" onClick={() => markRead(n)}>
                      Mark read
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
          {cursor && (
            <div className="center">
              <Button variant="secondary" busy={loading} onClick={() => load(cursor)}>
                Load more
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  )
}

export function AccountPage() {
  const { user, setUser, logout } = useAuth()
  const [name, setName] = useState(user?.display_name ?? '')
  const [notify, setNotify] = useState(user?.notify_match_email ?? true)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  if (!user) return null

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      const updated = await api.patch<User>('/api/me', { display_name: name, notify_match_email: notify })
      setUser(updated)
      toast('Preferences saved.')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const exportData = async () => {
    try {
      const data = await api.get<unknown>('/api/me/export')
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'my-campus-lost-and-found-data.json'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast(errorMessage(err), 'danger')
    }
  }

  return (
    <>
      <PageHeader title="Account" subtitle="We store only your campus email and an optional display name." />
      <div className="grid-2">
        <Card>
          <h2>Profile</h2>
          <KeyValue
            items={[
              ['Email', user.email],
              ['Role', user.role],
              ['Email verified', user.email_verified ? 'Yes' : 'Not yet — check your inbox'],
            ]}
          />
          <FormError error={error} />
          <TextField label="Display name" maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
          <label className="check">
            <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
            <span>
              Email me about match suggestions
              <span className="field-hint block">Claim and handover emails are always sent. Match alerts also appear in-app.</span>
            </span>
          </label>
          <Button onClick={save} busy={busy}>
            Save
          </Button>
        </Card>
        <Card>
          <h2>Your data</h2>
          <p className="muted">Download everything we hold about you: your reports, claims, evidence and notifications.</p>
          <Button variant="secondary" onClick={exportData}>
            Download my data (JSON)
          </Button>
          <hr />
          <h3>Delete account</h3>
          <Alert tone="warning">
            Deletes your email, name, sessions, notifications, private photos and claim evidence. Your reports are
            anonymised and closed. This cannot be undone.
          </Alert>
          <ConfirmButton
            label="Delete my account"
            question="Permanently delete your account?"
            confirmLabel="Yes, delete"
            variant="danger"
            onConfirm={async () => {
              try {
                await api.del('/api/me')
                await logout().catch(() => {})
                toast('Your account was deleted.')
                navigate('/login')
              } catch (err) {
                toast(errorMessage(err), 'danger')
              }
            }}
          />
        </Card>
      </div>
    </>
  )
}
