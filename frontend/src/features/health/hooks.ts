import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { env } from '@/config/env';
import { fetchHealth, fetchLiveness, fetchReadiness } from '@/features/health/api';
import type { HealthResponse } from '@/lib/api/types';

export const healthKeys = {
  all: ['health'] as const,
  deep: () => [...healthKeys.all, 'deep'] as const,
  liveness: () => [...healthKeys.all, 'liveness'] as const,
  readiness: () => [...healthKeys.all, 'readiness'] as const,
};

/** Polls the deep health endpoint; failures are surfaced, never thrown as 500s. */
export function useSystemHealth(): UseQueryResult<HealthResponse, Error> {
  return useQuery({
    queryKey: healthKeys.deep(),
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: env.healthPollMs,
    refetchIntervalInBackground: false,
    retry: 1,
    staleTime: 15_000,
  });
}

export function useLiveness() {
  return useQuery({
    queryKey: healthKeys.liveness(),
    queryFn: ({ signal }) => fetchLiveness(signal),
    refetchInterval: env.healthPollMs * 2,
    retry: 0,
  });
}

export function useReadiness() {
  return useQuery({
    queryKey: healthKeys.readiness(),
    queryFn: ({ signal }) => fetchReadiness(signal),
    refetchInterval: env.healthPollMs * 2,
    retry: 0,
  });
}
