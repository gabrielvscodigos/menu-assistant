// Prices arrive as exact decimal strings ("14.50"). Totals are added up in cents, so they
// never pick up floating-point noise, and shown in the guest's language.
import type { DishSource, Language } from '../api/client'

export type DishPrice = DishSource['price']

const LOCALES: Record<Language, string> = { en: 'en-US', pt: 'pt-BR', es: 'es-ES' }

export function toCents(amount: string): number {
  const [units, fraction = ''] = amount.split('.')
  return Number(units) * 100 + Number(fraction.padEnd(2, '0').slice(0, 2))
}

export function formatPrice(price: DishPrice, language: Language): string {
  return formatCents(toCents(price.amount), price.currency, language)
}

export function formatCents(cents: number, currency: string, language: Language): string {
  return new Intl.NumberFormat(LOCALES[language], { style: 'currency', currency }).format(
    cents / 100,
  )
}

/**
 * The sum per currency, in the order currencies first appear. Usually one entry; two when
 * the guest picked dishes in different languages (e.g. R$ and US$), which never get added
 * together.
 */
export function totalsByCurrency(
  prices: readonly DishPrice[],
): { cents: number; currency: string }[] {
  const totals = new Map<string, number>()
  for (const price of prices) {
    totals.set(price.currency, (totals.get(price.currency) ?? 0) + toCents(price.amount))
  }
  return [...totals].map(([currency, cents]) => ({ cents, currency }))
}

/** "R$ 54,90", or "R$ 54,90 + US$ 16,50" for mixed currencies; empty for no prices. */
export function formatTotal(prices: readonly DishPrice[], language: Language): string {
  return totalsByCurrency(prices)
    .map((total) => formatCents(total.cents, total.currency, language))
    .join(' + ')
}
