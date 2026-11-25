import { type FormEvent, type KeyboardEvent, useState } from 'react'

interface ComposerProps {
  placeholder: string
  sendLabel: string
  disabled: boolean
  onSend: (question: string) => void
}

/** The question box. Enter sends; Shift+Enter adds a new line. */
export function Composer({ placeholder, sendLabel, disabled, onSend }: ComposerProps) {
  const [question, setQuestion] = useState('')
  const canSend = !disabled && question.trim() !== ''

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (canSend) {
      onSend(question)
      setQuestion('')
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      submit(event)
    }
  }

  return (
    <form onSubmit={submit} className="flex items-end gap-2">
      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        aria-label={placeholder}
        rows={1}
        maxLength={500}
        className="max-h-40 min-h-11 flex-1 resize-none rounded-3xl border border-stone-300 bg-white px-4 py-2.5 text-base text-stone-900 sm:text-sm shadow-sm outline-none focus:border-red-600 focus:ring-2 focus:ring-red-200 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100 dark:focus:ring-red-800"
      />
      <button
        type="submit"
        disabled={!canSend}
        className="h-11 rounded-full bg-red-600 px-5 font-semibold text-white shadow-sm transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-stone-300 dark:disabled:bg-stone-700"
      >
        {sendLabel}
      </button>
    </form>
  )
}
