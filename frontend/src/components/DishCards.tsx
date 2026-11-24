import type { Course, DishSource, Language } from '../api/client'
import { LABELS } from '../i18n/labels'
import { MESSAGES } from '../i18n/messages'
import { formatPrice } from '../i18n/price'

interface DishCardsProps {
  dishes: readonly DishSource[]
  language: Language
  /** How many of each dish (by id) the guest has selected. */
  quantities: ReadonlyMap<string, number>
  onToggle: (dish: DishSource) => void
  onAdd: (dish: DishSource) => void
  onRemove: (dish: DishSource) => void
  /** Shows the "Other options" card when set (only on the newest answer). */
  onOtherOptions?: () => void
}

/** The suggested dishes as compact, selectable cards, plus an "Other options" card. */
export function DishCards({
  dishes,
  language,
  quantities,
  onToggle,
  onAdd,
  onRemove,
  onOtherOptions,
}: DishCardsProps) {
  const text = MESSAGES[language]
  return (
    <ul className="space-y-2">
      {dishes.map((dish) => (
        <li key={dish.id} className="relative">
          <DishCard
            dish={dish}
            language={language}
            quantity={quantities.get(dish.id) ?? 0}
            onToggle={() => onToggle(dish)}
          />
          {quantities.has(dish.id) && (
            // A sibling of the card (buttons cannot nest), placed over its bottom-right corner.
            <QuantityStepper
              dishName={dish.name}
              quantity={quantities.get(dish.id) ?? 0}
              language={language}
              onAdd={() => onAdd(dish)}
              onRemove={() => onRemove(dish)}
            />
          )}
        </li>
      ))}
      {onOtherOptions && (
        <li>
          <button
            type="button"
            onClick={onOtherOptions}
            className="flex w-full items-center gap-3 rounded-2xl border-2 border-dashed border-red-300 bg-white/60 p-2.5 text-left transition-colors hover:border-red-400 hover:bg-white active:scale-[0.99] dark:border-red-700 dark:bg-stone-800/60"
          >
            <span
              aria-hidden="true"
              className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-red-100 text-2xl font-semibold text-red-700 dark:bg-red-900 dark:text-red-200"
            >
              +
            </span>
            <span className="min-w-0">
              <span className="block font-semibold">{text.otherOptions}</span>
              <span className="block truncate text-xs text-stone-500 dark:text-stone-400">
                {text.otherOptionsHint}
              </span>
            </span>
          </button>
        </li>
      )}
    </ul>
  )
}

// Stand-in pictures until the menu has dish photos.
const COURSE_ICONS: Record<Course, string> = {
  starter: '🥗',
  main: '🍽️',
  side: '🌽',
  dessert: '🍰',
}

interface DishCardProps {
  dish: DishSource
  language: Language
  quantity: number
  onToggle: () => void
}

function DishCard({ dish, language, quantity, onToggle }: DishCardProps) {
  const selected = quantity > 0
  const text = MESSAGES[language]
  const labels = LABELS[language]
  const price = formatPrice(dish.price, language)
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={`${text.selectDish}: ${dish.name}, ${price}`}
      onClick={onToggle}
      className="flex w-full items-start gap-3 rounded-2xl border border-stone-200 bg-white p-2.5 text-left shadow-sm transition-transform hover:border-red-300 active:scale-[0.99] aria-pressed:border-red-600 aria-pressed:bg-red-50 aria-pressed:ring-2 aria-pressed:ring-red-400 dark:border-stone-700 dark:bg-stone-800 dark:aria-pressed:bg-red-950"
    >
      <span
        aria-hidden="true"
        title={labels.courses[dish.course]}
        className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-red-100 text-2xl dark:bg-stone-700"
      >
        {COURSE_ICONS[dish.course]}
      </span>

      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 leading-snug font-semibold text-stone-900 dark:text-stone-100">
          {dish.name}
        </span>
        <span className="line-clamp-2 text-xs text-stone-500 dark:text-stone-400">
          {dish.ingredients.join(', ')}
        </span>
        <span className="mt-1.5 flex flex-wrap gap-1 text-[11px] leading-4">
          {dish.allergens.length > 0 ? (
            <span
              title={text.contains}
              className="rounded-full bg-orange-50 px-1.5 py-0.5 font-medium text-orange-800 dark:bg-orange-950 dark:text-orange-200"
            >
              ⚠ {dish.allergens.map((allergen) => labels.allergens[allergen]).join(', ')}
            </span>
          ) : (
            <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-stone-600 dark:bg-stone-700 dark:text-stone-300">
              {text.noAllergens}
            </span>
          )}
          {dish.dietary_flags.map((flag) => (
            <span
              key={flag}
              className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
            >
              {labels.diets[flag]}
            </span>
          ))}
        </span>
      </span>

      <span className="flex shrink-0 flex-col items-end gap-2">
        <span className="font-semibold text-stone-900 tabular-nums dark:text-stone-100">
          {price}
        </span>
        {selected ? (
          // Keeps room for the quantity stepper laid over this corner.
          <span aria-hidden="true" className="h-7 w-[5.5rem]" />
        ) : (
          <span
            aria-hidden="true"
            className="flex size-5 items-center justify-center rounded-full border border-stone-300 text-xs text-transparent dark:border-stone-600"
          >
            ✓
          </span>
        )}
      </span>
    </button>
  )
}

interface QuantityStepperProps {
  dishName: string
  quantity: number
  language: Language
  onAdd: () => void
  onRemove: () => void
}

/** "− 2 +" control for ordering the same dish more than once. */
function QuantityStepper({ dishName, quantity, language, onAdd, onRemove }: QuantityStepperProps) {
  const text = MESSAGES[language]
  const stepClass =
    'flex size-7 items-center justify-center rounded-full text-base leading-none text-white hover:bg-red-700 active:scale-95'
  return (
    <fieldset
      aria-label={`${text.quantity}: ${dishName}`}
      className="absolute right-2.5 bottom-2.5 flex h-7 w-[5.5rem] items-center justify-between rounded-full bg-red-600 font-semibold text-white shadow-sm"
    >
      <button
        type="button"
        onClick={onRemove}
        aria-label={`${text.removeOne}: ${dishName}`}
        className={stepClass}
      >
        −
      </button>
      <span className="text-sm tabular-nums">{quantity}</span>
      <button
        type="button"
        onClick={onAdd}
        aria-label={`${text.addOne}: ${dishName}`}
        className={stepClass}
      >
        +
      </button>
    </fieldset>
  )
}
