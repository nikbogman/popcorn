import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, parse, type Schemas } from '@/api'

/** A reel shared to the app, and what it was found to show. */
export type ReelRequest = Schemas['ReelRequest']

const key = ['reels'] as const

export const inProgress = (r: ReelRequest) => r.status === 'queued' || r.status === 'running'

/** Every request, newest first. Re-checks every 3s while any is still being identified. */
export function useRequests() {
  return useQuery({
    queryKey: key,
    queryFn: () => parse(api.GET('/api/reels')),
    refetchInterval: (q) => (q.state.data?.some(inProgress) ? 3000 : false),
  })
}

/** Sends a reel URL to be identified. Fails for anything that isn't an Instagram reel or post. */
export function useShareReel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (url: string) => parse(api.POST('/api/reels', { body: { url } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  })
}

/** Queues a failed request again. */
export function useRetry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => parse(api.POST('/api/reels/{id}/retry', { params: { path: { id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  })
}
