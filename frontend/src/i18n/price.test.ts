import { describe, expect, it } from 'vitest'
import { formatPrice, formatTotal, toCents, totalsByCurrency } from './price'

const usd = (amount: string) => ({ amount, currency: 'USD' })
const brl = (amount: string) => ({ amount, currency: 'BRL' })

describe('price', () => {
  it('reads decimal strings as exact cents', () => {
    expect(toCents('14.50')).toBe(1450)
    expect(toCents('8')).toBe(800)
    expect(toCents('0.1')).toBe(10)
  })

  it('adds prices without floating-point noise', () => {
    expect(totalsByCurrency([usd('0.10'), usd('0.20'), usd('16.50')])).toEqual([
      { cents: 1680, currency: 'USD' },
    ])
    expect(totalsByCurrency([])).toEqual([])
  })

  it('never adds different currencies together', () => {
    expect(totalsByCurrency([brl('54.90'), usd('16.50'), brl('18.90')])).toEqual([
      { cents: 7380, currency: 'BRL' },
      { cents: 1650, currency: 'USD' },
    ])
    expect(formatTotal([brl('54.90'), usd('16.50')], 'pt')).toMatch(/^R\$\s54,90 \+ US\$\s16,50$/)
  })

  it('formats in the guest language', () => {
    expect(formatPrice(usd('16.50'), 'en')).toBe('$16.50')
    expect(formatPrice(brl('54.90'), 'pt')).toMatch(/^R\$\s54,90$/)
    expect(formatPrice(usd('16.50'), 'es')).toMatch(/16,50\sUS\$/)
  })
})
