import { api } from '@/lib/api/client';
import type { HealthResponse, LivenessResponse, ReadinessResponse } from '@/lib/api/types';

/** GET /api/v1/health/ — deep check (PostgreSQL + Redis). */
export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return api.get<HealthResponse>('/health/', { signal });
}

/** GET /api/v1/health/live/ — process liveness. */
export function fetchLiveness(signal?: AbortSignal): Promise<LivenessResponse> {
  return api.get<LivenessResponse>('/health/live/', { signal, timeoutMs: 5_000 });
}

/** GET /api/v1/health/ready/ — readiness (database reachable). */
export function fetchReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return api.get<ReadinessResponse>('/health/ready/', { signal, timeoutMs: 5_000 });
}
