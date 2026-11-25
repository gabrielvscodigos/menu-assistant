import { render, screen, waitFor, within } from '@testing-library/react'
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
        description: 'Rich pork broth with chili oil.',
        ingredients: ['wheat noodles', 'pork bone broth', 'chili oil', 'soft-boiled egg'],
        price: { amount: '16.50', currency: 'USD' },
        allergens: ['eggs'],
        dietary_flags: [],
        score: 0.9,
      },
      {
        id: 'edamame',
        name: 'Salted Edamame',
        course: 'starter',
        description: 'Steamed young soybeans with sea salt.',
        ingredients: ['edamame (young soybeans)', 'sea salt'],
        price: { amount: '5.50', currency: 'USD' },
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

  it('shows suggested dishes as compact cards below the reply', async () => {
    const reply = answer()
    askMock.mockResolvedValue({ ...reply, sources: reply.candidates })
    render(<App />)

    await ask_('something spicy')

    const ramen = await screen.findByRole('button', { name: 'Select: Spicy Miso Ramen, $16.50' })
    expect(ramen).toHaveTextContent('wheat noodles, pork bone broth, chili oil, soft-boiled egg')
    expect(within(ramen).getByTitle('Contains')).toHaveTextContent('eggs')
    expect(ramen).toHaveAttribute('aria-pressed', 'false')
    const edamame = screen.getByRole('button', { name: /Salted Edamame/ })
    expect(edamame).toHaveTextContent('vegan')
    expect(edamame).toHaveTextContent('$5.50')
    // The cards come after the reply text, outside its bubble.
    const replyText = screen.getByText(/Try the Spicy Miso Ramen/)
    expect(replyText.compareDocumentPosition(ramen) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(replyText.closest('li')).not.toContainElement(ramen)
    expect(screen.getByRole('button', { name: /Other options/ })).toBeInTheDocument()
  })

  it('orders the selected dishes with a total and a staff notice', async () => {
    const reply = answer()
    askMock.mockResolvedValue({ ...reply, sources: reply.candidates })
    render(<App />)
    const user = await ask_('something spicy')
    const ramen = await screen.findByRole('button', { name: /Spicy Miso Ramen/ })
    expect(screen.queryByRole('button', { name: 'Order now' })).not.toBeInTheDocument()

    await user.click(ramen)
    await user.click(screen.getByRole('button', { name: /Salted Edamame/ }))

    expect(ramen).toHaveAttribute('aria-pressed', 'true')
    const bar = screen.getByRole('region', { name: 'My order' })
    expect(bar).toHaveTextContent('2 dishes selected')
    expect(bar).toHaveTextContent('Total: $22.00')

    await user.click(screen.getByRole('button', { name: 'Order now' }))

    expect(
      screen.getByText("Great choice! I've sent your order to the kitchen."),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('note').at(-1)).toHaveTextContent(/tell the staff/)
    expect(screen.queryByRole('region', { name: 'My order' })).not.toBeInTheDocument()
    expect(ramen).toHaveAttribute('aria-pressed', 'false')
    expect(askMock).toHaveBeenCalledTimes(1) // ordering does not ask the LLM
  })

  it('orders the same dish more than once', async () => {
    const reply = answer()
    askMock.mockResolvedValue({ ...reply, sources: reply.candidates })
    render(<App />)
    const user = await ask_('something spicy')
    expect(screen.queryByRole('button', { name: /Add one more/ })).not.toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: /Select: Spicy Miso Ramen/ }))
    const addRamen = screen.getByRole('button', { name: 'Add one more: Spicy Miso Ramen' })
    await user.click(addRamen)
    await user.click(addRamen)
    await user.click(screen.getByRole('button', { name: 'Remove one: Spicy Miso Ramen' }))
    await user.click(screen.getByRole('button', { name: /Select: Salted Edamame/ }))

    expect(screen.getByRole('group', { name: 'Quantity: Spicy Miso Ramen' })).toHaveTextContent('2')
    const bar = screen.getByRole('region', { name: 'My order' })
    expect(bar).toHaveTextContent('3 dishes selected')
    expect(bar).toHaveTextContent('Total: $38.50')

    await user.click(screen.getByRole('button', { name: 'Order now' }))

    const ramenLine = screen.getByText('Spicy Miso Ramen', { selector: 'li > span' }).closest('li')
    expect(ramenLine).toHaveTextContent('2× Spicy Miso Ramen$33.00')
  })

  it('removes a dish when its quantity drops to zero', async () => {
    const reply = answer()
    askMock.mockResolvedValue({ ...reply, sources: reply.candidates })
    render(<App />)
    const user = await ask_('something spicy')
    const edamame = await screen.findByRole('button', { name: /Select: Salted Edamame/ })

    await user.click(edamame)
    await user.click(screen.getByRole('button', { name: 'Remove one: Salted Edamame' }))

    expect(edamame).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('region', { name: 'My order' })).not.toBeInTheDocument()
  })

  it('clears the selection without ordering', async () => {
    const reply = answer()
    askMock.mockResolvedValue({ ...reply, sources: reply.candidates })
    render(<App />)
    const user = await ask_('something spicy')
    await user.click(await screen.findByRole('button', { name: /Salted Edamame/ }))

    await user.click(screen.getByRole('button', { name: 'Clear selection' }))

    expect(screen.queryByRole('button', { name: 'Order now' })).not.toBeInTheDocument()
  })

  it('asks for other dishes, excluding every dish already suggested', async () => {
    const first = answer({ language: 'pt' })
    askMock
      .mockResolvedValueOnce({ ...first, sources: [first.candidates[0]] })
      .mockResolvedValueOnce({ ...first, answer: 'Second.', sources: [first.candidates[1]] })
      .mockResolvedValueOnce({ ...first, answer: 'Third.', sources: [] })
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: 'pt' }))
    await ask_('algo apimentado')
    await screen.findByRole('button', { name: /Spicy Miso Ramen/ })

    await user.click(screen.getByRole('button', { name: /Outras opções/ }))
    await screen.findByText('Second.')
    await user.click(screen.getByRole('button', { name: /Outras opções/ }))
    await screen.findByText('Third.')

    expect(screen.getAllByText('Pode sugerir outras opções?')).toHaveLength(2)
    expect(askMock.mock.calls[1][0]).toMatchObject({
      question: 'Pode sugerir outras opções?',
      language: 'pt',
      exclude_dishes: ['spicy-miso-ramen'],
    })
    expect(askMock.mock.calls[2][0]).toMatchObject({
      exclude_dishes: ['spicy-miso-ramen', 'edamame'],
    })
    // Only the newest answer offers more options, and it suggested no dish.
    expect(screen.queryByRole('button', { name: /Outras opções/ })).not.toBeInTheDocument()
  })

  it('warns when the API reports it is not ready', async () => {
    healthMock.mockResolvedValue({ status: 'degraded', detail: 'LLM unavailable: run ollama' })
    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('LLM unavailable: run ollama')
  })

  it('shows the full waiter only before the first question', async () => {
    askMock.mockResolvedValue(answer({ answer: 'Done.' }))
    render(<App />)
    expect(screen.getByTestId('welcome-waiter')).toBeInTheDocument()

    await ask_('hi')

    expect(screen.queryByTestId('welcome-waiter')).not.toBeInTheDocument()
    await screen.findByText('Done.')
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
