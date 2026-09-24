/**
 * User administration: list, invite, activate/deactivate and assign roles.
 *
 * Everything here is scoped by the API to the organizations the caller can
 * reach; the screen merely reflects that.
 */
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { UserPlus, UserRoundCheck, UserRoundX } from 'lucide-react';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import { authApi } from '@/features/auth/api';
import { usePermissions } from '@/features/auth/auth-context';
import { PERMISSIONS } from '@/features/auth/types';
import { isApiError } from '@/lib/api/errors';
import { formatDateTime } from '@/lib/utils/format';

const emptyInvite = {
  email: '',
  first_name: '',
  last_name: '',
  job_title: '',
  password: '',
};

export function UsersPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermissions();
  const canManage = hasPermission(PERMISSIONS.usersManage);

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [invite, setInvite] = useState(emptyInvite);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ['identity', 'users', { search, status }],
    queryFn: ({ signal }) =>
      authApi.users({ search: search || undefined, status: status || undefined }, signal),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['identity', 'users'] });

  const createUser = useMutation({
    mutationFn: () =>
      authApi.createUser({
        email: invite.email,
        first_name: invite.first_name,
        last_name: invite.last_name,
        job_title: invite.job_title || undefined,
        password: invite.password || undefined,
        send_verification_email: !invite.password,
      }),
    onSuccess: (created) => {
      setNotice(
        invite.password
          ? `Temporary password set for ${created.email}. They must change it at first sign-in.`
          : `Invitation sent to ${created.email}.`,
      );
      setInvite(emptyInvite);
      setError(null);
      void invalidate();
    },
    onError: (caught) => {
      setNotice(null);
      setError(isApiError(caught) ? caught.message : 'The user could not be created.');
    },
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      active ? authApi.activateUser(id) : authApi.deactivateUser(id, 'deactivated from console'),
    onSuccess: () => {
      setError(null);
      void invalidate();
    },
    onError: (caught) => setError(isApiError(caught) ? caught.message : 'The change was refused.'),
  });

  const users = usersQuery.data?.results ?? [];
  const total = usersQuery.data?.count ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Users"
        description="Accounts in the organizations you administer. Deactivating a user revokes their sessions and pauses their role assignments."
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

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardContent className="space-y-4 pt-4">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Search" htmlFor="user-search" className="min-w-[200px] flex-1">
                <Input
                  id="user-search"
                  placeholder="Name, email or reference"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </Field>
              <Field label="Status" htmlFor="user-status" className="w-40">
                <Select
                  id="user-status"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="">All</option>
                  <option value="active">Active</option>
                  <option value="invited">Invited</option>
                  <option value="deactivated">Deactivated</option>
                </Select>
              </Field>
            </div>

            {usersQuery.isPending ? (
              <div className="flex justify-center py-10" role="status">
                <Spinner className="size-6" />
              </div>
            ) : usersQuery.isError ? (
              <Alert variant="danger" title="Could not load users">
                {isApiError(usersQuery.error) ? usersQuery.error.message : 'Please retry.'}
              </Alert>
            ) : users.length === 0 ? (
              <EmptyState
                icon={<UserPlus className="size-5" />}
                title="No users match"
                description="Adjust the filters or invite someone new."
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Last sign-in</TableHead>
                    {canManage ? <TableHead className="text-right">Actions</TableHead> : null}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{user.full_name}</span>
                          <span className="text-muted-foreground text-xs">{user.email}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={user.is_active ? 'success' : 'danger'}>{user.status}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {user.last_login_at ? formatDateTime(user.last_login_at) : 'never'}
                      </TableCell>
                      {canManage ? (
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant={user.is_active ? 'outline' : 'primary'}
                            loading={toggleActive.isPending}
                            onClick={() => toggleActive.mutate({ id: user.id, active: !user.is_active })}
                            icon={
                              user.is_active ? (
                                <UserRoundX className="size-3.5" />
                              ) : (
                                <UserRoundCheck className="size-3.5" />
                              )
                            }
                          >
                            {user.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </TableCell>
                      ) : null}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            <p className="text-muted-foreground text-xs" aria-live="polite">
              {total} account{total === 1 ? '' : 's'} visible to you.
            </p>
          </CardContent>
        </Card>

        <RoleAssignmentPanel enabled={canManage} onError={setError} onDone={setNotice} />

        {canManage ? (
          <Card className="lg:col-span-2">
            <CardContent className="space-y-4 pt-4">
              <h2 className="text-sm font-semibold">Invite a user</h2>
              <p className="text-muted-foreground text-xs">
                Without a password the account is created as <em>invited</em> and receives a
                verification email. With a temporary password the user must change it at first
                sign-in.
              </p>
              <form
                className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                onSubmit={(event) => {
                  event.preventDefault();
                  createUser.mutate();
                }}
              >
                <Field label="Email" htmlFor="invite-email">
                  <Input
                    id="invite-email"
                    type="email"
                    required
                    value={invite.email}
                    onChange={(event) => setInvite({ ...invite, email: event.target.value })}
                  />
                </Field>
                <Field label="First name" htmlFor="invite-first">
                  <Input
                    id="invite-first"
                    required
                    value={invite.first_name}
                    onChange={(event) => setInvite({ ...invite, first_name: event.target.value })}
                  />
                </Field>
                <Field label="Last name" htmlFor="invite-last">
                  <Input
                    id="invite-last"
                    required
                    value={invite.last_name}
                    onChange={(event) => setInvite({ ...invite, last_name: event.target.value })}
                  />
                </Field>
                <Field label="Job title" htmlFor="invite-job">
                  <Input
                    id="invite-job"
                    value={invite.job_title}
                    onChange={(event) => setInvite({ ...invite, job_title: event.target.value })}
                  />
                </Field>
                <Field
                  label="Temporary password"
                  htmlFor="invite-password"
                  hint="Optional — minimum 12 characters"
                >
                  <Input
                    id="invite-password"
                    type="password"
                    autoComplete="new-password"
                    value={invite.password}
                    onChange={(event) => setInvite({ ...invite, password: event.target.value })}
                  />
                </Field>
                <div className="flex items-end">
                  <Button type="submit" loading={createUser.isPending} icon={<UserPlus className="size-4" />}>
                    Create user
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function RoleAssignmentPanel({
  enabled,
  onError,
  onDone,
}: {
  enabled: boolean;
  onError: (message: string) => void;
  onDone: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const { organizations, hasPermission } = usePermissions();
  const [target, setTarget] = useState('');
  const [roleId, setRoleId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');

  const organization = organizations[0];
  const canAssign = enabled && hasPermission(PERMISSIONS.assignmentsManage);

  const usersQuery = useQuery({
    queryKey: ['identity', 'users', 'picker'],
    queryFn: ({ signal }) => authApi.users({ page_size: 100 }, signal),
    enabled: canAssign,
  });

  const rolesQuery = useQuery({
    queryKey: ['security', 'roles', 'grantable', organization],
    queryFn: ({ signal }) => authApi.grantableRoles(organization, signal),
    enabled: canAssign,
  });

  const assignmentsQuery = useQuery({
    queryKey: ['security', 'assignments'],
    queryFn: ({ signal }) => authApi.assignments({ page_size: 25 }, signal),
    enabled: canAssign,
  });

  const create = useMutation({
    mutationFn: () =>
      authApi.createAssignment({
        user: Number(target),
        role: Number(roleId),
        organization: organization ?? null,
        warehouse: warehouseId ? Number(warehouseId) : null,
      }),
    onSuccess: () => {
      onDone('Role granted. It is effective immediately.');
      setTarget('');
      setRoleId('');
      setWarehouseId('');
      void queryClient.invalidateQueries({ queryKey: ['security', 'assignments'] });
    },
    onError: (caught) => onError(isApiError(caught) ? caught.message : 'The grant was refused.'),
  });

  const revoke = useMutation({
    mutationFn: (id: number) => authApi.revokeAssignment(id),
    onSuccess: () => {
      onDone('Role revoked.');
      void queryClient.invalidateQueries({ queryKey: ['security', 'assignments'] });
    },
    onError: (caught) => onError(isApiError(caught) ? caught.message : 'The change was refused.'),
  });

  const roles = useMemo(() => rolesQuery.data?.results ?? [], [rolesQuery.data]);
  const users = usersQuery.data?.results ?? [];
  const assignments = assignmentsQuery.data?.results ?? [];

  return (
    <Card>
      <CardContent className="space-y-4 pt-4">
        <h2 className="text-sm font-semibold">Grant a role</h2>

        {!canAssign ? (
          <p className="text-muted-foreground text-xs">
            You need <code className="font-mono">assignment.manage</code> to grant roles.
          </p>
        ) : (
          <>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                create.mutate();
              }}
            >
              <Field label="User" htmlFor="assignment-user">
                <Select
                  id="assignment-user"
                  required
                  value={target}
                  onChange={(event) => setTarget(event.target.value)}
                >
                  <option value="">Select a user…</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.full_name} — {user.email}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field
                label="Role"
                htmlFor="assignment-role"
                hint="Only roles you already hold and may delegate."
              >
                <Select
                  id="assignment-role"
                  required
                  value={roleId}
                  onChange={(event) => setRoleId(event.target.value)}
                >
                  <option value="">Select a role…</option>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name} (level {role.level})
                    </option>
                  ))}
                </Select>
              </Field>

              <Field
                label="Warehouse scope"
                htmlFor="assignment-warehouse"
                hint="Leave empty for the whole organization."
              >
                <Select
                  id="assignment-warehouse"
                  value={warehouseId}
                  onChange={(event) => setWarehouseId(event.target.value)}
                >
                  <option value="">All warehouses</option>
                </Select>
              </Field>

              <Button type="submit" loading={create.isPending}>
                Grant role
              </Button>
            </form>

            <div className="border-border border-t pt-4">
              <h3 className="mb-2 text-xs font-semibold tracking-wide uppercase">Recent grants</h3>
              {assignments.length === 0 ? (
                <p className="text-muted-foreground text-xs">No grants visible in your scope.</p>
              ) : (
                <ul className="space-y-2">
                  {assignments.slice(0, 6).map((assignment) => (
                    <li
                      key={assignment.id}
                      className="flex items-center justify-between gap-2 text-xs"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{assignment.user_email}</span>
                        <span className="text-muted-foreground">
                          {assignment.role_name} · {assignment.scope}
                        </span>
                      </span>
                      {assignment.is_effective ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => revoke.mutate(assignment.id)}
                          loading={revoke.isPending}
                        >
                          Revoke
                        </Button>
                      ) : (
                        <Badge variant="outline">inactive</Badge>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
