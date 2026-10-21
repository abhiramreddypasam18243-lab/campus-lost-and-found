import { useEffect, useId, useMemo, useState } from 'react'
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

const KIND_LABEL: Record<string, string> = {
  campus: 'Campus',
  building: 'Building',
  floor: 'Floor',
  room: 'Room',
  area: 'Area',
}

/**
 * Cascading pickers: choose as precisely as you remember. Any level is valid (AC-20),
 * so "anywhere in <building>" is a real answer, and no GPS is ever asked for.
 */
export function LocationPicker({
  value,
  onChange,
  error,
  label = 'Where?',
}: {
  value: string
  onChange: (id: string) => void
  error?: string
  label?: string
}) {
  const state = useLocations()
  const baseId = useId()
  const index = useMemo(() => (state.data ? indexLocations(state.data) : null), [state.data])
  const [chain, setChain] = useState<string[]>([])

  // Keep the visible chain in sync with an externally provided value.
  useEffect(() => {
    if (!index) return
    const ids = pathOf(index, value).map((l) => l.id)
    setChain(ids)
  }, [index, value])

  if (state.loading && !index) return <p className="field-hint">Loading campus locations…</p>
  if (state.error || !index) {
    return (
      <p className="field-error" role="alert">
        Campus locations could not be loaded.{' '}
        <button type="button" className="link-btn" onClick={state.reload}>
          Retry
        </button>
      </p>
    )
  }

  const levels: { parent: string | null; options: Location[]; selected: string }[] = []
  let parent: string | null = null
  for (let depth = 0; ; depth++) {
    const options = index.children.get(parent) ?? []
    if (options.length === 0) break
    const selected = chain[depth] ?? ''
    levels.push({ parent, options, selected })
    if (!selected) break
    parent = selected
  }

  const errorId = `${baseId}-error`
  return (
    <fieldset className={`field fieldset ${error ? 'field-invalid' : ''}`} aria-describedby={error ? errorId : undefined}>
      <legend className="field-label">
        {label}
        <span className="req" aria-hidden="true"> *</span>
      </legend>
      <div className="cascade">
        {levels.map((level, depth) => {
          const parentLoc = level.parent ? index.byId.get(level.parent) : null
          const kind = level.options[0]?.kind ?? 'area'
          const selectId = `${baseId}-${depth}`
          return (
            <div key={selectId} className="cascade-level">
              <label htmlFor={selectId} className="sr-only">
                {KIND_LABEL[kind] ?? 'Location'}
              </label>
              <select
                id={selectId}
                className="input select"
                value={level.selected}
                aria-invalid={error && depth === 0 ? true : undefined}
                onChange={(e) => {
                  const next = e.target.value
                  const newChain = [...chain.slice(0, depth), ...(next ? [next] : [])]
                  setChain(newChain)
                  onChange(newChain[newChain.length - 1] ?? '')
                }}
              >
                <option value="">
                  {parentLoc ? `Anywhere in ${parentLoc.name}` : `Choose a ${(KIND_LABEL[kind] ?? 'location').toLowerCase()}…`}
                </option>
                {level.options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
          )
        })}
      </div>
      {error ? (
        <span id={errorId} className="field-error">
          {error}
        </span>
      ) : (
        <span className="field-hint">Pick as precisely as you remember — a building is fine.</span>
      )}
    </fieldset>
  )
}

/** Building options for filters (buildings with their campus for disambiguation). */
export function buildingOptions(index: LocationIndex): { id: string; label: string }[] {
  return [...index.byId.values()]
    .filter((l) => l.kind === 'building')
    .map((l) => ({ id: l.id, label: l.name }))
    .sort((a, b) => a.label.localeCompare(b.label))
}
