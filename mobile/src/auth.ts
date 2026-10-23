import * as SecureStore from 'expo-secure-store'
import { useSyncExternalStore } from 'react'

const KEY = 'watcher.token'

// undefined while the stored token loads, null when signed out.
let token: string | null | undefined
const listeners = new Set<() => void>()

function set(next: string | null) {
  token = next
  listeners.forEach((listener) => listener())
}

SecureStore.getItemAsync(KEY).then(set, () => set(null))

export const getToken = () => token

/** Stores the bearer token, or with null forgets it. Every useToken re-renders. */
export async function saveToken(next: string | null) {
  await (next ? SecureStore.setItemAsync(KEY, next) : SecureStore.deleteItemAsync(KEY))
  set(next)
}

/** The bearer token: undefined while it loads, null when signed out. */
export function useToken() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => token,
  )
}
