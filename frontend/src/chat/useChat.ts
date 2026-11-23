import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  type AskRequest,
  type AskResponse,
  ask,
  type ChatTurn,
  isAbortError,
  type Language,
} from '../api/client'

export type ChatEntry =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; response: AskResponse }

export type ChatStatus =
  | { state: 'idle' }
  | { state: 'thinking' }
  | { state: 'error'; error: ApiError }

export interface Chat {
  entries: ChatEntry[]
  status: ChatStatus
  send: (question: string) => void
  retry: () => void
  reset: () => void
}

/**
 * The conversation, kept in the browser: the API is stateless, so every question is sent
 * with the earlier answered turns as `history` (which is how restrictions carry over).
 */
export function useChat(language: Language): Chat {
  const [entries, setEntries] = useState<ChatEntry[]>([])
  const [status, setStatus] = useState<ChatStatus>({ state: 'idle' })
  const nextId = useRef(0)
  const inFlight = useRef<AbortController | null>(null)

  const request = useCallback(
    async (question: string, earlier: readonly ChatEntry[]) => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      setStatus({ state: 'thinking' })
      try {
        const response = await ask(
          { question, language, history: toHistory(earlier), ...carriedRestrictions(earlier) },
          controller.signal,
        )
        setEntries((current) => [...current, { id: nextId.current++, role: 'assistant', response }])
        setStatus({ state: 'idle' })
      } catch (error) {
        if (isAbortError(error)) {
          return // reset or unmount: nothing to show
        }
        setStatus({ state: 'error', error: toApiError(error) })
      }
    },
    [language],
  )

  const send = useCallback(
    (question: string) => {
      const text = question.trim()
      if (!text || status.state === 'thinking') {
        return
      }
      setEntries((current) => [...current, { id: nextId.current++, role: 'user', text }])
      void request(text, entries)
    },
    [entries, request, status.state],
  )

  const retry = useCallback(() => {
    const last = entries.at(-1)
    if (status.state === 'error' && last?.role === 'user') {
      void request(last.text, entries.slice(0, -1))
    }
  }, [entries, request, status.state])

  const reset = useCallback(() => {
    inFlight.current?.abort()
    setEntries([])
    setStatus({ state: 'idle' })
  }, [])

  useEffect(() => () => inFlight.current?.abort(), [])

  return { entries, status, send, retry, reset }
}

/** Earlier turns for the API: only questions that got an answer, oldest first. */
export function toHistory(entries: readonly ChatEntry[]): ChatTurn[] {
  const turns: ChatTurn[] = []
  entries.forEach((entry, index) => {
    const next = entries[index + 1]
    if (entry.role === 'user' && next?.role === 'assistant') {
      turns.push({ role: 'user', content: entry.text })
    } else if (entry.role === 'assistant') {
      turns.push({ role: 'assistant', content: entry.response.answer })
    }
  })
  return turns.slice(-MAX_HISTORY_TURNS)
}

// The API accepts at most 20 earlier turns (see `carriedRestrictions` for why trimming
// older ones is safe).
const MAX_HISTORY_TURNS = 20

/**
 * The restrictions the last answer applied, sent back explicitly. The API also detects
 * them from `history`, but history is trimmed in long conversations; this way a
 * restriction stated once ("I'm allergic to peanuts") is never dropped. The course is
 * left out: it is a per-question preference, not a restriction.
 */
export function carriedRestrictions(
  entries: readonly ChatEntry[],
): Pick<AskRequest, 'exclude_allergens' | 'require_flags' | 'exclude_ingredients'> {
  const last = entries.findLast((entry) => entry.role === 'assistant')
  if (!last) {
    return {}
  }
  const { exclude_allergens, require_flags, exclude_ingredients } =
    last.response.applied_restrictions
  return { exclude_allergens, require_flags, exclude_ingredients }
}

function toApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError(0, error instanceof Error ? error.message : String(error))
}
