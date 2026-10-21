/**
 * Typed API client. All types come from the backend OpenAPI document (AC-133):
 * `npm run gen:api` regenerates src/api/schema.d.ts from src/api/openapi.json.
 */
import type { components } from '../api/schema'

export type Schemas = components['schemas']
export type User = Schemas['UserResponse']
export type Report = Schemas['ReportResponse']
export type StaffReport = Schemas['FullStaffReportResponse']
export type PublicReport = Schemas['PublicReportDetailResponse']
export type FoundSummary = Schemas['PublicFoundItemSummary']
export type FoundList = Schemas['PublicFoundItemListResponse']
export type Location = Schemas['LocationResponse']
export type Adjacency = Schemas['AdjacencyResponse']
export type Match = Schemas['MatchCandidateResponse']
export type MatchList = Schemas['MatchListResponse']
export type Claim = Schemas['ClaimResponse']
export type ClaimForm = Schemas['ClaimFormResponse']
export type QueueItem = Schemas['ModeratorQueueItem']
export type QueueResponse = Schemas['ModeratorQueueResponse']
export type DeskItem = Schemas['HandoverDeskItem']
export type HandoverStatus = Schemas['HandoverStatusResponse']
export type HandoverVerify = Schemas['HandoverVerifyResponse']
export type Notification = Schemas['NotificationResponse']
export type NotificationList = Schemas['NotificationListResponse']
export type Dashboard = Schemas['DashboardMetricsResponse']
export type AdminUser = Schemas['AdminUserResponse']
export type AdminJob = Schemas['AdminJobResponse']
export type ModelEntry = Schemas['ModelRegistryResponse']
export type Evaluation = Schemas['AdminEvaluationResponse']
export type ImageInfo = Schemas['ImageResponse']
export type TimePrecision = Schemas['CreateLostReportRequest']['time_precision']

/** An API failure with the server's error code and any per-field messages. */
export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string>
  retryAfter: number | null
  details: Record<string, unknown>

  constructor(
    status: number,
    code: string,
    message: string,
    fields: Record<string, string> = {},
    retryAfter: number | null = null,
    details: Record<string, unknown> = {},
  ) {
    super(message)
    this.status = status
    this.code = code
    this.fields = fields
    this.retryAfter = retryAfter
    this.details = details
  }
}

const CSRF_KEY = 'campus_csrf'

function readCsrf(): string | null {
  try {
    return sessionStorage.getItem(CSRF_KEY)
  } catch {
    return null
  }
}

export function setCsrf(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(CSRF_KEY, token)
    else sessionStorage.removeItem(CSRF_KEY)
  } catch {
    // storage unavailable (private mode): the token lives only for this page load
  }
  memoryCsrf = token
}

let memoryCsrf: string | null = readCsrf()

export function hasCsrf(): boolean {
  return Boolean(memoryCsrf)
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string }

async function toApiError(res: Response): Promise<ApiError> {
  const retryHeader = res.headers.get('Retry-After')
  const retryAfter = retryHeader ? Number(retryHeader) : null
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    body = null
  }
  const detail = (body as { detail?: unknown } | null)?.detail

  if (Array.isArray(detail)) {
    // FastAPI/Pydantic validation errors: map each to its field name.
    const fields: Record<string, string> = {}
    for (const issue of detail as ValidationIssue[]) {
      const loc = issue.loc ?? []
      const name = String(loc[loc.length - 1] ?? 'form')
      if (!fields[name]) fields[name] = (issue.msg ?? 'Invalid value').replace(/^Value error, /, '')
    }
    return new ApiError(res.status, 'validation_error', 'Please correct the highlighted fields.', fields, retryAfter)
  }
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>
    const code = String(d.code ?? `http_${res.status}`)
    const fields: Record<string, string> = {}
    if (typeof d.field === 'string') fields[d.field] = String(d.message ?? code)
    return new ApiError(res.status, code, String(d.message ?? code), fields, retryAfter, d)
  }
  if (typeof detail === 'string') {
    return new ApiError(res.status, detail, detail, {}, retryAfter)
  }
  return new ApiError(res.status, `http_${res.status}`, res.statusText || 'Request failed', {}, retryAfter)
}

async function refreshCsrf(): Promise<boolean> {
  const res = await fetch('/api/auth/csrf', { credentials: 'same-origin' })
  if (!res.ok) return false
  const data = (await res.json()) as { csrf_token: string }
  setCsrf(data.csrf_token)
  return true
}

type Body = Record<string, unknown> | FormData | undefined

async function request<T>(method: string, path: string, body?: Body, retried = false): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const isForm = body instanceof FormData
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && memoryCsrf) headers['X-CSRF-Token'] = memoryCsrf

  const res = await fetch(path, {
    method,
    headers,
    credentials: 'same-origin',
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await toApiError(res)
    // The CSRF token lives in this tab only; after a reload, fetch a fresh one once.
    if (err.code === 'csrf_failed' && !retried && (await refreshCsrf())) {
      return request<T>(method, path, body, true)
    }
    throw err
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: Body) => request<T>('POST', path, body ?? {}),
  patch: <T>(path: string, body?: Body) => request<T>('PATCH', path, body ?? {}),
  del: <T>(path: string) => request<T>('DELETE', path),
  refreshCsrf,
}

/** Build a query string, skipping empty values. */
export function qs(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') search.set(k, String(v))
  }
  const s = search.toString()
  return s ? `?${s}` : ''
}
