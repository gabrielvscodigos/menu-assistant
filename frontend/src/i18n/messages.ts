// Every text the interface shows, in each language the guest can choose. The mascot's
// replies come from the API in the same language (sent as `language` with each question).
import type { Language } from '../api/client'

export const LANGUAGES: readonly Language[] = ['en', 'pt', 'es']
export const DEFAULT_LANGUAGE: Language = 'en'

export interface Messages {
  languageName: string
  title: string
  subtitle: string
  greeting: string
  placeholder: string
  send: string
  thinking: string
  newChat: string
  avoiding: string
  course: string
  notice: string
  retry: string
  serverUnreachable: string
  serverError: string
  degraded: string
  languageLabel: string
  mascotLabel: string
  contains: string
  noAllergens: string
  otherOptions: string
  otherOptionsHint: string
  otherOptionsQuestion: string
  selectDish: string
  selectedCount: (count: number) => string
  total: string
  orderNow: string
  clearSelection: string
  quantity: string
  addOne: string
  removeOne: string
  yourOrder: string
  orderConfirmed: string
  orderNotice: string
}

export const MESSAGES: Record<Language, Messages> = {
  en: {
    languageName: 'English',
    title: 'Menu Assistant',
    subtitle: 'online now',
    greeting:
      "Hi! I'm your waiter today. Tell me what you feel like eating, or anything you need to avoid, and I'll suggest something from our menu.",
    placeholder: 'What are you in the mood for?',
    send: 'Send',
    thinking: 'Checking the menu…',
    newChat: 'New conversation',
    avoiding: 'Avoiding',
    course: 'Course',
    notice: 'Please note',
    retry: 'Try again',
    serverUnreachable: "I can't reach the kitchen right now. Is the API running?",
    serverError: 'Something went wrong in the kitchen:',
    degraded: 'The assistant is not fully ready:',
    languageLabel: 'Language',
    mascotLabel: 'The waiter',
    contains: 'Contains',
    noAllergens: 'No allergens listed',
    otherOptions: 'Other options',
    otherOptionsHint: 'Show me different dishes',
    otherOptionsQuestion: 'Can you suggest other options?',
    selectDish: 'Select',
    selectedCount: (count) => (count === 1 ? '1 dish selected' : `${count} dishes selected`),
    total: 'Total',
    orderNow: 'Order now',
    clearSelection: 'Clear selection',
    quantity: 'Quantity',
    addOne: 'Add one more',
    removeOne: 'Remove one',
    yourOrder: 'My order',
    orderConfirmed: "Great choice! I've sent your order to the kitchen.",
    orderNotice: 'If you have any allergy, please tell the staff before the kitchen starts.',
  },
  pt: {
    languageName: 'Português',
    title: 'Assistente do Cardápio',
    subtitle: 'online agora',
    greeting:
      'Olá! Sou seu garçom hoje. Me conte o que você está com vontade de comer, ou o que precisa evitar, e eu sugiro algo do nosso cardápio.',
    placeholder: 'Do que você está com vontade?',
    send: 'Enviar',
    thinking: 'Consultando o cardápio…',
    newChat: 'Nova conversa',
    avoiding: 'Evitando',
    course: 'Tipo de prato',
    notice: 'Atenção',
    retry: 'Tentar de novo',
    serverUnreachable: 'Não consigo falar com a cozinha agora. A API está rodando?',
    serverError: 'Algo deu errado na cozinha:',
    degraded: 'O assistente não está totalmente pronto:',
    languageLabel: 'Idioma',
    mascotLabel: 'O garçom',
    contains: 'Contém',
    noAllergens: 'Nenhum alérgeno listado',
    otherOptions: 'Outras opções',
    otherOptionsHint: 'Me mostre pratos diferentes',
    otherOptionsQuestion: 'Pode sugerir outras opções?',
    selectDish: 'Selecionar',
    selectedCount: (count) =>
      count === 1 ? '1 prato selecionado' : `${count} pratos selecionados`,
    total: 'Total',
    orderNow: 'Pedir agora',
    clearSelection: 'Limpar seleção',
    quantity: 'Quantidade',
    addOne: 'Adicionar mais um',
    removeOne: 'Remover um',
    yourOrder: 'Meu pedido',
    orderConfirmed: 'Ótima escolha! Já enviei seu pedido para a cozinha.',
    orderNotice: 'Se você tem alguma alergia, avise a equipe antes de a cozinha começar.',
  },
  es: {
    languageName: 'Español',
    title: 'Asistente de la Carta',
    subtitle: 'en línea ahora',
    greeting:
      '¡Hola! Hoy soy tu camarero. Cuéntame qué te apetece comer, o qué necesitas evitar, y te sugiero algo de nuestra carta.',
    placeholder: '¿Qué te apetece?',
    send: 'Enviar',
    thinking: 'Consultando la carta…',
    newChat: 'Nueva conversación',
    avoiding: 'Evitando',
    course: 'Tipo de plato',
    notice: 'Atención',
    retry: 'Reintentar',
    serverUnreachable: 'No puedo hablar con la cocina ahora. ¿La API está en marcha?',
    serverError: 'Algo salió mal en la cocina:',
    degraded: 'El asistente no está del todo listo:',
    languageLabel: 'Idioma',
    mascotLabel: 'El camarero',
    contains: 'Contiene',
    noAllergens: 'Sin alérgenos indicados',
    otherOptions: 'Otras opciones',
    otherOptionsHint: 'Muéstrame platos diferentes',
    otherOptionsQuestion: '¿Puedes sugerir otras opciones?',
    selectDish: 'Seleccionar',
    selectedCount: (count) =>
      count === 1 ? '1 plato seleccionado' : `${count} platos seleccionados`,
    total: 'Total',
    orderNow: 'Pedir ahora',
    clearSelection: 'Quitar selección',
    quantity: 'Cantidad',
    addOne: 'Añadir uno más',
    removeOne: 'Quitar uno',
    yourOrder: 'Mi pedido',
    orderConfirmed: '¡Buena elección! Ya envié tu pedido a la cocina.',
    orderNotice: 'Si tienes alguna alergia, avisa al personal antes de que la cocina empiece.',
  },
}
