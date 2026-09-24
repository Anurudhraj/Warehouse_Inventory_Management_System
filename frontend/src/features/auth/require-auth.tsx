/**
 * Route guards.
 *
 * `RequireAuth` keeps anonymous visitors out of the application shell;
 * `RequirePermission` renders a clear "no access" state instead of a broken
 * screen when the signed-in user lacks a capability. Both are UX affordances —
 * the API rejects unauthorised calls regardless of what the UI renders.
 */
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

import { Alert, Card, CardContent, PageHeader } from '@/components/ui';
import { Spinner } from '@/components/ui/spinner';

import { useAuth } from './auth-context';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <div className="flex min-h-[60vh] items-center justify-center" role="status">
        <Spinner className="size-6" />
        <span className="sr-only">Restoring your session…</span>
      </div>
    );
  }

  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}

export function RequirePermission({
  permission,
  anyOf,
  title = 'You do not have access to this area',
  children,
}: {
  permission?: string;
  anyOf?: string[];
  title?: string;
  children: ReactNode;
}) {
  const { hasPermission, hasAnyPermission } = useAuth();
  const allowed = permission
    ? hasPermission(permission)
    : anyOf
      ? hasAnyPermission(anyOf)
      : true;

  if (!allowed) {
    return (
      <div className="space-y-6">
        <PageHeader title={title} description="Ask an administrator to grant you the role that owns this capability." />
        <Card>
          <CardContent className="pt-4">
            <Alert variant="warning" title="Permission required">
              <p className="flex items-center gap-2">
                <ShieldAlert className="size-4" aria-hidden="true" />
                Required permission: <code className="font-mono">{permission ?? anyOf?.join(' or ')}</code>
              </p>
            </Alert>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
