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
}

export const MESSAGES: Record<Language, Messages> = {
  en: {
    languageName: 'English',
    title: 'Menu Assistant',
    subtitle: 'Your waiter for today',
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
  },
  pt: {
    languageName: 'Português',
    title: 'Assistente do Cardápio',
    subtitle: 'Seu garçom de hoje',
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
  },
  es: {
    languageName: 'Español',
    title: 'Asistente de la Carta',
    subtitle: 'Tu camarero de hoy',
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
  },
}
