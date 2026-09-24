/**
 * Application smoke tests: the shell, registry-driven routing, module landing
 * pages, the 404 route and the API health indicator.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { routes } from '@/app/routes';
import { AppProviders } from '@/app/providers';
import { MODULES } from '@/config/modules';

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>,
  );
}

const sessionPayload = {
  authenticated: true,
  user: {
    id: 1,
    reference: 'USR-TEST',
    email: 'admin@acme.test',
    first_name: 'Ada',
    last_name: 'Admin',
    phone: '',
    job_title: 'Warehouse Manager',
    timezone: 'UTC',
    locale: 'en',
    organization: { id: 1, code: 'ACME', name: 'Acme Distribution' },
    status: 'active',
    is_email_verified: true,
    mfa_required: false,
    has_mfa_enabled: false,
    must_change_password: false,
    last_login_at: null,
  },
  permissions: [
    'warehouse.view',
    'user.view',
    'user.manage',
    'role.view',
    'role.manage',
    'assignment.manage',
  ],
  organizations: [1],
  warehouses: [1],
  is_platform_admin: false,
};

const healthPayload = {
  status: 'ok',
  environment: 'test',
  version: 'v1',
  django_version: '5.2.17',
  checks: {
    database: { status: 'ok', detail: '1.2ms' },
    redis: { status: 'ok', detail: '0.8ms' },
  },
};

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/identity/auth/session/')) {
        return new Response(JSON.stringify(sessionPayload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/health')) {
        return new Response(JSON.stringify(healthPayload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({ error: { code: 'not_found', message: 'nope' } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
});

describe('app shell', () => {
  it('renders the dashboard with KPI cards and module navigation', async () => {
    renderAt('/');

    expect(await screen.findByRole('heading', { name: /warehouse control tower/i })).toBeVisible();
    expect(screen.getByText(/active skus/i)).toBeVisible();
    expect(screen.getByLabelText('Primary navigation')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^warehouses$/i })).toBeInTheDocument();
  });

  it('registers a sidebar link for every module in the registry', async () => {
    renderAt('/');
    await screen.findByRole('heading', { name: /warehouse control tower/i });

    const nav = screen.getByLabelText('Primary navigation');
    const hrefs = Array.from(nav.querySelectorAll('a')).map((a) => a.getAttribute('href'));

    for (const module of MODULES) {
      expect(hrefs).toContain(module.path);
    }
  });

  it('shows live API status from the health endpoint', async () => {
    renderAt('/');
    await waitFor(() => expect(screen.getAllByText(/all systems operational/i).length).toBeGreaterThan(0));
    expect(screen.getByText(/API operational/i)).toBeVisible();
  });
});

describe('module routes', () => {
  it('renders the module landing page generated from the registry', async () => {
    renderAt('/inventory');

    expect(await screen.findByRole('heading', { name: 'Inventory', level: 1 })).toBeVisible();
    expect(screen.getByText(/real-time stock ledger per location/i)).toBeVisible();
    expect(screen.getByText('/api/v1/inventory/')).toBeVisible();
  });
});

describe('error routes', () => {
  it('renders the 404 page for unknown paths', async () => {
    renderAt('/not-a-real-module');

    expect(await screen.findByText(/page not found/i)).toBeVisible();
    expect(screen.getAllByText(/not-a-real-module/i).length).toBeGreaterThan(0);
  });
});
