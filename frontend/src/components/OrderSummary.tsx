import type { DishSource, Language } from '../api/client'
import { MESSAGES } from '../i18n/messages'
import { formatCents, formatTotal, toCents } from '../i18n/price'

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
        {groupByDish(dishes).map(({ dish, quantity }) => (
          <li key={dish.id} className="flex justify-between gap-3">
            <span className="min-w-0 truncate">
              {quantity > 1 && <span className="tabular-nums">{quantity}× </span>}
              {dish.name}
            </span>
            <span className="tabular-nums">
              {formatCents(toCents(dish.price.amount) * quantity, dish.price.currency, language)}
            </span>
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

/** One line per dish, in the order first picked, with how many times it was ordered. */
export function groupByDish(
  dishes: readonly DishSource[],
): { dish: DishSource; quantity: number }[] {
  const lines = new Map<string, { dish: DishSource; quantity: number }>()
  for (const dish of dishes) {
    const line = lines.get(dish.id)
    if (line) {
      line.quantity += 1
    } else {
      lines.set(dish.id, { dish, quantity: 1 })
    }
  }
  return [...lines.values()]
}
