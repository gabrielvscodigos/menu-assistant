import { describe, expect, it } from 'vitest'
import type { AskResponse } from '../api/client'
import { type ChatEntry, carriedRestrictions, suggestedDishes, toHistory } from './useChat'

function reply(
  text: string,
  allergens: AskResponse['applied_restrictions']['exclude_allergens'] = [],
) {
  return {
    answer: text,
    sources: [],
    candidates: [],
    applied_restrictions: {
      exclude_allergens: allergens,
      require_flags: [],
      exclude_ingredients: [],
      course: 'dessert',
    },
    language: 'en',
    notice: null,
  } satisfies AskResponse
}

describe('toHistory', () => {
  it('keeps answered questions and answers, oldest first', () => {
    const entries: ChatEntry[] = [
      { id: 1, role: 'user', text: 'q1' },
      { id: 2, role: 'assistant', response: reply('a1') },
      { id: 3, role: 'user', text: 'q2 (failed)' },
      { id: 4, role: 'user', text: 'q3' },
      { id: 5, role: 'assistant', response: reply('a3') },
    ]

    expect(toHistory(entries)).toEqual([
      { role: 'user', content: 'q1' },
      { role: 'assistant', content: 'a1' },
      { role: 'user', content: 'q3' },
      { role: 'assistant', content: 'a3' },
    ])
  })

  it('keeps only the last 20 turns', () => {
    const entries: ChatEntry[] = Array.from({ length: 30 }, (_, n) =>
      n % 2 === 0
        ? { id: n, role: 'user', text: `q${n}` }
        : { id: n, role: 'assistant', response: reply(`a${n}`) },
    )

    const history = toHistory(entries)

    expect(history).toHaveLength(20)
    expect(history[0]).toEqual({ role: 'user', content: 'q10' })
  })
})

describe('carriedRestrictions', () => {
  it('sends back what the last answer applied, without the course', () => {
    const entries: ChatEntry[] = [
      { id: 1, role: 'user', text: 'no peanuts' },
      { id: 2, role: 'assistant', response: reply('a', ['peanuts']) },
    ]

    expect(carriedRestrictions(entries)).toEqual({
      exclude_allergens: ['peanuts'],
      require_flags: [],
      exclude_ingredients: [],
    })
  })

  it('is empty before the first answer', () => {
    expect(carriedRestrictions([{ id: 1, role: 'user', text: 'hi' }])).toEqual({})
  })
})

describe('suggestedDishes', () => {
  it('lists every cited dish once, oldest first', () => {
    const withSources = (ids: string[]) => ({
      ...reply('a'),
      sources: ids.map((id) => ({
        id,
        name: id,
        course: 'main' as const,
        description: '',
        ingredients: [],
        price: { amount: '1.00', currency: 'USD' },
        allergens: [],
        dietary_flags: [],
        score: 1,
      })),
    })
    const entries: ChatEntry[] = [
      { id: 1, role: 'user', text: 'q1' },
      { id: 2, role: 'assistant', response: withSources(['ramen', 'gyoza']) },
      { id: 3, role: 'user', text: 'q2' },
      { id: 4, role: 'assistant', response: withSources(['gyoza', 'elote']) },
    ]

    expect(suggestedDishes(entries)).toEqual(['ramen', 'gyoza', 'elote'])
  })
})
