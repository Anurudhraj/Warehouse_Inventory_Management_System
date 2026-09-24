/**
 * Error model shared by the API client and the UI.
 *
 * The backend renders every failure as:
 *   { "error": { "code": "not_found", "message": "...", "detail": {...} } }
 * (see apps/core/exceptions.py), so the client normalises that shape and keeps
 * the request id for support/debugging.
 */
export interface ApiErrorPayload {
  code: string;
  message: string;
  detail?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail?: unknown;
  readonly requestId?: string;

  constructor(options: {
    status: number;
    code: string;
    message: string;
    detail?: unknown;
    requestId?: string;
  }) {
    super(options.message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.detail = options.detail;
    this.requestId = options.requestId;
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/** Extract a user-presentable message from any thrown value. */
export function toErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.isNetworkError) {
      return 'Cannot reach the API. Check that the backend is running.';
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong.';
}
