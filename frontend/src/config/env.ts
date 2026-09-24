/**
 * Runtime configuration.
 *
 * Everything is provided through Vite environment variables at build time
 * (see frontend/.env.example). Defaults are safe for local development:
 * relative URLs, so the browser always talks to the same origin — in dev the
 * Vite server proxies to Django, in production nginx does.
 */

function readString(key: string, fallback: string): string {
  const value = import.meta.env[key as keyof ImportMetaEnv];
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

function readNumber(key: string, fallback: number): number {
  const raw = import.meta.env[key as keyof ImportMetaEnv];
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export const env = {
  /** Base URL for API calls — relative by default (same-origin). */
  apiBaseUrl: readString('VITE_API_BASE_URL', '/api/v1'),
  /** Human-readable environment label shown in the UI chrome. */
  appEnv: readString('VITE_APP_ENV', import.meta.env.MODE),
  appName: readString('VITE_APP_NAME', 'WIMS'),
  /** Polling interval (ms) for the API health indicator. */
  healthPollMs: readNumber('VITE_HEALTH_POLL_MS', 30_000),
  /** Request timeout (ms) for API calls. */
  requestTimeoutMs: readNumber('VITE_REQUEST_TIMEOUT_MS', 20_000),
} as const;

export const isProduction = import.meta.env.PROD;
export const isDevelopment = import.meta.env.DEV;
