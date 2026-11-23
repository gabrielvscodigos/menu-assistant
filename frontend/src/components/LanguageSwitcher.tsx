import type { Language } from '../api/client'
import { LANGUAGES, MESSAGES } from '../i18n/messages'

interface LanguageSwitcherProps {
  language: Language
  onChange: (language: Language) => void
}

/** EN / PT / ES option buttons; the pressed one is the language the mascot speaks. */
export function LanguageSwitcher({ language, onChange }: LanguageSwitcherProps) {
  return (
    <fieldset className="flex rounded-full border border-stone-300 bg-white p-0.5 text-xs font-semibold dark:border-stone-600 dark:bg-stone-800">
      <legend className="sr-only">{MESSAGES[language].languageLabel}</legend>
      {LANGUAGES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={option === language}
          title={MESSAGES[option].languageName}
          onClick={() => onChange(option)}
          className="rounded-full px-2.5 py-1 uppercase text-stone-600 transition-colors hover:text-stone-900 aria-pressed:bg-amber-500 aria-pressed:text-white dark:text-stone-300"
        >
          {option}
        </button>
      ))}
    </fieldset>
  )
}
