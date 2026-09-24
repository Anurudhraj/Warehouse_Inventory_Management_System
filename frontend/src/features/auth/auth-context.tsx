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
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<LoginResponse>;
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

  const refresh = useCallback(async () => {
    try {
      const payload = await authApi.session();
      setSession(payload);
      setStatus('authenticated');
    } catch (error) {
      // 401 is the normal "not signed in" answer; anything else means the API
      // is unreachable, which the health indicator already reports.
      if (isApiError(error) && error.status === 401) {
        setSession(null);
        setStatus('anonymous');
        return;
      }
      setSession(null);
      setStatus('anonymous');
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    if (!response.mfa_required) await refresh();
    return response;
  }, [refresh]);

  const completeMfa = useCallback(
    async (challengeToken: string, code: string) => {
      await authApi.verifyMfa(challengeToken, code);
      await refresh();
    },
    [refresh],
  );

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setSession(null);
      setStatus('anonymous');
    }
  }, []);

  const setUser = useCallback((user: SessionUser) => {
    setSession((current) => (current ? { ...current, user } : current));
  }, []);

  const value = useMemo<AuthContextValue>(() => {
    const permissions = session?.permissions ?? [];
    return {
      status,
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
  }, [completeMfa, refresh, session, setUser, signIn, signOut, status]);

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
