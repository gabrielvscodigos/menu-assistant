import type { DishSource, Language } from '../api/client'
import { MESSAGES } from '../i18n/messages'
import { formatPrice, formatTotal } from '../i18n/price'

interface OrderSummaryProps {
  dishes: readonly DishSource[]
  language: Language
}

/** The guest's side of a placed order: each dish with its price, and the total. */
export function OrderSummary({ dishes, language }: OrderSummaryProps) {
  const text = MESSAGES[language]
  return (
    <div className="w-64 max-w-full text-sm">
      <p className="mb-1.5 font-semibold">🧾 {text.yourOrder}</p>
      <ul className="space-y-1">
        {dishes.map((dish) => (
          <li key={dish.id} className="flex justify-between gap-3">
            <span className="min-w-0 truncate">{dish.name}</span>
            <span className="tabular-nums">{formatPrice(dish.price, language)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1.5 flex justify-between gap-3 border-t border-white/40 pt-1.5 font-semibold">
        <span>{text.total}</span>
        <span className="text-right tabular-nums">
          {formatTotal(
            dishes.map((dish) => dish.price),
            language,
          )}
        </span>
      </p>
    </div>
  )
}
