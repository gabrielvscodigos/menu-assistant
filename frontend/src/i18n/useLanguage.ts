import { useCallback, useState } from 'react'
import type { Language } from '../api/client'
import { DEFAULT_LANGUAGE, LANGUAGES } from './messages'

const STORAGE_KEY = 'menu-assistant.language'

/** The language the guest chose, remembered in this browser (English until they pick). */
export function useLanguage(): [Language, (language: Language) => void] {
  const [language, setLanguageState] = useState<Language>(readStoredLanguage)

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Storage can be unavailable (private mode, blocked site data): keep it in memory.
    }
  }, [])

  return [language, setLanguage]
}

function readStoredLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return LANGUAGES.find((language) => language === stored) ?? DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}
