import type { DishSource, Language } from '../api/client'
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
            className="flex w-full items-center gap-3 rounded-2xl border-2 border-dashed border-red-300 bg-white/60 p-3 text-left transition-colors hover:border-red-400 hover:bg-white active:scale-[0.99] dark:border-red-700 dark:bg-stone-800/60"
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

// Line icons, drawn inline so no icon library is needed.
function UtensilsIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-6"
    >
      <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
      <path d="M7 2v20" />
      <path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
    </svg>
  )
}

function WarningIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-3.5 shrink-0"
    >
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-3.5"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
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
      className="flex w-full items-start gap-3 rounded-2xl border-2 border-stone-200 bg-white p-3 text-left transition hover:border-red-300 active:scale-[0.99] aria-pressed:border-red-600 aria-pressed:bg-red-50 dark:border-stone-700 dark:bg-stone-800 dark:aria-pressed:bg-red-950"
    >
      <span
        aria-hidden="true"
        title={labels.courses[dish.course]}
        className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-red-100 text-red-600 dark:bg-red-950 dark:text-red-300"
      >
        <UtensilsIcon />
      </span>

      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 leading-snug font-semibold text-stone-900 dark:text-stone-100">
          {dish.name}
        </span>
        <span className="mt-0.5 line-clamp-2 text-xs text-stone-500 dark:text-stone-400">
          {dish.ingredients.join(', ')}
        </span>
        <span className="mt-2 flex flex-wrap gap-1.5 text-xs leading-4">
          {dish.allergens.length > 0 ? (
            <span
              title={text.contains}
              className="flex items-center gap-1 rounded-full bg-orange-50 px-2 py-1 text-stone-700 dark:bg-orange-950 dark:text-orange-100"
            >
              <span className="text-orange-600 dark:text-orange-300">
                <WarningIcon />
              </span>
              {dish.allergens.map((allergen) => labels.allergens[allergen]).join(', ')}
            </span>
          ) : (
            <span className="rounded-full bg-stone-100 px-2 py-1 text-stone-600 dark:bg-stone-700 dark:text-stone-300">
              {text.noAllergens}
            </span>
          )}
          {dish.dietary_flags.map((flag) => (
            <span
              key={flag}
              className="rounded-full bg-emerald-100 px-2 py-1 font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
            >
              {labels.diets[flag]}
            </span>
          ))}
        </span>
      </span>

      <span className="flex shrink-0 flex-col items-end gap-2">
        <span className="flex items-center gap-2.5">
          <span className="font-bold text-stone-900 tabular-nums dark:text-stone-100">{price}</span>
          <span
            aria-hidden="true"
            className={`flex size-6 items-center justify-center rounded-full ${
              selected
                ? 'bg-red-600 text-white'
                : 'border-2 border-stone-300 text-transparent dark:border-stone-600'
            }`}
          >
            <CheckIcon />
          </span>
        </span>
        {selected && (
          // Keeps room for the quantity stepper laid over this corner.
          <span aria-hidden="true" className="h-7 w-[5.5rem]" />
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
      className="absolute right-3 bottom-3 flex h-7 w-[5.5rem] items-center justify-between rounded-full bg-red-600 font-semibold text-white shadow-sm"
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
