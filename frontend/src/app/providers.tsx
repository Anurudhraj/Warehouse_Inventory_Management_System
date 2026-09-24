import { useState, type ReactNode } from 'react';
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { isApiError } from '@/lib/api/errors';
import { isDevelopment } from '@/config/env';

/**
 * Global data layer.
 *
 * Sensible enterprise defaults: no aggressive refetching on window focus,
 * one retry for transient failures (never for 4xx), and structured logging of
 * failed queries in development.
 */
function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (!isDevelopment) return;
        const key = JSON.stringify(query.queryKey);
        const status = isApiError(error) ? error.status : 'n/a';
        console.warn(`[query] ${key} failed (status ${status}):`, error);
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (isApiError(error) && error.status >= 400 && error.status < 500) return false;
          return failureCount < 2;
        },
      },
      mutations: { retry: 0 },
    },
  });
}

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
