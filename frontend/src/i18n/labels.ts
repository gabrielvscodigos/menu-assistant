// Display names for the API's codes (allergens, diets, courses) in each UI language.
// `Record<Code, string>` makes the compiler flag any code the API adds later.

import type { Language } from '../api/client'
import type { components } from '../api/schema'

type Allergen = components['schemas']['Allergen']
type DietaryFlag = components['schemas']['DietaryFlag']
type Course = components['schemas']['Course']

interface Labels {
  allergens: Record<Allergen, string>
  diets: Record<DietaryFlag, string>
  courses: Record<Course, string>
}

export const LABELS: Record<Language, Labels> = {
  en: {
    allergens: {
      celery: 'celery',
      crustaceans: 'crustaceans',
      eggs: 'eggs',
      fish: 'fish',
      gluten: 'gluten',
      lupin: 'lupin',
      milk: 'milk',
      molluscs: 'molluscs',
      mustard: 'mustard',
      peanuts: 'peanuts',
      sesame: 'sesame',
      soy: 'soy',
      sulphites: 'sulphites',
      tree_nuts: 'tree nuts',
    },
    diets: {
      vegan: 'vegan',
      vegetarian: 'vegetarian',
      gluten_free: 'gluten-free',
      dairy_free: 'dairy-free',
      halal: 'halal',
    },
    courses: { starter: 'starter', main: 'main course', side: 'side dish', dessert: 'dessert' },
  },
  pt: {
    allergens: {
      celery: 'aipo',
      crustaceans: 'crustáceos',
      eggs: 'ovos',
      fish: 'peixe',
      gluten: 'glúten',
      lupin: 'tremoço',
      milk: 'leite',
      molluscs: 'moluscos',
      mustard: 'mostarda',
      peanuts: 'amendoim',
      sesame: 'gergelim',
      soy: 'soja',
      sulphites: 'sulfitos',
      tree_nuts: 'castanhas',
    },
    diets: {
      vegan: 'vegano',
      vegetarian: 'vegetariano',
      gluten_free: 'sem glúten',
      dairy_free: 'sem lactose',
      halal: 'halal',
    },
    courses: {
      starter: 'entrada',
      main: 'prato principal',
      side: 'acompanhamento',
      dessert: 'sobremesa',
    },
  },
  es: {
    allergens: {
      celery: 'apio',
      crustaceans: 'crustáceos',
      eggs: 'huevos',
      fish: 'pescado',
      gluten: 'gluten',
      lupin: 'altramuz',
      milk: 'leche',
      molluscs: 'moluscos',
      mustard: 'mostaza',
      peanuts: 'cacahuete',
      sesame: 'sésamo',
      soy: 'soja',
      sulphites: 'sulfitos',
      tree_nuts: 'frutos secos',
    },
    diets: {
      vegan: 'vegano',
      vegetarian: 'vegetariano',
      gluten_free: 'sin gluten',
      dairy_free: 'sin lácteos',
      halal: 'halal',
    },
    courses: {
      starter: 'entrante',
      main: 'plato principal',
      side: 'guarnición',
      dessert: 'postre',
    },
  },
}
