import { Suspense, lazy, type ReactNode } from 'react';
import type { RouteObject } from 'react-router-dom';

import { RouteFallback } from '@/app/route-fallback';
import { AppShell } from '@/components/layout/app-shell';
import { MODULES } from '@/config/modules';
import { RequireAuth, RequirePermission } from '@/features/auth/require-auth';
import { PERMISSIONS } from '@/features/auth/types';

const DashboardPage = lazy(() =>
  import('@/features/dashboard/dashboard-page').then((m) => ({ default: m.DashboardPage })),
);
const SystemHealthPage = lazy(() =>
  import('@/pages/system-health-page').then((m) => ({ default: m.SystemHealthPage })),
);
const ModulePage = lazy(() =>
  import('@/pages/module-page').then((m) => ({ default: m.ModulePage })),
);
const NotFoundPage = lazy(() =>
  import('@/pages/not-found-page').then((m) => ({ default: m.NotFoundPage })),
);
const ServerErrorPage = lazy(() =>
  import('@/pages/server-error-page').then((m) => ({ default: m.ServerErrorPage })),
);
const LoginPage = lazy(() =>
  import('@/features/auth/login-page').then((m) => ({ default: m.LoginPage })),
);
const ForgotPasswordPage = lazy(() =>
  import('@/features/auth/forgot-password-page').then((m) => ({
    default: m.ForgotPasswordPage,
  })),
);
const ResetPasswordPage = lazy(() =>
  import('@/features/auth/reset-password-page').then((m) => ({ default: m.ResetPasswordPage })),
);
const ProfilePage = lazy(() =>
  import('@/features/profile/profile-page').then((m) => ({ default: m.ProfilePage })),
);
const UsersPage = lazy(() =>
  import('@/features/users/users-page').then((m) => ({ default: m.UsersPage })),
);
const RolesPage = lazy(() =>
  import('@/features/security/roles-page').then((m) => ({ default: m.RolesPage })),
);
const PermissionsPage = lazy(() =>
  import('@/features/security/permissions-page').then((m) => ({ default: m.PermissionsPage })),
);

export function suspense(node: ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{node}</Suspense>;
}

/**
 * Route table.
 *
 * Module routes are generated from the shared module registry — adding a
 * module there is enough to register its navigation entry *and* its route.
 * Exported separately from the router instance so tests can render it in a
 * memory router.
 */
export const routes: RouteObject[] = [
  // Public: the sign-in surface itself (no shell, no session).
  { path: '/login', element: suspense(<LoginPage />) },
  { path: '/forgot-password', element: suspense(<ForgotPasswordPage />) },
  { path: '/reset-password', element: suspense(<ResetPasswordPage />) },
  {
    path: '/',
    // Everything behind the shell requires an authenticated, active session.
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    errorElement: suspense(<ServerErrorPage />),
    children: [
      { index: true, element: suspense(<DashboardPage />) },
      { path: 'system/health', element: suspense(<SystemHealthPage />) },
      { path: 'profile', element: suspense(<ProfilePage />) },
      {
        path: 'administration/users',
        element: (
          <RequirePermission permission={PERMISSIONS.users}>
            {suspense(<UsersPage />)}
          </RequirePermission>
        ),
      },
      {
        path: 'administration/roles',
        element: (
          <RequirePermission permission={PERMISSIONS.roles}>
            {suspense(<RolesPage />)}
          </RequirePermission>
        ),
      },
      {
        path: 'administration/permissions',
        element: (
          <RequirePermission permission={PERMISSIONS.permissions}>
            {suspense(<PermissionsPage />)}
          </RequirePermission>
        ),
      },
      ...MODULES.map((module) => ({
        path: module.path.replace(/^\//, ''),
        element: suspense(<ModulePage moduleKey={module.key} />),
      })),
      { path: '*', element: suspense(<NotFoundPage />) },
    ],
  },
];
