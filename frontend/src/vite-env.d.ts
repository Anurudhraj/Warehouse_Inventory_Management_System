/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for API requests (default: `/api/v1`, same-origin). */
  readonly VITE_API_BASE_URL?: string;
  /** Environment label displayed in the UI chrome. */
  readonly VITE_APP_ENV?: string;
  /** Product name shown in the sidebar. */
  readonly VITE_APP_NAME?: string;
  /** Health polling interval in milliseconds. */
  readonly VITE_HEALTH_POLL_MS?: string;
  /** Default request timeout in milliseconds. */
  readonly VITE_REQUEST_TIMEOUT_MS?: string;
  /** Dev-server port (vite.config.ts). */
  readonly VITE_PORT?: string;
  /** Backend origin the dev server proxies `/api` to. */
  readonly VITE_DEV_API_TARGET?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
