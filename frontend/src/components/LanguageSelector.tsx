import React, { useState } from 'react'
import { Language, SUPPORTED_LANGUAGES } from '../i18n/translations'

interface LanguageSelectorProps {
  currentLanguage: Language
  onSelectLanguage: (lang: Language) => void
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  currentLanguage,
  onSelectLanguage,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false)

  const activeLang =
    SUPPORTED_LANGUAGES.find((l) => l.code === currentLanguage) ||
    SUPPORTED_LANGUAGES[0]

  return (
    <div className="language-selector-wrapper" style={{ position: 'relative' }}>
      <button
        type="button"
        className="language-selector-btn"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label="Select Language"
      >
        <span className="lang-flag">{activeLang.flag}</span>
        <span className="lang-code-text">{activeLang.nativeName}</span>
        <span className="lang-arrow" style={{ fontSize: '0.7rem', opacity: 0.7 }}>
          {isOpen ? '▲' : '▼'}
        </span>
      </button>

      {isOpen && (
        <>
          <div
            className="language-menu-backdrop"
            onClick={() => setIsOpen(false)}
            style={{ position: 'fixed', inset: 0, zIndex: 1050 }}
          />
          <ul
            className="language-dropdown-menu"
            role="listbox"
            aria-label="Language choices"
          >
            {SUPPORTED_LANGUAGES.map((l) => {
              const isSelected = l.code === currentLanguage
              return (
                <li
                  key={l.code}
                  role="option"
                  aria-selected={isSelected}
                  className={`language-option-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    onSelectLanguage(l.code)
                    setIsOpen(false)
                  }}
                >
                  <span className="lang-flag">{l.flag}</span>
                  <div className="lang-labels">
                    <strong>{l.nativeName}</strong>
                    <small>{l.label}</small>
                  </div>
                  {isSelected && <span className="lang-check">✓</span>}
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )
}
