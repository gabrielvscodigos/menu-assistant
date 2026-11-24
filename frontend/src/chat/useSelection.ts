import { useCallback, useMemo, useState } from 'react'
import type { DishSource } from '../api/client'

interface Picked {
  dish: DishSource
  quantity: number
}

export interface Selection {
  /** Selected dishes in the order they were first picked, each repeated by its quantity. */
  dishes: DishSource[]
  /** How many of each dish (by id) are selected; unselected dishes are absent. */
  quantities: ReadonlyMap<string, number>
  /** Selects one of the dish, or removes it entirely if already selected. */
  toggle: (dish: DishSource) => void
  /** Adds one more of the dish. */
  add: (dish: DishSource) => void
  /** Removes one of the dish; at zero it is no longer selected. */
  remove: (dish: DishSource) => void
  clear: () => void
}

/** Dishes the guest picked from the cards, across all answers, ready to order. */
export function useSelection(): Selection {
  const [picked, setPicked] = useState<ReadonlyMap<string, Picked>>(new Map())

  const change = useCallback((dish: DishSource, quantityOf: (current: number) => number) => {
    setPicked((current) => {
      const next = new Map(current)
      const quantity = quantityOf(current.get(dish.id)?.quantity ?? 0)
      if (quantity > 0) {
        next.set(dish.id, { dish, quantity })
      } else {
        next.delete(dish.id)
      }
      return next
    })
  }, [])

  const toggle = useCallback(
    (dish: DishSource) => change(dish, (quantity) => (quantity > 0 ? 0 : 1)),
    [change],
  )
  const add = useCallback((dish: DishSource) => change(dish, (quantity) => quantity + 1), [change])
  const remove = useCallback(
    (dish: DishSource) => change(dish, (quantity) => quantity - 1),
    [change],
  )
  const clear = useCallback(() => setPicked(new Map()), [])

  return useMemo(() => {
    const items = [...picked.values()]
    return {
      dishes: items.flatMap(({ dish, quantity }) => Array<DishSource>(quantity).fill(dish)),
      quantities: new Map(items.map(({ dish, quantity }) => [dish.id, quantity])),
      toggle,
      add,
      remove,
      clear,
    }
  }, [picked, toggle, add, remove, clear])
}
