import { describe, expect, it } from 'vitest'
import type { DishSource } from '../api/client'
import { parseAnswer, parseInline } from './answerText'

const RAMEN: DishSource = {
  id: 'spicy-miso-ramen',
  name: 'Spicy Miso Ramen',
  course: 'main',
  allergens: [],
  dietary_flags: [],
  score: 0.9,
}
const NAMES = new Map([[RAMEN.id, RAMEN.name]])

describe('parseInline', () => {
  it('marks a citation that follows the dish name', () => {
    expect(parseInline('Try the Spicy Miso Ramen [spicy-miso-ramen].', NAMES)).toEqual([
      { type: 'text', text: 'Try the Spicy Miso Ramen ' },
      { type: 'dish', id: 'spicy-miso-ramen', name: 'Spicy Miso Ramen', named: true },
      { type: 'text', text: '.' },
    ])
  })

  it('shows the name when the citation stands alone', () => {
    expect(parseInline('[spicy-miso-ramen] is great', NAMES)[0]).toEqual({
      type: 'dish',
      id: 'spicy-miso-ramen',
      name: 'Spicy Miso Ramen',
      named: false,
    })
  })

  it('recognizes a bold dish name before the citation', () => {
    const parts = parseInline('**Spicy Miso Ramen** [spicy-miso-ramen]', NAMES)

    expect(parts[0]).toEqual({ type: 'bold', text: 'Spicy Miso Ramen' })
    expect(parts[1]).toMatchObject({ type: 'text', text: ' ' })
    expect(parts[2]).toMatchObject({ type: 'dish', named: true })
  })

  it('marks a citation that comes right before the dish name', () => {
    expect(parseInline('Try [spicy-miso-ramen] Spicy Miso Ramen, it is hot', NAMES)[1]).toEqual({
      type: 'dish',
      id: 'spicy-miso-ramen',
      name: 'Spicy Miso Ramen',
      named: true,
    })
    expect(parseInline('[spicy-miso-ramen] **Spicy Miso Ramen**', NAMES)[0]).toMatchObject({
      named: true,
    })
  })

  it('keeps unknown brackets as text', () => {
    expect(parseInline('sauce [on the side] and [lasagna]', NAMES)).toEqual([
      { type: 'text', text: 'sauce [on the side] and ' },
      { type: 'text', text: '[lasagna]' },
    ])
  })
})

describe('parseAnswer', () => {
  it('groups lines into paragraphs and lists', () => {
    const text = 'Here you go:\n\n1. First\n2. Second\n\n- a\n- b\nEnjoy!'

    expect(parseAnswer(text, [RAMEN])).toEqual([
      { type: 'paragraph', lines: [[{ type: 'text', text: 'Here you go:' }]] },
      {
        type: 'list',
        ordered: true,
        items: [[{ type: 'text', text: 'First' }], [{ type: 'text', text: 'Second' }]],
      },
      {
        type: 'list',
        ordered: false,
        items: [[{ type: 'text', text: 'a' }], [{ type: 'text', text: 'b' }]],
      },
      { type: 'paragraph', lines: [[{ type: 'text', text: 'Enjoy!' }]] },
    ])
  })

  it('treats "*" bullets as list items, not bold', () => {
    const [block] = parseAnswer('* [spicy-miso-ramen] is spicy', [RAMEN])

    expect(block).toMatchObject({ type: 'list', ordered: false })
  })

  it('returns nothing for blank text', () => {
    expect(parseAnswer('\n \n', [])).toEqual([])
  })
})
