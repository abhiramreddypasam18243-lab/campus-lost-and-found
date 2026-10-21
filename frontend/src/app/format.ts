import { ApiError, type TimePrecision } from './api'

/** The fixed category list (spec 5.7) with readable labels. */
export const CATEGORIES: { id: string; label: string; icon: string }[] = [
  { id: 'bottle', label: 'Bottle', icon: '🧴' },
  { id: 'bag', label: 'Bag', icon: '🎒' },
  { id: 'wallet', label: 'Wallet', icon: '👛' },
  { id: 'phone', label: 'Phone', icon: '📱' },
  { id: 'laptop_tablet', label: 'Laptop / tablet', icon: '💻' },
  { id: 'earphones', label: 'Earphones', icon: '🎧' },
  { id: 'keys', label: 'Keys', icon: '🔑' },
  { id: 'id_card', label: 'ID card', icon: '🪪' },
  { id: 'clothing', label: 'Clothing', icon: '🧥' },
  { id: 'book', label: 'Book', icon: '📘' },
  { id: 'accessory', label: 'Accessory', icon: '⌚' },
  { id: 'other', label: 'Other', icon: '📦' },
]

/** S4: these categories never show photos publicly. */
export const SENSITIVE_CATEGORIES = new Set(['id_card', 'wallet'])

export function categoryLabel(id: string): string {
  return CATEGORIES.find((c) => c.id === id)?.label ?? id
}

export function categoryIcon(id: string): string {
  return CATEGORIES.find((c) => c.id === id)?.icon ?? '📦'
}

export const PRECISIONS: { id: TimePrecision; label: string }[] = [
  { id: 'exact', label: 'At an exact time' },
  { id: 'morning', label: 'Morning (06:00–12:00)' },
  { id: 'afternoon', label: 'Afternoon (12:00–17:00)' },
  { id: 'evening', label: 'Evening (17:00–22:00)' },
  { id: 'night', label: 'Night (22:00–06:00)' },
  { id: 'day', label: 'Sometime that day' },
]

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

/** Every status shows as text plus a tone, so colour never carries meaning alone. */
const STATUS: Record<string, { label: string; tone: Tone }> = {
  pending_review: { label: 'Awaiting review', tone: 'warning' },
  open: { label: 'Open', tone: 'info' },
  reserved: { label: 'Reserved', tone: 'warning' },
  returned: { label: 'Returned', tone: 'success' },
  resolved: { label: 'Resolved', tone: 'success' },
  unclaimed_expired: { label: 'Unclaimed', tone: 'neutral' },
  expired: { label: 'Expired', tone: 'neutral' },
  closed: { label: 'Closed', tone: 'neutral' },
  removed: { label: 'Removed', tone: 'danger' },
  submitted: { label: 'Submitted', tone: 'info' },
  under_review: { label: 'Under review', tone: 'warning' },
  needs_more_info: { label: 'More info needed', tone: 'warning' },
  approved: { label: 'Approved', tone: 'success' },
  rejected: { label: 'Rejected', tone: 'danger' },
  completed: { label: 'Collected', tone: 'success' },
  withdrawn: { label: 'Withdrawn', tone: 'neutral' },
  issued: { label: 'Waiting at desk', tone: 'info' },
  locked: { label: 'Locked', tone: 'danger' },
  used: { label: 'Used', tone: 'success' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
  flagged: { label: 'Flagged', tone: 'warning' },
  pending: { label: 'Pending', tone: 'info' },
  running: { label: 'Running', tone: 'info' },
  failed: { label: 'Failed', tone: 'danger' },
  suggested: { label: 'Suggested', tone: 'info' },
  dismissed: { label: 'Dismissed', tone: 'neutral' },
}

export function statusInfo(status: string): { label: string; tone: Tone } {
  return STATUS[status] ?? { label: status.replace(/_/g, ' '), tone: 'neutral' }
}

const BIN_TONE: Record<string, Tone> = { high: 'success', medium: 'warning', low: 'neutral' }
export function binTone(bin: string): Tone {
  return BIN_TONE[bin] ?? 'neutral'
}

const PII_KIND: Record<string, string> = {
  card_number: 'a card number',
  long_number: 'a long number (9+ digits)',
  phone: 'a phone number',
  email: 'an email address',
}

/** Human messages for the backend's error codes. */
const MESSAGES: Record<string, string> = {
  invalid_credentials: 'That email and password do not match an account.',
  email_domain_not_allowed: 'Use your campus email address to register.',
  email_already_registered: 'An account with this email already exists. Try signing in.',
  email_not_verified: 'Verify your campus email first. Check your inbox for the link.',
  tls_required: 'Signing in from another device needs the secure (https) address.',
  csrf_failed: 'Your session expired. Please sign in again.',
  unauthorized: 'Please sign in to continue.',
  forbidden: 'You do not have access to this page.',
  report_not_found: 'This item does not exist or is not visible to you.',
  location_not_found: 'Choose a campus location from the list.',
  invalid_transition: 'That action is not possible in the item’s current state.',
  item_reserved: 'This item is reserved for another claim right now.',
  conflict_of_interest: 'You cannot decide a claim on an item you reported or claimed.',
  handover_locked: 'Too many wrong codes. The handover is locked until it is reissued.',
  invalid_code: 'That code is not right.',
  identity_note_too_short: 'Record how you checked identity (at least 10 characters).',
  code_used: 'This code was already used.',
  code_expired: 'This code has expired.',
  image_too_large: 'That image is too large (over 6,000 × 6,000 pixels).',
  unsupported_media_type: 'Only JPEG, PNG or WebP photos can be uploaded.',
  too_many_images: 'A report can have at most 3 photos.',
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'pii_detected') {
      const kind = PII_KIND[String(err.details.kind)] ?? 'contact details'
      const field = String(err.details.field ?? 'text')
      return `The ${field} looks like it contains ${kind}. Public fields cannot include contact details or long numbers. Put them in the private details instead.`
    }
    if (err.status === 429) {
      const wait = err.retryAfter ? ` Try again in ${Math.ceil(err.retryAfter / 60)} min.` : ''
      return `Too many attempts.${wait}`
    }
    if (err.status === 413) return 'That file or request is too large (photos up to 5 MB).'
    if (err.status === 415) return MESSAGES.unsupported_media_type
    if (MESSAGES[err.code]) return MESSAGES[err.code]
    if (err.code === 'validation_error') return err.message
    if (err.status === 404) return MESSAGES.report_not_found
    if (err.status >= 500) return 'Something went wrong on the server. Please try again.'
    return err.message.replace(/_/g, ' ')
  }
  if (err instanceof TypeError) return 'Cannot reach the server. Check your connection.'
  return 'Something went wrong. Please try again.'
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function timeAgo(iso: string): string {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m} min ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} h ago`
  const d = Math.round(h / 24)
  return `${d} day${d === 1 ? '' : 's'} ago`
}

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function todayISO(): string {
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
}

/** Handover codes are shown to the claimant grouped as XXXX-XXXX for reading aloud. */
export function groupCode(code: string): string {
  return code.length === 8 ? `${code.slice(0, 4)}-${code.slice(4)}` : code
}
