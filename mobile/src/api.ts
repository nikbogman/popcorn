import createClient from 'openapi-fetch'

import type { components, paths } from '@/api-types'
import { getToken, saveToken } from '@/auth'

/** The server's request and response shapes, generated from its OpenAPI spec by `pnpm api`. */
export type Schemas = components['schemas']

export const api = createClient<paths>({ baseUrl: process.env.EXPO_PUBLIC_API_URL })

api.use({
  onRequest({ request }) {
    const token = getToken()
    if (token) request.headers.set('authorization', `Bearer ${token}`)
  },
  // A token the server no longer accepts signs out, and the root layout's guard shows Login.
  onResponse({ response }) {
    if (response.status === 401 && getToken()) void saveToken(null)
  },
})

/** The response's data. Throws on an error status, so React Query sees the failure. */
export async function parse<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>) {
  const { data, error, response } = await request
  if (!response.ok) throw new Error(`${response.status}: ${JSON.stringify(error)}`)
  return data as T
}

/** Trades the password for a token. Resolves to an error message when it can't. */
export async function logIn(password: string) {
  try {
    const { data, response } = await api.POST('/api/auth/login', { body: { password } })
    if (data) return void (await saveToken(data.token))
    return response.status === 401 ? 'Wrong password.' : "Couldn't log in."
  } catch {
    return "Couldn't reach the server."
  }
}

/** Ends the token on the server, then forgets it here even if the server couldn't be reached. */
export async function logOut() {
  await api.POST('/api/auth/logout').catch(() => {})
  await saveToken(null)
}
