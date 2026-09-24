/** Identity & access API calls (thin wrappers over the shared client). */
import { api } from '@/lib/api/client';

import type {
  GroupedPermissions,
  LoginResponse,
  MfaStatus,
  Paginated,
  Permission,
  Role,
  RoleAssignment,
  SessionPayload,
  SessionUser,
  UserSummary,
} from './types';

export const authApi = {
  // --- authentication ---------------------------------------------------
  session: (signal?: AbortSignal) =>
    api.get<SessionPayload>('/identity/auth/session/', { signal }),
  // ``token_auth`` asks the server for the bearer fallback as well as the
  // cookie. Harmless when the server does not offer it (the field is null) and
  // the difference between "works in the preview" and "stuck on sign-in" when
  // the browser refuses third-party cookies.
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/identity/auth/login/', { email, password, token_auth: true }),
  verifyMfa: (challengeToken: string, code: string) =>
    api.post<LoginResponse>('/identity/auth/mfa/verify/', {
      challenge_token: challengeToken,
      code,
      token_auth: true,
    }),
  logout: () => api.post<void>('/identity/auth/logout/'),

  // --- passwords --------------------------------------------------------
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<{ detail: string }>('/identity/auth/password/change/', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  requestPasswordReset: (email: string) =>
    api.post<{ detail: string }>('/identity/auth/password/reset/', { email }),
  validateResetToken: (token: string) =>
    api.post<{ valid: boolean; purpose: string }>('/identity/auth/password/reset/validate/', {
      token,
      purpose: 'password_reset',
    }),
  confirmPasswordReset: (token: string, newPassword: string) =>
    api.post<{ detail: string }>('/identity/auth/password/reset/confirm/', {
      token,
      new_password: newPassword,
    }),

  // --- profile ----------------------------------------------------------
  profile: (signal?: AbortSignal) => api.get<SessionUser>('/identity/profile/', { signal }),
  updateProfile: (payload: Partial<SessionUser>) =>
    api.patch<SessionUser>('/identity/profile/', payload),

  // --- MFA --------------------------------------------------------------
  mfaStatus: (signal?: AbortSignal) => api.get<MfaStatus>('/identity/mfa/', { signal }),
  mfaEnrol: (name = 'Authenticator app') =>
    api.post<{ secret: string; otpauth_uri: string; device: unknown; detail: string }>(
      '/identity/mfa/enrol/',
      { name },
    ),
  mfaConfirm: (code: string) =>
    api.post<{ recovery_codes: string[]; detail: string }>('/identity/mfa/confirm/', { code }),
  mfaDisable: (password: string) =>
    api.post<{ detail: string }>('/identity/mfa/disable/', { password }),
  mfaRecoveryCodes: () =>
    api.post<{ recovery_codes: string[] }>('/identity/mfa/recovery-codes/'),

  // --- administration ---------------------------------------------------
  users: (query?: Record<string, string | number | undefined>, signal?: AbortSignal) =>
    api.get<Paginated<UserSummary>>('/identity/users/', { query, signal }),
  createUser: (payload: {
    email: string;
    first_name: string;
    last_name: string;
    job_title?: string;
    phone?: string;
    password?: string;
    organization_id?: number | null;
    send_verification_email?: boolean;
    mfa_required?: boolean;
  }) => api.post<SessionUser>('/identity/users/', payload),
  activateUser: (id: number) => api.post<SessionUser>(`/identity/users/${id}/activate/`),
  deactivateUser: (id: number, reason: string) =>
    api.post<SessionUser>(`/identity/users/${id}/deactivate/`, { reason }),
  setUserPassword: (id: number, password: string) =>
    api.post<{ detail: string }>(`/identity/users/${id}/set-password/`, { password }),

  permissions: (signal?: AbortSignal) =>
    api.get<Paginated<Permission>>('/security/permissions/', { query: { page_size: 200 }, signal }),
  groupedPermissions: (signal?: AbortSignal) =>
    api.get<GroupedPermissions>('/security/permissions/grouped/', { signal }),
  roles: (query?: Record<string, string | number | undefined>, signal?: AbortSignal) =>
    api.get<Paginated<Role>>('/security/roles/', { query, signal }),
  grantableRoles: (organization?: number, signal?: AbortSignal) =>
    api.get<{ count: number; results: Role[] }>('/security/roles/grantable/', {
      query: { organization },
      signal,
    }),
  createRole: (payload: {
    code: string;
    name: string;
    description?: string;
    level?: number;
    organization?: number | null;
    permission_codes: string[];
  }) => api.post<Role>('/security/roles/', payload),
  setRolePermissions: (id: number, permissionCodes: string[]) =>
    api.put<Role>(`/security/roles/${id}/permissions/`, { permission_codes: permissionCodes }),

  assignments: (query?: Record<string, string | number | undefined>, signal?: AbortSignal) =>
    api.get<Paginated<RoleAssignment>>('/security/assignments/', { query, signal }),
  createAssignment: (payload: {
    user: number;
    role: number;
    organization?: number | null;
    warehouse?: number | null;
    expires_at?: string | null;
    note?: string;
  }) => api.post<RoleAssignment>('/security/assignments/', payload),
  revokeAssignment: (id: number) => api.delete<void>(`/security/assignments/${id}/`),
};
