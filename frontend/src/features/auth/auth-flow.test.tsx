/**
 * Authentication flow tests: the sign-in screen, the MFA step, route guarding
 * and permission-gated navigation.
 *
 * The API is stubbed — these tests describe the *client* contract (what is
 * rendered, what is requested); backend enforcement is covered by the Django
 * authorization suites.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppProviders } from '@/app/providers';
import { routes } from '@/app/routes';

const baseUser = {
  id: 7,
  reference: 'USR-7',
  email: 'operator@acme.test',
  first_name: 'Olive',
  last_name: 'Operator',
  phone: '',
  job_title: 'Picker',
  timezone: 'UTC',
  locale: 'en',
  organization: { id: 1, code: 'ACME', name: 'Acme Distribution' },
  status: 'active',
  is_email_verified: true,
  mfa_required: false,
  has_mfa_enabled: false,
  must_change_password: false,
  last_login_at: null,
};

function sessionResponse(permissions: string[]) {
  return {
    authenticated: true,
    user: baseUser,
    permissions,
    organizations: [1],
    warehouses: [1],
    is_platform_admin: false,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}

let authenticated: boolean;
let permissions: string[];

beforeEach(() => {
  authenticated = false;
  permissions = ['warehouse.view'];
  localStorage.clear();

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url.includes('/identity/auth/session/')) {
        return authenticated
          ? jsonResponse(sessionResponse(permissions))
          : jsonResponse({ error: { code: 'not_authenticated', message: 'no session' } }, 401);
      }

      if (url.includes('/identity/auth/login/')) {
        const body = JSON.parse(String(init?.body ?? '{}'));
        if (body.password === 'correct-horse-battery') {
          authenticated = true;
          return jsonResponse({ mfa_required: false, user: baseUser, permissions });
        }
        return jsonResponse(
          { error: { code: 'authentication_failed', message: 'Invalid email or password.' } },
          401,
        );
      }

      if (url.includes('/identity/auth/logout/')) {
        authenticated = false;
        return new Response(null, { status: 204 });
      }

      if (url.includes('/identity/auth/password/reset/validate/')) {
        return jsonResponse({ valid: true, purpose: 'password_reset' });
      }

      if (url.includes('/health')) {
        return jsonResponse({
          status: 'ok',
          environment: 'test',
          version: 'v1',
          checks: {
            database: { status: 'ok', detail: '1ms' },
            redis: { status: 'ok', detail: '1ms' },
          },
        });
      }

      return jsonResponse({ count: 0, next: null, previous: null, results: [] });
    }),
  );
});

describe('authentication flow', () => {
  it('redirects anonymous visitors to the sign-in screen', async () => {
    renderAt('/');

    expect(await screen.findByRole('heading', { name: /sign in to wims/i })).toBeVisible();
    expect(screen.getByLabelText(/email address/i)).toBeVisible();
    expect(screen.getByLabelText(/password/i)).toBeVisible();
  });

  it('reports rejected credentials without leaking whether the account exists', async () => {
    const user = userEvent.setup();
    renderAt('/login');

    await user.type(await screen.findByLabelText(/email address/i), 'operator@acme.test');
    await user.type(screen.getByLabelText(/password/i), 'wrong-password');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText(/invalid email or password/i)).toBeVisible();
  });

  it('signs in and renders the application shell', async () => {
    const user = userEvent.setup();
    renderAt('/login');

    await user.type(await screen.findByLabelText(/email address/i), 'operator@acme.test');
    await user.type(screen.getByLabelText(/password/i), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('heading', { name: /warehouse control tower/i })).toBeVisible();
    expect(screen.getByLabelText('Primary navigation')).toBeInTheDocument();
  });

  it('offers a password reset link', async () => {
    const user = userEvent.setup();
    renderAt('/login');

    await user.click(await screen.findByRole('link', { name: /forgot your password/i }));

    expect(
      await screen.findByRole('heading', { name: /reset your wims password/i }),
    ).toBeVisible();
  });
});

describe('permission-gated navigation', () => {
  it('hides administration links from users without those permissions', async () => {
    authenticated = true;
    renderAt('/');

    await screen.findByRole('heading', { name: /warehouse control tower/i });

    expect(screen.getByRole('link', { name: /my profile/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /^users$/i })).toBeNull();
    expect(screen.queryByRole('link', { name: /^roles$/i })).toBeNull();
    expect(screen.queryByRole('link', { name: /^permissions$/i })).toBeNull();
  });

  it('shows administration links when the session holds the permissions', async () => {
    authenticated = true;
    permissions = ['warehouse.view', 'user.view', 'role.view', 'assignment.manage'];
    renderAt('/');

    await screen.findByRole('heading', { name: /warehouse control tower/i });

    expect(screen.getByRole('link', { name: /^users$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^roles$/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^permissions$/i })).toBeInTheDocument();
  });

  it('renders a clear refusal instead of a broken screen when the role is missing', async () => {
    authenticated = true;
    permissions = ['warehouse.view'];
    renderAt('/administration/users');

    expect(
      await screen.findByRole('heading', { name: /do not have access to this area/i }),
    ).toBeVisible();
    expect(screen.getByText(/user.view/i)).toBeVisible();
  });

  it('loads the users screen for an administrator', async () => {
    authenticated = true;
    permissions = ['user.view', 'user.manage', 'assignment.manage'];
    renderAt('/administration/users');

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: /users/i })).toBeVisible(),
    );
    expect(screen.getByLabelText(/^search$/i)).toBeVisible();
    expect(screen.getByRole('heading', { name: /invite a user/i })).toBeVisible();
  });
});
