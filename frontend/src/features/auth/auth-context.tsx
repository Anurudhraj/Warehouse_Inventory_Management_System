/**
 * Authentication state for the SPA.
 *
 * The browser session is a Django session cookie; this provider only mirrors
 * it. Everything that matters is enforced by the API — `hasPermission()` exists
 * to *hide* controls, never to grant access.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { setSessionToken } from '@/lib/api/client';
import { isApiError } from '@/lib/api/errors';

import { authApi } from './api';
import type { LoginResponse, SessionPayload, SessionUser } from './types';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthContextValue {
  status: AuthStatus;
  user: SessionUser | null;
  permissions: string[];
  organizations: number[];
  warehouses: number[];
  isPlatformAdmin: boolean;
  /** Re-reads the session; resolves to whether an authenticated session exists. */
  refresh: () => Promise<boolean>;
  signIn: (email: string, password: string) => Promise<LoginResponse>;
  /** Set when credentials were accepted but the browser dropped the session. */
  sessionBlocked: boolean;
  completeMfa: (challengeToken: string, code: string) => Promise<void>;
  signOut: () => Promise<void>;
  setUser: (user: SessionUser) => void;
  hasPermission: (code: string) => boolean;
  hasAnyPermission: (codes: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [sessionBlocked, setSessionBlocked] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const payload = await authApi.session();
      setSession(payload);
      setStatus('authenticated');
      setSessionBlocked(false);
      return true;
    } catch (error) {
      // 401 is the normal "not signed in" answer; anything else means the API
      // is unreachable, which the health indicator already reports.
      setSession(null);
      setStatus('anonymous');
      if (isApiError(error)) return false;
      return false;
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const response = await authApi.login(email, password);
      // Prefer the cookie; use the opaque session token only when the server
      // offered one (embedded deployments where cookies are unusable).
      setSessionToken(response.session_token);
      if (!response.mfa_required) {
        const established = await refresh();
        // Credentials were accepted but the session did not stick: the browser
        // is refusing the session cookie and no token fallback is available.
        setSessionBlocked(!established);
      }
      return response;
    },
    [refresh],
  );

  const completeMfa = useCallback(
    async (challengeToken: string, code: string) => {
      const response = await authApi.verifyMfa(challengeToken, code);
      setSessionToken(response.session_token);
      const established = await refresh();
      setSessionBlocked(!established);
    },
    [refresh],
  );

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setSessionToken(null);
      setSession(null);
      setStatus('anonymous');
      setSessionBlocked(false);
    }
  }, []);

  const setUser = useCallback((user: SessionUser) => {
    setSession((current) => (current ? { ...current, user } : current));
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const permissions = session?.permissions ?? [];
    return {
      status,
      sessionBlocked,
      user: session?.user ?? null,
      permissions,
      organizations: session?.organizations ?? [],
      warehouses: session?.warehouses ?? [],
      isPlatformAdmin: session?.is_platform_admin ?? false,
      refresh,
      signIn,
      completeMfa,
      signOut,
      setUser,
      hasPermission: (code: string) => permissions.includes(code),
      hasAnyPermission: (codes: string[]) => codes.some((code) => permissions.includes(code)),
    };
  }, [completeMfa, refresh, session, sessionBlocked, setUser, signIn, signOut, status]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}

/** Convenience hook for permission-gated UI. */
export function usePermissions() {
  const { hasPermission, hasAnyPermission, permissions, isPlatformAdmin, organizations, warehouses } =
    useAuth();
  return {
    hasPermission,
    hasAnyPermission,
    permissions,
    isPlatformAdmin,
    organizations,
    warehouses,
  };
}
