/** Shapes returned by the backend API (Part 1: platform endpoints). */

export interface HealthCheck {
  status: 'ok' | 'error';
  detail?: string;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  environment: string;
  version: string;
  django_version: string;
  checks: {
    database: HealthCheck;
    redis: HealthCheck;
    [key: string]: HealthCheck;
  };
}

export interface LivenessResponse {
  status: 'alive';
}

export interface ReadinessResponse {
  status: 'ready' | 'degraded';
  checks: {
    database: HealthCheck;
    [key: string]: HealthCheck;
  };
}

/** DRF pagination envelope used by list endpoints. */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    detail?: unknown;
  };
}
