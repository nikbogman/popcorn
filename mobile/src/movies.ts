import { useQuery } from '@tanstack/react-query'

import { api, parse, type Schemas } from '@/api'

export type MovieSummary = Schemas['MovieSummary']

/** TMDB search, idle while q is empty. */
export function useSearch(q: string) {
  return useQuery({
    queryKey: ['search', q],
    queryFn: () => parse(api.GET('/api/search', { params: { query: { q } } })),
    enabled: q.length > 0,
  })
}
