import type { ReactNode } from 'react'

/* Line icons for the fixed category list (spec 5.7), drawn on a 24px grid in currentColor. */
const CATEGORY_SHAPES: Record<string, ReactNode> = {
  bottle: (
    <>
      <path d="M10 2h4v3l1.5 2.5V20a2 2 0 0 1-2 2h-3a2 2 0 0 1-2-2V7.5L10 5z" />
      <path d="M8.5 11h7" />
    </>
  ),
  bag: (
    <>
      <path d="M6 10a6 6 0 0 1 12 0v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2z" />
      <path d="M9 6.5V4a3 3 0 0 1 6 0v2.5" />
      <path d="M9 14h6v4H9z" />
    </>
  ),
  wallet: (
    <>
      <path d="M18 5H5a2 2 0 0 0 0 4h15v11H5a2 2 0 0 1-2-2V7" />
      <circle cx="16" cy="14.5" r="1" />
    </>
  ),
  phone: (
    <>
      <rect x="7" y="2" width="10" height="20" rx="2" />
      <path d="M11 18h2" />
    </>
  ),
  laptop_tablet: (
    <>
      <rect x="4" y="4" width="16" height="11" rx="1.5" />
      <path d="M2 19h20" />
    </>
  ),
  earphones: (
    <>
      <path d="M3 15v-3a9 9 0 0 1 18 0v3" />
      <rect x="3" y="14" width="4" height="7" rx="1.5" />
      <rect x="17" y="14" width="4" height="7" rx="1.5" />
    </>
  ),
  keys: (
    <>
      <circle cx="8" cy="15" r="4" />
      <path d="M10.8 12.2L20 3" />
      <path d="M17 6l3 3" />
      <path d="M14.5 8.5l2 2" />
    </>
  ),
  id_card: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="9" cy="11" r="2" />
      <path d="M6 16c.6-1.4 1.7-2 3-2s2.4.6 3 2" />
      <path d="M14.5 10h4M14.5 14h4" />
    </>
  ),
  clothing: <path d="M8 3l4 2 4-2 5 4-3 4-2-1v11H8V10l-2 1-3-4z" />,
  book: (
    <>
      <path d="M2 5h7a3 3 0 0 1 3 3v12a2.5 2.5 0 0 0-2.5-2.5H2z" />
      <path d="M22 5h-7a3 3 0 0 0-3 3v12a2.5 2.5 0 0 1 2.5-2.5H22z" />
    </>
  ),
  accessory: (
    <>
      <circle cx="12" cy="12" r="5" />
      <path d="M9 7.5L9.7 3h4.6l.7 4.5M9 16.5l.7 4.5h4.6l.7-4.5" />
      <path d="M12 10v2l1.2 1.2" />
    </>
  ),
  other: (
    <>
      <path d="M3 7.5l9-4.5 9 4.5v9L12 21l-9-4.5z" />
      <path d="M3 7.5l9 4.5 9-4.5" />
      <path d="M12 12v9" />
    </>
  ),
}

export function CategoryIcon({ category, size = 24 }: { category: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {CATEGORY_SHAPES[category] ?? CATEGORY_SHAPES.other}
    </svg>
  )
}

export function LockIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  )
}
