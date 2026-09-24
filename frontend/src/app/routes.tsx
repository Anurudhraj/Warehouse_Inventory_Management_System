import { Suspense, lazy, type ReactNode } from 'react';
import type { RouteObject } from 'react-router-dom';

import { RouteFallback } from '@/app/route-fallback';
import { AppShell } from '@/components/layout/app-shell';
import { MODULES } from '@/config/modules';

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
  {
    path: '/',
    element: <AppShell />,
    errorElement: suspense(<ServerErrorPage />),
    children: [
      { index: true, element: suspense(<DashboardPage />) },
      { path: 'system/health', element: suspense(<SystemHealthPage />) },
      ...MODULES.map((module) => ({
        path: module.path.replace(/^\//, ''),
        element: suspense(<ModulePage moduleKey={module.key} />),
      })),
      { path: '*', element: suspense(<NotFoundPage />) },
    ],
  },
];
