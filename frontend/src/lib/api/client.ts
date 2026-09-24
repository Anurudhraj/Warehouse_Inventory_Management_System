/**
 * Thin, typed fetch wrapper for the versioned REST API.
 *
 * Responsibilities: base URL + versioned path building, JSON encoding,
 * CSRF handling for Django session auth, timeouts/aborts, error normalisation
 * into `ApiError`, and request-id propagation.
 */
import { env } from '@/config/env';

import { ApiError } from './errors';

export type QueryValue = string | number | boolean | null | undefined;

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** JSON-serialisable request body (serialised automatically). */
  body?: unknown;
  /** Query string parameters; `undefined`/`null` values are dropped. */
  query?: Record<string, QueryValue | QueryValue[]>;
  /** Abort/timeout in milliseconds (defaults to VITE_REQUEST_TIMEOUT_MS). */
  timeoutMs?: number;
}

const CSRF_COOKIE_NAMES = ['csrftoken', '__Host-csrftoken'];
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE']);

/**
 * Bearer fallback for the (opt-in) session-token path.
 *
 * The HttpOnly session cookie stays the primary credential; this exists for
 * deployments where the browser will not store or send it — most importantly a
 * cross-site embedded preview, where ``SameSite=Lax`` cookies are dropped on
 * XHR. The token is the same server-tracked session credential, so revocation
 * and expiry behave identically; it lives in ``sessionStorage`` (cleared when
 * the tab closes, never shared across tabs) and is only ever sent to the API.
 */
const TOKEN_STORAGE_KEY = 'wims.session_token';

export function getSessionToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setSessionToken(token: string | null | undefined): void {
  try {
    if (token) window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    /* storage unavailable (private mode) — cookie auth still applies */
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null;
}

function getCsrfToken(): string | null {
  for (const name of CSRF_COOKIE_NAMES) {
    const token = readCookie(name);
    if (token) return token;
  }
  return null;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = env.apiBaseUrl.replace(/\/$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  const url = `${base}${suffix}`;

  if (!query) return url;

  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      value.forEach((item) => item != null && search.append(key, String(item)));
    } else {
      search.append(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const body = payload as
    | { error?: { code?: string; message?: string; detail?: unknown }; detail?: string }
    | null;

  const code = body?.error?.code ?? `http_${response.status}`;
  const message =
    body?.error?.message ??
    body?.detail ??
    (response.statusText || `Request failed with status ${response.status}`);

  return new ApiError({
    status: response.status,
    code,
    message,
    detail: body?.error?.detail,
    requestId: response.headers.get('X-Request-ID') ?? undefined,
  });
}

/** Perform an API request and return the parsed JSON body. */
export async function apiRequest<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const { body, query, timeoutMs = env.requestTimeoutMs, headers, ...rest } = options;
  const method = (rest.method ?? (body === undefined ? 'GET' : 'POST')).toUpperCase();

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  const requestHeaders = new Headers(headers);
  requestHeaders.set('Accept', 'application/json');
  if (body !== undefined && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json');
  }
  const sessionToken = getSessionToken();
  if (sessionToken) requestHeaders.set('Authorization', `Bearer ${sessionToken}`);
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) requestHeaders.set('X-CSRFToken', csrfToken);
  }

  try {
    const response = await fetch(buildUrl(path, query), {
      ...rest,
      method,
      headers: requestHeaders,
      credentials: 'include',
      signal: rest.signal ?? controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (!response.ok) {
      const failure = await parseError(response);
      if (failure.status === 401 && sessionToken) {
        // The stored token is dead (revoked/expired session): drop it so the
        // app falls back to "signed out" instead of retrying with it forever.
        setSessionToken(null);
      }
      throw failure;
    }
    if (response.status === 204) return undefined as TResponse;

    const contentType = response.headers.get('Content-Type') ?? '';
    if (!contentType.includes('application/json')) {
      return (await response.text()) as unknown as TResponse;
    }
    return (await response.json()) as TResponse;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError({
        status: 0,
        code: 'timeout',
        message: `The request timed out after ${timeoutMs}ms.`,
      });
    }
    throw new ApiError({
      status: 0,
      code: 'network_error',
      message: 'Network request failed.',
      detail: error,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'DELETE' }),
} as const;
