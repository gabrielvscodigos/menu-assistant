import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { ApiError, type AskResponse, ask, getHealth } from './api/client'

vi.mock('./api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api/client')>()),
  ask: vi.fn(),
  getHealth: vi.fn(),
}))

const askMock = vi.mocked(ask)
const healthMock = vi.mocked(getHealth)

function answer(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    answer: 'Try the Spicy Miso Ramen [spicy-miso-ramen] or [edamame].',
    sources: [],
    candidates: [
      {
        id: 'spicy-miso-ramen',
        name: 'Spicy Miso Ramen',
        course: 'main',
        allergens: ['eggs'],
        dietary_flags: [],
        score: 0.9,
      },
      {
        id: 'edamame',
        name: 'Salted Edamame',
        course: 'starter',
        allergens: ['soy'],
        dietary_flags: ['vegan'],
        score: 0.8,
      },
    ],
    applied_restrictions: {
      exclude_allergens: ['peanuts'],
      require_flags: [],
      exclude_ingredients: ['onion'],
      course: null,
    },
    language: 'en',
    notice: 'Please confirm with the restaurant staff.',
    ...overrides,
  }
}

async function ask_(question: string) {
  const user = userEvent.setup()
  await user.type(screen.getByRole('textbox'), `${question}{Enter}`)
  return user
}

beforeEach(() => {
  localStorage.clear()
  healthMock.mockResolvedValue({ status: 'ok', detail: null })
})

afterEach(() => {
  vi.resetAllMocks()
})

describe('App', () => {
  it('greets in English by default', () => {
    render(<App />)

    expect(screen.getByText(/I'm your waiter today/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'en' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('switches language with the option buttons and remembers it', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<App />)

    await user.click(screen.getByRole('button', { name: 'pt' }))

    expect(screen.getByText(/Sou seu garçom hoje/)).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveAttribute(
      'placeholder',
      'Do que você está com vontade?',
    )
    unmount()
    render(<App />)
    expect(screen.getByRole('button', { name: 'pt' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows the question, then the answer with dishes, restrictions and the notice', async () => {
    askMock.mockResolvedValue(answer())
    render(<App />)

    await ask_("I'm allergic to peanuts, no onion")

    expect(screen.getByText("I'm allergic to peanuts, no onion")).toBeInTheDocument()
    expect(await screen.findByText('Salted Edamame')).toBeInTheDocument() // bare citation
    expect(screen.getByText('Avoiding: peanuts, onion')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('Please confirm with the restaurant staff.')
    expect(askMock).toHaveBeenCalledWith(
      { question: "I'm allergic to peanuts, no onion", language: 'en', history: [] },
      expect.any(AbortSignal),
    )
  })

  it('sends earlier turns, their restrictions, and the chosen language with a follow-up', async () => {
    askMock.mockResolvedValue(answer())
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'es' }))

    await ask_('Soy alérgico al maní')
    await screen.findByText('Salted Edamame')
    await ask_('¿y un postre?')

    await waitFor(() => expect(askMock).toHaveBeenCalledTimes(2))
    expect(askMock.mock.calls[1][0]).toEqual({
      question: '¿y un postre?',
      language: 'es',
      history: [
        { role: 'user', content: 'Soy alérgico al maní' },
        { role: 'assistant', content: answer().answer },
      ],
      exclude_allergens: ['peanuts'],
      require_flags: [],
      exclude_ingredients: ['onion'],
    })
  })

  it('explains an error and retries the same question', async () => {
    askMock
      .mockRejectedValueOnce(new ApiError(503, 'LLM unavailable: cannot reach Ollama'))
      .mockResolvedValueOnce(answer({ answer: 'Here you go.', notice: null }))
    render(<App />)

    const user = await ask_('spicy noodles')

    expect(await screen.findByText(/LLM unavailable: cannot reach Ollama/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Here you go.')).toBeInTheDocument()
    expect(askMock.mock.calls[1][0]).toMatchObject({ question: 'spicy noodles', history: [] })
  })

  it('warns when the API reports it is not ready', async () => {
    healthMock.mockResolvedValue({ status: 'degraded', detail: 'LLM unavailable: run ollama' })
    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('LLM unavailable: run ollama')
  })

  it('starts a new conversation', async () => {
    askMock.mockResolvedValue(answer({ answer: 'First answer.' }))
    render(<App />)
    const user = await ask_('hello')
    await screen.findByText('First answer.')

    await user.click(screen.getByRole('button', { name: 'New conversation' }))

    expect(screen.queryByText('First answer.')).not.toBeInTheDocument()
    expect(screen.queryByText('hello')).not.toBeInTheDocument()
  })
})
