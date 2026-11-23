import { useCallback, useMemo, useState } from 'react'
import type { DishSource } from '../api/client'

export interface Selection {
  /** Selected dishes, in the order they were picked. */
  dishes: DishSource[]
  ids: ReadonlySet<string>
  toggle: (dish: DishSource) => void
  clear: () => void
}

/** Dishes the guest picked from the cards, across all answers, ready to order. */
export function useSelection(): Selection {
  const [picked, setPicked] = useState<ReadonlyMap<string, DishSource>>(new Map())

  const toggle = useCallback((dish: DishSource) => {
    setPicked((current) => {
      const next = new Map(current)
      if (next.has(dish.id)) {
        next.delete(dish.id)
      } else {
        next.set(dish.id, dish)
      }
      return next
    })
  }, [])

  const clear = useCallback(() => setPicked(new Map()), [])

  return useMemo(
    () => ({ dishes: [...picked.values()], ids: new Set(picked.keys()), toggle, clear }),
    [picked, toggle, clear],
  )
}
