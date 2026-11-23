// Typed access to the menu-assistant API. Types come from `schema.d.ts`, generated from the
// API's OpenAPI schema (`pnpm gen:api`), so they always match the backend.
import type { components } from './schema'

type Schemas = components['schemas']

export type AskRequest = Schemas['AskRequest']
export type AskResponse = Schemas['AskResponse']
export type ChatTurn = Schemas['ChatTurn']
export type DishSource = Schemas['DishSource']
export type HealthResponse = Schemas['HealthResponse']
export type Language = Schemas['Language']

// In development Vite proxies /api to the FastAPI server (see vite.config.ts).
export const API_BASE = '/api'

/** A failed API call. `status` is 0 when the server could not be reached at all. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function ask(request: AskRequest, signal?: AbortSignal): Promise<AskResponse> {
  return call<AskResponse>('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return call<HealthResponse>('/health', { signal })
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }
    throw new ApiError(0, 'Cannot reach the server.')
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return (await response.json()) as T
}

// Checked by name: a DOMException is not always an `instanceof Error` across environments.
export function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError'
  )
}

// FastAPI reports errors as {"detail": "..."}, or {"detail": [...]} for validation (422).
async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const { detail } = body
      return typeof detail === 'string' ? detail : JSON.stringify(detail)
    }
  } catch {
    // Not JSON: fall through to the status text.
  }
  return response.statusText || `HTTP ${response.status}`
}
