import { useEffect, useState } from 'react'

/** The value once it has stopped changing for ms: waits for a pause in typing before asking the server. */
export function useDebounced<T>(value: T, ms: number) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}
