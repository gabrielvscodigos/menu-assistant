import type { DishSource, Language } from '../api/client'
import { MESSAGES } from '../i18n/messages'
import { formatTotal } from '../i18n/price'

interface OrderBarProps {
  dishes: readonly DishSource[]
  language: Language
  onOrder: () => void
  onClear: () => void
}

/** Shows what is selected and the total, with the "Order now" button. */
export function OrderBar({ dishes, language, onOrder, onClear }: OrderBarProps) {
  const text = MESSAGES[language]
  if (dishes.length === 0) {
    return null
  }
  return (
    <section
      aria-label={text.yourOrder}
      className="flex items-center gap-2 rounded-2xl bg-stone-900 py-2 pr-2 pl-4 text-white shadow-lg dark:bg-stone-100 dark:text-stone-900"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{text.selectedCount(dishes.length)}</p>
        <p className="text-xs text-stone-300 tabular-nums dark:text-stone-600">
          {text.total}:{' '}
          {formatTotal(
            dishes.map((dish) => dish.price),
            language,
          )}
        </p>
      </div>
      <button
        type="button"
        onClick={onClear}
        aria-label={text.clearSelection}
        title={text.clearSelection}
        className="flex size-9 items-center justify-center rounded-full text-lg text-stone-300 hover:bg-white/10 hover:text-white dark:text-stone-600 dark:hover:bg-black/10"
      >
        ×
      </button>
      <button
        type="button"
        onClick={onOrder}
        className="h-10 rounded-xl bg-red-600 px-4 font-semibold text-white transition-colors hover:bg-red-700 active:scale-[0.98]"
      >
        {text.orderNow}
      </button>
    </section>
  )
}
