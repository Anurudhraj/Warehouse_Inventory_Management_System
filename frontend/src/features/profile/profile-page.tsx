/** Self-service profile: identity, editable details, password and MFA. */
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { BadgeCheck, KeyRound, Lock, ShieldCheck, Smartphone } from 'lucide-react';

import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Field,
  Input,
  PageHeader,
} from '@/components/ui';
import { useAuth } from '@/features/auth/auth-context';
import { authApi } from '@/features/auth/api';
import type { SessionUser } from '@/features/auth/types';
import { isApiError } from '@/lib/api/errors';
import { formatDateTime, initials } from '@/lib/utils/format';

function messageOf(error: unknown, fallback: string): string {
  return isApiError(error) ? error.message : fallback;
}

export function ProfilePage() {
  const { user, setUser, permissions, isPlatformAdmin } = useAuth();

  if (!user) return null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Account"
        title="My profile"
        description="Your identity, contact details and security settings."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <IdentityCard user={user} isPlatformAdmin={isPlatformAdmin} />

        <div className="space-y-6 lg:col-span-2">
          <DetailsCard user={user} onSaved={setUser} />
          <PasswordCard />
          <MfaCard user={user} onChanged={setUser} />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Effective permissions ({permissions.length})</CardTitle>
          <CardDescription>
            Decided by the API on every request — the UI only reflects them.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {permissions.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No permissions yet. Ask an administrator to assign you a role.
            </p>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {permissions.map((code) => (
                <li key={code}>
                  <Badge variant="outline" className="font-mono text-[11px]">
                    {code}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function IdentityCard({ user, isPlatformAdmin }: { user: SessionUser; isPlatformAdmin: boolean }) {
  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <div className="flex items-center gap-3">
          <span className="bg-primary text-primary-foreground flex size-12 items-center justify-center rounded-full text-sm font-semibold">
            {initials(user.full_name ?? `${user.first_name} ${user.last_name}`)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">
              {user.first_name} {user.last_name}
            </p>
            <p className="text-muted-foreground truncate text-xs">{user.email}</p>
          </div>
        </div>

        <dl className="space-y-2 text-xs">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted-foreground">Employee reference</dt>
            <dd className="font-mono">{user.reference}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted-foreground">Organization</dt>
            <dd>{user.organization?.name ?? 'Platform (no tenant)'}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted-foreground">Job title</dt>
            <dd>{user.job_title || '—'}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted-foreground">Last sign-in</dt>
            <dd>{user.last_login_at ? formatDateTime(user.last_login_at) : '—'}</dd>
          </div>
        </dl>

        <div className="flex flex-wrap gap-1.5">
          <Badge variant={user.is_active === false ? 'danger' : 'success'}>
            {user.status}
          </Badge>
          {isPlatformAdmin ? <Badge variant="primary">Platform admin</Badge> : null}
          <Badge variant={user.is_email_verified ? 'success' : 'warning'}>
            {user.is_email_verified ? 'email verified' : 'email unverified'}
          </Badge>
          {user.must_change_password ? <Badge variant="warning">password change due</Badge> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function DetailsCard({ user, onSaved }: { user: SessionUser; onSaved: (user: SessionUser) => void }) {
  const [form, setForm] = useState({
    first_name: user.first_name,
    last_name: user.last_name,
    phone: user.phone ?? '',
    job_title: user.job_title ?? '',
    timezone: user.timezone ?? 'UTC',
  });
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: () => authApi.updateProfile(form),
    onSuccess: (updated) => {
      onSaved(updated);
      setSaved(true);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Contact details</CardTitle>
        <CardDescription>
          Email address and status are managed by administrators.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            setSaved(false);
            mutation.mutate();
          }}
        >
          {mutation.isError ? (
            <div className="sm:col-span-2">
              <Alert variant="danger" title="Could not save">
                {messageOf(mutation.error, 'Please try again.')}
              </Alert>
            </div>
          ) : null}
          {saved ? (
            <div className="sm:col-span-2">
              <Alert variant="success">Profile updated.</Alert>
            </div>
          ) : null}

          <Field label="First name" htmlFor="first_name">
            <Input
              id="first_name"
              value={form.first_name}
              onChange={(event) => setForm({ ...form, first_name: event.target.value })}
            />
          </Field>
          <Field label="Last name" htmlFor="last_name">
            <Input
              id="last_name"
              value={form.last_name}
              onChange={(event) => setForm({ ...form, last_name: event.target.value })}
            />
          </Field>
          <Field label="Job title" htmlFor="job_title">
            <Input
              id="job_title"
              value={form.job_title}
              onChange={(event) => setForm({ ...form, job_title: event.target.value })}
            />
          </Field>
          <Field label="Phone" htmlFor="phone">
            <Input
              id="phone"
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
          </Field>
          <Field label="Time zone" htmlFor="timezone">
            <Input
              id="timezone"
              value={form.timezone}
              onChange={(event) => setForm({ ...form, timezone: event.target.value })}
            />
          </Field>
          <Field label="Email address" htmlFor="email" hint="Read-only">
            <Input id="email" value={user.email} readOnly disabled />
          </Field>

          <div className="sm:col-span-2">
            <Button type="submit" loading={mutation.isPending} icon={<BadgeCheck className="size-4" />}>
              Save changes
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => authApi.changePassword(current, next),
    onSuccess: () => {
      setCurrent('');
      setNext('');
      setConfirmation('');
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>
          Changing your password signs out every other device.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            setLocalError(null);
            if (next !== confirmation) {
              setLocalError('The two passwords do not match.');
              return;
            }
            mutation.mutate();
          }}
        >
          {mutation.isError ? (
            <div className="sm:col-span-2">
              <Alert variant="danger" title="Password not changed">
                {messageOf(mutation.error, 'Check your current password and the policy.')}
              </Alert>
            </div>
          ) : null}
          {mutation.isSuccess ? (
            <div className="sm:col-span-2">
              <Alert variant="success">Password updated. Other sessions were signed out.</Alert>
            </div>
          ) : null}
          {localError ? (
            <div className="sm:col-span-2">
              <Alert variant="danger">{localError}</Alert>
            </div>
          ) : null}

          <div className="sm:col-span-2">
            <Field label="Current password" htmlFor="current_password">
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(event) => setCurrent(event.target.value)}
              />
            </Field>
          </div>
          <Field label="New password" htmlFor="new_password" hint="Minimum 12 characters">
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
            />
          </Field>
          <Field label="Confirm new password" htmlFor="confirm_password">
            <Input
              id="confirm_password"
              type="password"
              autoComplete="new-password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </Field>

          <div className="sm:col-span-2">
            <Button type="submit" loading={mutation.isPending} icon={<Lock className="size-4" />}>
              Update password
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function MfaCard({ user, onChanged }: { user: SessionUser; onChanged: (user: SessionUser) => void }) {
  const [secret, setSecret] = useState<string | null>(null);
  const [uri, setUri] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);

  const enrol = useMutation({
    mutationFn: () => authApi.mfaEnrol(),
    onSuccess: (data) => {
      setSecret(data.secret);
      setUri(data.otpauth_uri);
    },
  });

  const confirm = useMutation({
    mutationFn: () => authApi.mfaConfirm(code),
    onSuccess: (data) => {
      setRecoveryCodes(data.recovery_codes);
      setSecret(null);
      setUri(null);
      setCode('');
      onChanged({ ...user, has_mfa_enabled: true });
    },
  });

  const disable = useMutation({
    mutationFn: () => authApi.mfaDisable(password),
    onSuccess: () => {
      setPassword('');
      setRecoveryCodes([]);
      onChanged({ ...user, has_mfa_enabled: false });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Smartphone className="size-4" aria-hidden="true" />
          Two-factor authentication
        </CardTitle>
        <CardDescription>
          Time-based one-time passwords (TOTP) with single-use recovery codes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={user.has_mfa_enabled ? 'success' : 'warning'}>
            {user.has_mfa_enabled ? 'enabled' : 'not enabled'}
          </Badge>
          {user.mfa_required ? <Badge variant="info">required by policy</Badge> : null}
        </div>

        {enrol.isError || confirm.isError || disable.isError ? (
          <Alert variant="danger" title="Something went wrong">
            {messageOf(enrol.error ?? confirm.error ?? disable.error, 'Please try again.')}
          </Alert>
        ) : null}

        {recoveryCodes.length > 0 ? (
          <Alert variant="warning" title="Store your recovery codes now">
            <ul className="mt-2 grid grid-cols-2 gap-1 font-mono text-xs">
              {recoveryCodes.map((recoveryCode) => (
                <li key={recoveryCode}>{recoveryCode}</li>
              ))}
            </ul>
          </Alert>
        ) : null}

        {!user.has_mfa_enabled && !secret ? (
          <Button onClick={() => enrol.mutate()} loading={enrol.isPending} icon={<ShieldCheck className="size-4" />}>
            Enable two-factor authentication
          </Button>
        ) : null}

        {secret ? (
          <div className="space-y-3">
            <Alert variant="info" title="Add this secret to your authenticator app">
              <p className="font-mono break-all">{secret}</p>
              {uri ? <p className="text-muted-foreground mt-1 break-all text-[11px]">{uri}</p> : null}
            </Alert>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                confirm.mutate();
              }}
            >
              <Field label="Code from the app" htmlFor="mfa-confirm-code">
                <Input
                  id="mfa-confirm-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                />
              </Field>
              <Button type="submit" loading={confirm.isPending}>
                Confirm enrolment
              </Button>
            </form>
          </div>
        ) : null}

        {user.has_mfa_enabled ? (
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              disable.mutate();
            }}
          >
            <Field label="Confirm your password to disable" htmlFor="mfa-disable-password">
              <Input
                id="mfa-disable-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
            <Button type="submit" variant="outline" loading={disable.isPending} icon={<KeyRound className="size-4" />}>
              Disable
            </Button>
          </form>
        ) : null}
      </CardContent>
    </Card>
  );
}
