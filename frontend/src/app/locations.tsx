import { useId, useMemo } from 'react'
import { api, type Location } from './api'
import { useAsync } from './ui'

let cache: Promise<Location[]> | null = null

/** The campus tree changes rarely; load it once per page view. */
export function loadLocations(force = false): Promise<Location[]> {
  if (!cache || force) cache = api.get<Location[]>('/api/locations').catch((e) => {
    cache = null
    throw e
  })
  return cache
}

export function useLocations() {
  return useAsync(() => loadLocations(), [])
}

export type LocationIndex = {
  byId: Map<string, Location>
  children: Map<string | null, Location[]>
}

export function indexLocations(locations: Location[]): LocationIndex {
  const byId = new Map(locations.map((l) => [l.id, l]))
  const children = new Map<string | null, Location[]>()
  for (const l of locations) {
    const key = l.parent_id && byId.has(l.parent_id) ? l.parent_id : null
    children.set(key, [...(children.get(key) ?? []), l])
  }
  for (const list of children.values()) list.sort((a, b) => a.name.localeCompare(b.name))
  return { byId, children }
}

export function pathOf(index: LocationIndex, id: string | null | undefined): Location[] {
  const path: Location[] = []
  let cur = id ? index.byId.get(id) : undefined
  while (cur) {
    path.unshift(cur)
    cur = cur.parent_id ? index.byId.get(cur.parent_id) : undefined
  }
  return path
}

export function pathLabel(index: LocationIndex, id: string | null | undefined): string {
  return pathOf(index, id)
    .map((l) => l.name)
    .join(' › ')
}

/** linkedLabelOnly: the text is just the linked place's own name, so nothing extra to store. */
export type PlaceValue = { text: string; locationId: string; linkedLabelOnly?: boolean }

/** A report's place for the reporter and staff: the campus path, the typed words, or both. */
export function placeLabel(index: LocationIndex, locationId: string | null | undefined, text: string | null | undefined): string {
  const path = locationId ? pathLabel(index, locationId) : ''
  if (path && text) return `${path} — “${text}”`
  return path || (text ? `“${text}”` : '—')
}

/**
 * D-22: link the longest campus place the typed text starts with ("Library › Floor 2, by the
 * window" links Floor 2). Plain names count only when unique, so "Floor 1" never guesses a
 * building. Returns '' when nothing matches; the text is then saved as typed.
 */
export function matchPlace(index: LocationIndex, text: string): string {
  const typed = text.trim().toLowerCase()
  if (!typed) return ''
  const nameCount = new Map<string, number>()
  for (const l of index.byId.values()) nameCount.set(l.name.toLowerCase(), (nameCount.get(l.name.toLowerCase()) ?? 0) + 1)
  let best = { id: '', len: 0 }
  for (const l of index.byId.values()) {
    const labels = [pathLabel(index, l.id).toLowerCase()]
    if (nameCount.get(l.name.toLowerCase()) === 1) labels.push(l.name.toLowerCase())
    for (const label of labels) {
      const next = typed.charAt(label.length)
      if (typed.startsWith(label) && (next === '' || !/[\p{L}\p{N}]/u.test(next)) && label.length > best.len) {
        best = { id: l.id, len: label.length }
      }
    }
  }
  return best.id
}

/**
 * "Where?" as free text with campus suggestions (D-22). Picking or starting with a known place
 * links it, which helps matching; anything else is kept as typed and shown only to the reporter
 * and staff. No GPS is ever asked for.
 */
export function PlaceField({
  value,
  onChange,
  error,
  label,
}: {
  value: PlaceValue
  onChange: (v: PlaceValue) => void
  error?: string
  label: string
}) {
  const state = useLocations()
  const baseId = useId()
  const index = useMemo(() => (state.data ? indexLocations(state.data) : null), [state.data])
  const suggestions = useMemo(
    () => (index ? [...index.byId.keys()].map((id) => pathLabel(index, id)).sort((a, b) => a.localeCompare(b)) : []),
    [index],
  )
  const inputId = `${baseId}-input`
  const listId = `${baseId}-places`
  const statusId = `${baseId}-status`
  const linked = value.locationId && index ? pathLabel(index, value.locationId) : ''

  return (
    <div className={`field ${error ? 'field-invalid' : ''}`}>
      <label htmlFor={inputId} className="field-label">
        {label}
        <span className="req" aria-hidden="true"> *</span>
      </label>
      <input
        id={inputId}
        className="input"
        list={listId}
        autoComplete="off"
        maxLength={200}
        placeholder="e.g. Library › Floor 2, or “bench outside the canteen”"
        value={value.text}
        aria-invalid={error ? true : undefined}
        aria-describedby={statusId}
        onChange={(e) => {
          const text = e.target.value
          const locationId = index ? matchPlace(index, text) : ''
          const typed = text.trim().toLowerCase()
          const own = locationId && index ? [pathLabel(index, locationId), index.byId.get(locationId)?.name ?? ''] : []
          onChange({ text, locationId, linkedLabelOnly: own.some((l) => l.toLowerCase() === typed) })
        }}
      />
      <datalist id={listId}>
        {suggestions.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      <span id={statusId} className={error ? 'field-error' : 'field-hint'} aria-live="polite">
        {error
          ? error
          : linked
            ? `Linked to ${linked} — this helps us find matches.`
            : value.text.trim()
              ? 'Saved as you typed it. Start with a suggested place to also link it for matching.'
              : state.error
                ? 'Campus places could not be loaded — just type where it was.'
                : 'Type anything, or pick a campus place from the suggestions. Only you and campus staff see what you type.'}
      </span>
    </div>
  )
}

/** Building options for filters (buildings with their campus for disambiguation). */
export function buildingOptions(index: LocationIndex): { id: string; label: string }[] {
  return [...index.byId.values()]
    .filter((l) => l.kind === 'building')
    .map((l) => ({ id: l.id, label: l.name }))
    .sort((a, b) => a.label.localeCompare(b.label))
}
