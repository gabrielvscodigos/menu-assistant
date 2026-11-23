import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type AskResponse, ask, getHealth } from './client'

const ANSWER: AskResponse = {
  answer: 'Try Edamame [edamame].',
  sources: [],
  candidates: [],
  applied_restrictions: {
    exclude_allergens: [],
    require_flags: [],
    exclude_ingredients: [],
    course: null,
  },
  language: 'en',
  notice: null,
}

function mockFetch(response: Response | Error | DOMException) {
  const fetchMock = vi.fn(() =>
    response instanceof Response ? Promise.resolve(response) : Promise.reject(response),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ask', () => {
  it('posts the request to /api/ask and returns the answer', async () => {
    const fetchMock = mockFetch(json(ANSWER))

    const answer = await ask({ question: 'something light', language: 'pt' })

    expect(answer).toEqual(ANSWER)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/ask',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ question: 'something light', language: 'pt' }),
      }),
    )
  })

  it('turns an error detail into an ApiError', async () => {
    mockFetch(json({ detail: 'LLM unavailable: cannot reach Ollama' }, 503))

    const error = await ask({ question: 'hi' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 503, message: 'LLM unavailable: cannot reach Ollama' })
  })

  it('reports validation errors as text', async () => {
    mockFetch(json({ detail: [{ msg: 'Field required' }] }, 422))

    await expect(ask({ question: '' })).rejects.toMatchObject({
      status: 422,
      message: '[{"msg":"Field required"}]',
    })
  })

  it('reports an unreachable server with status 0', async () => {
    mockFetch(new TypeError('Failed to fetch'))

    await expect(ask({ question: 'hi' })).rejects.toMatchObject({
      status: 0,
      message: 'Cannot reach the server.',
    })
  })

  it('lets a cancelled request reject with the abort error', async () => {
    mockFetch(new DOMException('aborted', 'AbortError'))

    await expect(ask({ question: 'hi' })).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('falls back to the status text when the body is not JSON', async () => {
    mockFetch(new Response('oops', { status: 502, statusText: 'Bad Gateway' }))

    await expect(ask({ question: 'hi' })).rejects.toMatchObject({
      status: 502,
      message: 'Bad Gateway',
    })
  })
})

describe('getHealth', () => {
  it('reads /api/health', async () => {
    const fetchMock = mockFetch(json({ status: 'degraded', detail: 'LLM unavailable' }))

    expect(await getHealth()).toEqual({ status: 'degraded', detail: 'LLM unavailable' })
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything())
  })
})
