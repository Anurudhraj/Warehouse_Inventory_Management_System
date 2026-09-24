/**
 * Role management.
 *
 * System roles come from the code-defined registry (and are therefore
 * read-only); organizations can additionally maintain custom roles, bounded by
 * the authority of whoever edits them — the API enforces every bound.
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ShieldPlus, ShieldCheck } from 'lucide-react';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
} from '@/components/ui';
import { authApi } from '@/features/auth/api';
import { usePermissions } from '@/features/auth/auth-context';
import { PERMISSIONS, type Role } from '@/features/auth/types';
import { isApiError } from '@/lib/api/errors';

export function RolesPage() {
  const queryClient = useQueryClient();
  const { hasPermission, organizations } = usePermissions();
  const canManage = hasPermission(PERMISSIONS.rolesManage);

  const [selected, setSelected] = useState<Role | null>(null);
  const [draft, setDraft] = useState({ code: '', name: '', description: '', level: '40' });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [permissionDraft, setPermissionDraft] = useState<string[] | null>(null);

  const rolesQuery = useQuery({
    queryKey: ['security', 'roles'],
    queryFn: ({ signal }) => authApi.roles({ page_size: 100 }, signal),
  });

  const permissionsQuery = useQuery({
    queryKey: ['security', 'permissions', 'grouped'],
    queryFn: ({ signal }) => authApi.groupedPermissions(signal),
  });

  const createRole = useMutation({
    mutationFn: () =>
      authApi.createRole({
        code: draft.code,
        name: draft.name,
        description: draft.description,
        level: Number(draft.level) || 40,
        organization: organizations[0] ?? null,
        permission_codes: permissionDraft ?? [],
      }),
    onSuccess: (role) => {
      setNotice(`Role “${role.name}” created with ${role.permission_count} permissions.`);
      setError(null);
      setDraft({ code: '', name: '', description: '', level: '40' });
      setPermissionDraft(null);
      void queryClient.invalidateQueries({ queryKey: ['security', 'roles'] });
    },
    onError: (caught) =>
      setError(isApiError(caught) ? caught.message : 'The role could not be created.'),
  });

  const savePermissions = useMutation({
    mutationFn: (role: Role) => authApi.setRolePermissions(role.id, permissionDraft ?? []),
    onSuccess: (role) => {
      setSelected(role);
      setPermissionDraft(null);
      setError(null);
      setNotice(`Permissions updated for “${role.name}”.`);
      void queryClient.invalidateQueries({ queryKey: ['security', 'roles'] });
    },
    onError: (caught) =>
      setError(isApiError(caught) ? caught.message : 'The permission change was refused.'),
  });

  const roles = rolesQuery.data?.results ?? [];
  const canEdit = (role: Role) => canManage && !role.is_system;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Roles"
        description="Roles bundle permissions and carry an authority level. You can only delegate authority you already hold, and never above level 90."
      />

      {notice ? (
        <Alert variant="success" title="Done">
          {notice}
        </Alert>
      ) : null}
      {error ? (
        <Alert variant="danger" title="Refused">
          {error}
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Role catalog ({roles.length})</CardTitle>
            <CardDescription>System roles are read-only by design.</CardDescription>
          </CardHeader>
          <CardContent>
            {rolesQuery.isPending ? (
              <div className="flex justify-center py-10" role="status">
                <Spinner className="size-6" />
              </div>
            ) : roles.length === 0 ? (
              <EmptyState title="No roles visible" description="Your scope has no roles yet." />
            ) : (
              <ul className="divide-border divide-y">
                {roles.map((role) => (
                  <li key={role.id} className="flex items-start justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{role.name}</span>
                        <Badge variant={role.is_system ? 'info' : 'outline'} dot>
                          {role.is_system ? 'system' : 'custom'}
                        </Badge>
                        {role.is_platform ? <Badge variant="primary">platform</Badge> : null}
                      </div>
                      <p className="text-muted-foreground mt-0.5 text-xs">
                        <code className="font-mono">{role.code}</code> · level {role.level} ·{' '}
                        {role.permission_count} permissions · {role.assignment_count} assignments
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelected(role);
                        setPermissionDraft(role.permission_codes);
                      }}
                    >
                      {canEdit(role) ? 'Edit' : 'View'}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          {selected ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="size-4" aria-hidden="true" />
                  {selected.name}
                </CardTitle>
                <CardDescription>
                  {selected.is_system
                    ? 'Defined by the platform registry — clone it to customize.'
                    : 'Custom role: permissions can be adjusted within your own authority.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {permissionsQuery.isPending ? (
                  <Spinner className="size-5" />
                ) : (
                  Object.entries(permissionsQuery.data?.modules ?? {}).map(([module, permissions]) => (
                    <div key={module} className="space-y-1">
                      <p className="text-muted-foreground text-[11px] font-semibold tracking-widest uppercase">
                        {module}
                      </p>
                      <ul className="space-y-1">
                        {permissions.map((permission) => {
                          const checked = (permissionDraft ?? selected.permission_codes).includes(
                            permission.codename,
                          );
                          return (
                            <li key={permission.codename}>
                              <label className="hover:bg-muted/60 flex items-start gap-2 rounded-md px-2 py-1 text-xs">
                                <input
                                  type="checkbox"
                                  className="mt-0.5"
                                  checked={checked}
                                  disabled={!canEdit(selected)}
                                  onChange={(event) => {
                                    const current = permissionDraft ?? selected.permission_codes;
                                    setPermissionDraft(
                                      event.target.checked
                                        ? [...current, permission.codename]
                                        : current.filter((code) => code !== permission.codename),
                                    );
                                  }}
                                />
                                <span>
                                  <span className="font-mono">{permission.codename}</span>
                                  {permission.is_sensitive ? (
                                    <Badge variant="warning" className="ms-2">
                                      sensitive
                                    </Badge>
                                  ) : null}
                                  <span className="text-muted-foreground block">
                                    {permission.description}
                                  </span>
                                </span>
                              </label>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))
                )}

                {canEdit(selected) && permissionDraft ? (
                  <Button
                    loading={savePermissions.isPending}
                    onClick={() => savePermissions.mutate(selected)}
                  >
                    Save permissions
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {canManage ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldPlus className="size-4" aria-hidden="true" />
                  New custom role
                </CardTitle>
                <CardDescription>
                  Level must stay at or below your own authority ({'≤ 90'}).
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form
                  className="space-y-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    createRole.mutate();
                  }}
                >
                  <Field label="Code" htmlFor="role-code" hint="lowercase_with_underscores">
                    <Input
                      id="role-code"
                      required
                      value={draft.code}
                      onChange={(event) => setDraft({ ...draft, code: event.target.value })}
                    />
                  </Field>
                  <Field label="Name" htmlFor="role-name">
                    <Input
                      id="role-name"
                      required
                      value={draft.name}
                      onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                    />
                  </Field>
                  <Field label="Authority level" htmlFor="role-level">
                    <Select
                      id="role-level"
                      value={draft.level}
                      onChange={(event) => setDraft({ ...draft, level: event.target.value })}
                    >
                      {[20, 30, 40, 50, 60, 70].map((level) => (
                        <option key={level} value={level}>
                          {level}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Description" htmlFor="role-description">
                    <Input
                      id="role-description"
                      value={draft.description}
                      onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                    />
                  </Field>
                  <Button type="submit" loading={createRole.isPending}>
                    Create role
                  </Button>
                </form>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
