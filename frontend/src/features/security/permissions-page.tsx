/**
 * Permission catalog.
 *
 * Permissions are declared in code (`apps/security/permission_registry.py`) and
 * projected into the database by `manage.py sync_rbac`, so this screen is
 * deliberately read-only: it documents what exists and who may hold it.
 */
import { useQuery } from '@tanstack/react-query';
import { KeySquare, Lock } from 'lucide-react';

import {
  Alert,
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  PageHeader,
  Spinner,
} from '@/components/ui';
import { authApi } from '@/features/auth/api';
import { isApiError } from '@/lib/api/errors';
import { titleCase } from '@/lib/utils/format';

export function PermissionsPage() {
  const query = useQuery({
    queryKey: ['security', 'permissions', 'grouped'],
    queryFn: ({ signal }) => authApi.groupedPermissions(signal),
  });

  const modules = Object.entries(query.data?.modules ?? {});

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Permissions"
        description="The permission registry the whole platform authorizes against. Grant them through roles — never directly to a user."
      />

      <Alert variant="info" title="Enforced on the backend">
        Every endpoint re-checks the caller's scoped permissions. Hiding a control in
        the UI never protects anything on its own.
      </Alert>

      {query.isPending ? (
        <div className="flex justify-center py-16" role="status">
          <Spinner className="size-6" />
        </div>
      ) : query.isError ? (
        <Alert variant="danger" title="Could not load permissions">
          {isApiError(query.error) ? query.error.message : 'Your role may not include role.view.'}
        </Alert>
      ) : modules.length === 0 ? (
        <EmptyState
          icon={<KeySquare className="size-5" />}
          title="No permissions registered"
          description="Run `manage.py sync_rbac` to project the registry."
        />
      ) : (
        <>
          <p className="text-muted-foreground text-xs">
            {query.data?.count} permissions across {modules.length} modules.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            {modules.map(([module, permissions]) => (
              <Card key={module}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-2">
                    <span>{titleCase(module)}</span>
                    <Badge variant="outline">{permissions.length}</Badge>
                  </CardTitle>
                  <CardDescription>{module} capability set</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2.5">
                    {permissions.map((permission) => (
                      <li key={permission.codename}>
                        <div className="flex items-center gap-2">
                          <code className="text-[12px] font-medium">{permission.codename}</code>
                          {permission.is_sensitive ? (
                            <Badge variant="warning" dot>
                              <Lock className="size-3" aria-hidden="true" /> sensitive
                            </Badge>
                          ) : null}
                        </div>
                        <p className="text-muted-foreground text-xs">{permission.description}</p>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
