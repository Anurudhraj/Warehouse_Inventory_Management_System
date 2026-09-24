/**
 * Identity & access types — mirrors the `/api/v1/identity` and
 * `/api/v1/security` response shapes.
 *
 * These describe *what the API returns*; authorization itself is always decided
 * by the backend. The permission list here only drives which controls the UI
 * offers.
 */

export interface OrganizationRef {
  id: number;
  code: string;
  name: string;
}

export type UserStatus = 'invited' | 'active' | 'suspended' | 'deactivated';

export interface SessionUser {
  id: number;
  reference: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name?: string;
  phone: string;
  job_title: string;
  timezone: string;
  locale: string;
  organization: OrganizationRef | null;
  status: UserStatus;
  is_active?: boolean;
  is_email_verified: boolean;
  mfa_required: boolean;
  has_mfa_enabled: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  password_changed_at?: string | null;
  effective_permissions?: string[];
  created_at?: string;
}

export interface SessionPayload {
  authenticated: true;
  user: SessionUser;
  permissions: string[];
  organizations: number[];
  warehouses: number[];
  is_platform_admin: boolean;
}

export interface LoginResponse {
  mfa_required: boolean;
  challenge_token?: string;
  /** Present on a completed sign-in; during the MFA step only email/first name. */
  user: Partial<SessionUser>;
  permissions?: string[];
}

export interface UserSummary {
  id: number;
  reference: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  job_title: string;
  status: UserStatus;
  is_active: boolean;
  organization: number | null;
  last_login_at: string | null;
}

export interface Permission {
  id: number;
  codename: string;
  name: string;
  module: string;
  description: string;
  is_sensitive: boolean;
}

export interface GroupedPermissions {
  count: number;
  modules: Record<string, Omit<Permission, 'id' | 'module'>[]>;
}

export interface Role {
  id: number;
  code: string;
  name: string;
  description: string;
  level: number;
  is_system: boolean;
  is_platform: boolean;
  is_active: boolean;
  organization: number | null;
  organization_name: string | null;
  permission_codes: string[];
  permission_count: number;
  assignment_count: number;
  modules: string[];
}

export interface RoleAssignment {
  id: number;
  user: number;
  user_email: string;
  user_name: string;
  role: number;
  role_code: string;
  role_name: string;
  role_level: number;
  organization: number | null;
  organization_name: string | null;
  warehouse: number | null;
  warehouse_name: string | null;
  scope: string;
  is_active: boolean;
  is_effective: boolean;
  expires_at: string | null;
  granted_by: number | null;
  granted_at: string;
}

export interface MfaStatus {
  enabled: boolean;
  required: boolean;
  device_name: string;
  confirmed_at: string | null;
  last_used_at: string | null;
  recovery_codes_remaining: number;
  devices: {
    id: number;
    name: string;
    device_type: string;
    confirmed_at: string | null;
    last_used_at: string | null;
  }[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Permissions that gate each Part-2 screen (backend remains authoritative). */
export const PERMISSIONS = {
  users: 'user.view',
  usersManage: 'user.manage',
  roles: 'role.view',
  rolesManage: 'role.manage',
  permissions: 'role.view',
  assignmentsManage: 'assignment.manage',
  sessions: 'session.view',
  audit: 'audit.view',
} as const;
