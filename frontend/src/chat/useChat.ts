import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  type AskRequest,
  type AskResponse,
  ask,
  type ChatTurn,
  type DishSource,
  isAbortError,
  type Language,
} from '../api/client'

export type ChatEntry =
  // `otherOptions`: the guest asked for dishes other than the ones already suggested.
  | { id: number; role: 'user'; text: string; otherOptions?: boolean }
  | { id: number; role: 'assistant'; response: AskResponse }
  // An order placed from the dish cards; shown in the chat, never sent to the LLM.
  | { id: number; role: 'order'; dishes: DishSource[]; language: Language }

export type ChatStatus =
  | { state: 'idle' }
  | { state: 'thinking' }
  | { state: 'error'; error: ApiError }

export interface Chat {
  entries: ChatEntry[]
  status: ChatStatus
  send: (question: string, options?: { otherOptions?: boolean }) => void
  retry: () => void
  placeOrder: (dishes: readonly DishSource[]) => void
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
    async (question: string, earlier: readonly ChatEntry[], otherOptions = false) => {
      inFlight.current?.abort()
      const controller = new AbortController()
      inFlight.current = controller
      setStatus({ state: 'thinking' })
      try {
        const excluded = otherOptions ? suggestedDishes(earlier) : []
        const response = await ask(
          {
            question,
            language,
            history: toHistory(earlier),
            ...carriedRestrictions(earlier),
            ...(excluded.length > 0 && { exclude_dishes: excluded }),
          },
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
    (question: string, options: { otherOptions?: boolean } = {}) => {
      const text = question.trim()
      if (!text || status.state === 'thinking') {
        return
      }
      const { otherOptions = false } = options
      setEntries((current) => [
        ...current,
        { id: nextId.current++, role: 'user', text, otherOptions },
      ])
      void request(text, entries, otherOptions)
    },
    [entries, request, status.state],
  )

  const retry = useCallback(() => {
    const last = entries.at(-1)
    if (status.state === 'error' && last?.role === 'user') {
      void request(last.text, entries.slice(0, -1), last.otherOptions)
    }
  }, [entries, request, status.state])

  const placeOrder = useCallback(
    (dishes: readonly DishSource[]) => {
      if (dishes.length > 0) {
        setEntries((current) => [
          ...current,
          { id: nextId.current++, role: 'order', dishes: [...dishes], language },
        ])
      }
    },
    [language],
  )

  const reset = useCallback(() => {
    inFlight.current?.abort()
    setEntries([])
    setStatus({ state: 'idle' })
  }, [])

  useEffect(() => () => inFlight.current?.abort(), [])

  return { entries, status, send, retry, placeOrder, reset }
}

/** Every dish the waiter has suggested (cited) so far, oldest first, without repeats. */
export function suggestedDishes(entries: readonly ChatEntry[]): string[] {
  const ids = entries.flatMap((entry) =>
    entry.role === 'assistant' ? entry.response.sources.map((dish) => dish.id) : [],
  )
  return [...new Set(ids)]
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
