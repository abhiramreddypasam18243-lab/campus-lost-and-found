/**
 * Shared UI building blocks. Accessibility rules (spec 11): every field has a label, errors are
 * linked with aria-describedby, statuses carry text (not colour alone), and every async screen
 * has loading, empty and error states.
 */
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { errorMessage, statusInfo, type Tone } from './format'
import { StateIcon, type StateIconName } from './icons'

/* ---------- data loading ---------- */

export type Async<T> = {
  data: T | null
  error: unknown
  loading: boolean
  reload: () => void
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): Async<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const loadRef = useRef(load)
  loadRef.current = load

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    loadRef
      .current()
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}

/** Renders loading / error / empty / content for an Async value. */
export function AsyncView<T>({
  state,
  empty,
  isEmpty,
  children,
  label = 'Loading',
}: {
  state: Async<T>
  empty?: ReactNode
  isEmpty?: (data: T) => boolean
  children: (data: T) => ReactNode
  label?: string
}) {
  if (state.loading && state.data === null) return <Loading label={label} />
  if (state.error && state.data === null) return <ErrorState error={state.error} onRetry={state.reload} />
  if (state.data === null) return null
  if (isEmpty?.(state.data) && empty) return <>{empty}</>
  return <>{children(state.data)}</>
}

/* ---------- feedback ---------- */

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <div className="state-icon" aria-hidden="true">⚠️</div>
      <p className="state-title">Something didn’t load</p>
      <p className="state-text">{errorMessage(error)}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({
  icon = 'search',
  title,
  children,
  action,
}: {
  icon?: StateIconName
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="state">
      <div className="state-icon" aria-hidden="true">
        <StateIcon name={icon} />
      </div>
      <p className="state-title">{title}</p>
      {children && <div className="state-text">{children}</div>}
      {action}
    </div>
  )
}

export function Alert({
  tone = 'info',
  title,
  children,
}: {
  tone?: Tone
  title?: string
  children: ReactNode
}) {
  return (
    <div className={`alert alert-${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      {title && <strong className="alert-title">{title}</strong>}
      <div>{children}</div>
    </div>
  )
}

export function FormError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <Alert tone="danger" title="Couldn’t save">
      {errorMessage(error)}
    </Alert>
  )
}

/* ---------- toasts ---------- */

type ToastMsg = { id: number; text: string; tone: Tone }
let pushToast: (text: string, tone?: Tone) => void = () => {}

export function toast(text: string, tone: Tone = 'success') {
  pushToast(text, tone)
}

export function ToastHost() {
  const [items, setItems] = useState<ToastMsg[]>([])
  useEffect(() => {
    pushToast = (text, tone = 'success') => {
      const id = Date.now() + Math.random()
      setItems((xs) => [...xs, { id, text, tone }])
      window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 3500)
    }
  }, [])
  return (
    <div className="toasts" aria-live="polite" aria-atomic="false">
      {items.map((t) => (
        <div key={t.id} className={`toast toast-${t.tone}`} role="status">
          {t.text}
        </div>
      ))}
    </div>
  )
}

/* ---------- primitives ---------- */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'md' | 'sm'
  busy?: boolean
}

export function Button({
  variant = 'primary',
  size = 'md',
  busy = false,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`btn btn-${variant} btn-${size} ${className}`}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    >
      {busy && <span className="spinner spinner-sm" aria-hidden="true" />}
      {children}
    </button>
  )
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function StatusBadge({ status }: { status: string }) {
  const info = statusInfo(status)
  return <Badge tone={info.tone}>{info.label}</Badge>
}

export function Card({
  children,
  className = '',
  as: Tag = 'section',
}: {
  children: ReactNode
  className?: string
  as?: 'section' | 'article' | 'div'
}) {
  return <Tag className={`card ${className}`}>{children}</Tag>
}

export function PageHeader({
  title,
  subtitle,
  actions,
  back,
}: {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
  back?: { to: string; label: string }
}) {
  return (
    <header className="page-header">
      <div>
        {back && (
          <a className="back-link" href={`#${back.to}`}>
            ← {back.label}
          </a>
        )}
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

/* ---------- form fields ---------- */

type FieldShellProps = {
  id: string
  label: string
  hint?: ReactNode
  error?: string
  required?: boolean
  counter?: { value: number; max: number }
  children: ReactNode
}

function FieldShell({ id, label, hint, error, required, counter, children }: FieldShellProps) {
  return (
    <div className={`field ${error ? 'field-invalid' : ''}`}>
      <label htmlFor={id} className="field-label">
        {label}
        {required && <span className="req" aria-hidden="true"> *</span>}
      </label>
      {children}
      <div className="field-meta">
        {error ? (
          <span id={`${id}-error`} className="field-error">
            {error}
          </span>
        ) : hint ? (
          <span id={`${id}-hint`} className="field-hint">
            {hint}
          </span>
        ) : (
          <span />
        )}
        {counter && (
          <span className={`field-counter ${counter.value > counter.max ? 'over' : ''}`} aria-hidden="true">
            {counter.value}/{counter.max}
          </span>
        )}
      </div>
    </div>
  )
}

function describedBy(id: string, error?: string, hint?: ReactNode) {
  return error ? `${id}-error` : hint ? `${id}-hint` : undefined
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: ReactNode
  error?: string
  showCount?: boolean
}

export function TextField({ label, hint, error, showCount, id, required, maxLength, ...rest }: TextFieldProps) {
  const auto = useId()
  const fid = id ?? auto
  const len = typeof rest.value === 'string' ? rest.value.length : 0
  return (
    <FieldShell
      id={fid}
      label={label}
      hint={hint}
      error={error}
      required={required}
      counter={showCount && maxLength ? { value: len, max: maxLength } : undefined}
    >
      <input
        id={fid}
        className="input"
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fid, error, hint)}
        {...rest}
      />
    </FieldShell>
  )
}

type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string
  hint?: ReactNode
  error?: string
  max?: number
}

export function TextArea({ label, hint, error, id, required, max, rows = 4, ...rest }: TextAreaProps) {
  const auto = useId()
  const fid = id ?? auto
  const len = typeof rest.value === 'string' ? rest.value.length : 0
  return (
    <FieldShell
      id={fid}
      label={label}
      hint={hint}
      error={error}
      required={required}
      counter={max ? { value: len, max } : undefined}
    >
      <textarea
        id={fid}
        className="input textarea"
        rows={rows}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fid, error, hint)}
        {...rest}
      />
    </FieldShell>
  )
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string
  hint?: ReactNode
  error?: string
  children: ReactNode
}

export function SelectField({ label, hint, error, id, required, children, ...rest }: SelectProps) {
  const auto = useId()
  const fid = id ?? auto
  return (
    <FieldShell id={fid} label={label} hint={hint} error={error} required={required}>
      <select
        id={fid}
        className="input select"
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fid, error, hint)}
        {...rest}
      >
        {children}
      </select>
    </FieldShell>
  )
}

/** A confirm step inline (no window.confirm), keeping focus on the page. */
export function ConfirmButton({
  label,
  confirmLabel,
  question,
  onConfirm,
  variant = 'secondary',
  size = 'md',
}: {
  label: string
  confirmLabel: string
  question: string
  onConfirm: () => Promise<void> | void
  variant?: ButtonProps['variant']
  size?: ButtonProps['size']
}) {
  const [asking, setAsking] = useState(false)
  const [busy, setBusy] = useState(false)
  if (!asking) {
    return (
      <Button variant={variant} size={size} onClick={() => setAsking(true)}>
        {label}
      </Button>
    )
  }
  return (
    <span className="confirm" role="group" aria-label={question}>
      <span className="confirm-q">{question}</span>
      <Button
        variant="danger"
        size={size}
        busy={busy}
        autoFocus
        onClick={async () => {
          setBusy(true)
          try {
            await onConfirm()
          } finally {
            setBusy(false)
            setAsking(false)
          }
        }}
      >
        {confirmLabel}
      </Button>
      <Button variant="ghost" size={size} onClick={() => setAsking(false)}>
        Cancel
      </Button>
    </span>
  )
}

export function KeyValue({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v]) => (
        <div key={k} className="kv-row">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  label,
}: {
  tabs: { id: T; label: string; count?: number }[]
  active: T
  onChange: (id: T) => void
  label: string
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={t.id === active}
          className={`tab ${t.id === active ? 'tab-active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.count !== undefined && <span className={`tab-count ${t.count > 0 ? 'tab-count-on' : ''}`}>{t.count}</span>}
        </button>
      ))}
    </div>
  )
}
