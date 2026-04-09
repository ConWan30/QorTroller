// src/shared/api/client.js
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:            30_000,   // 30s
      retry:                2,
      retryDelay:           (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
      refetchOnWindowFocus: false,
      // On error, data stays in cache — UI shows stale with error badge
    },
  },
})
