# Warehouse & Inventory Management System (WIMS)

A production-ready, multi-warehouse inventory management platform: procurement and
receiving, putaway and slotting, real-time inventory, transfers, order fulfilment,
replenishment, cycle counting, returns, barcode/RFID capture, reporting and
governance — built as a modular monolith with a React/TypeScript client and a
Django/DRF API.

> **Status — Part 1 (Foundation) and Part 2 (Identity & organizations) complete.**
> The platform architecture, API surface, design system, infrastructure and
> operational tooling are in place, together with the identity and authorization
> foundation: email/password authentication, sessions, MFA (TOTP), password
> reset, email verification, login-attempt auditing and an organization/warehouse
> scoped RBAC engine — see **[docs/rbac.md](docs/rbac.md)**.
> Business modules (inventory, orders, procurement, …) remain **scaffolded
> only**; they are implemented in later parts of the build plan.

---

## Table of contents

- [Stack](#stack)
- [Architecture at a glance](#architecture-at-a-glance)
- [Repository layout](#repository-layout)
- [Quick start (Docker)](#quick-start-docker)
- [Local development (no Docker)](#local-development-no-docker)
- [Environment variables](#environment-variables)
- [API](#api)
- [Domain modules](#domain-modules)
- [Security model](#security-model)
- [Health checks & observability](#health-checks--observability)
- [Testing & quality gates](#testing--quality-gates)
- [Common tasks](#common-tasks)
- [Roadmap](#roadmap)
- [Further documentation](#further-documentation)

---

## Stack

| Layer            | Technology                                                              |
| ---------------- | ----------------------------------------------------------------------- |
| Frontend         | React 19 · TypeScript 7 · Vite 8 · Tailwind CSS v4 · React Router 7 · TanStack Query |
| Backend          | Python 3.12 · Django 5.2 · Django REST Framework 3.16 · drf-spectacular |
| Database         | PostgreSQL 16                                                           |
| Async / cache    | Redis 7 · Celery 5 (worker + beat)                                      |
| Infrastructure   | Docker · Docker Compose · nginx (edge proxy + SPA server)               |
| Quality          | Ruff · Vitest + Testing Library · Django test runner · TypeScript strict |

---

## Architecture at a glance

```
                    ┌──────────────────────────────┐
  Browser  ───────► │  nginx (edge, TLS termination)│
                    └───────┬──────────────┬────────┘
                            │              │
                   /api/ /admin/ /static/ │  /
                            │              │
                    ┌───────▼──────┐  ┌────▼─────────────┐
                    │ api (Django  │  │ frontend (nginx  │
                    │  + gunicorn) │  │  serving the SPA)│
                    └───┬──────┬───┘  └──────────────────┘
                        │      │
        ┌───────────────▼──┐ ┌─▼────────┐
        │ db (PostgreSQL)  │ │ redis    │◄──── worker / beat (Celery)
        │ internal net only│ │ internal │
        └──────────────────┘ └──────────┘
```

* **Modular monolith** – 25 domain modules under `backend/apps/`, each with its
  own models / serializers / views / services / tasks / routes, all mounted
  automatically at `/api/v1/<module>/`.
* **Versioned API surface** – `/api/v1/` is the only public API root; versioning
  is enforced through URL namespaces (DRF `NamespaceVersioning`).
* **Single source of truth for modules** – `backend/config/settings/base.py`
  (`DOMAIN_MODULES`) drives the backend routes, while
  `frontend/src/config/modules.ts` drives navigation **and** frontend routes.
* **Same-origin everywhere** – the browser only ever talks to `/api/v1/…`;
  Vite proxies in development, nginx proxies in production (no CORS sprawl).

Full details, including module boundaries, request lifecycle and deployment
topologies: **[docs/architecture.md](docs/architecture.md)**.

---

## Repository layout

```
.
├── backend/                    # Django project (Python 3.12)
│   ├── apps/
│   │   ├── core/               # health checks, middleware, logging, errors
│   │   ├── identity/           # ┐
│   │   ├── organizations/      # │
│   │   ├── warehouses/         # │  25 domain modules — scaffolded in Part 1,
│   │   ├── …                   # │  implemented in later parts
│   │   └── configuration/      # ┘
│   ├── config/
│   │   ├── settings/           # base / development / production / test
│   │   ├── api_urls.py         # /api/v1/ routing for every module
│   │   ├── celery.py           # Celery app (worker + beat)
│   │   ├── env.py              # environment-variable access helpers
│   │   └── urls.py             # root URLs, OpenAPI docs, error handlers
│   ├── Dockerfile · entrypoint.sh · requirements*.txt · pyproject.toml
├── frontend/                   # React + TypeScript SPA (Vite)
│   ├── src/
│   │   ├── app/                # router, providers, route fallbacks
│   │   ├── components/
│   │   │   ├── layout/         # app shell, sidebar, topbar, health badge
│   │   │   └── ui/             # design system primitives
│   │   ├── config/             # env access + module registry
│   │   ├── features/           # dashboard, health, (per-module feature code)
│   │   ├── lib/api/            # typed API client, error model
│   │   └── pages/              # module / system / error pages
│   ├── Dockerfile · nginx.conf · vite.config.ts · .env.example
├── nginx/                      # edge reverse proxy + security headers
├── scripts/dev_services.py     # embedded PostgreSQL + Redis (no Docker)
├── docs/architecture.md        # architecture, decisions, deployment
├── docker-compose.yml          # production-like stack
├── docker-compose.dev.yml      # developer override (runserver + Vite HMR)
├── .env.example                # every environment variable, documented
└── Makefile                    # `make help` lists all shortcuts
```

---

## Quick start (Docker)

Requires Docker Engine 24+ with Compose v2.

```bash
git clone <repository-url> wims && cd wims

# 1. Configuration (secrets live only in .env — never committed)
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"   # → DJANGO_SECRET_KEY
openssl rand -base64 32                                        # → POSTGRES_PASSWORD
openssl rand -base64 32                                        # → REDIS_PASSWORD

# 2. Start the stack (api, worker, beat, db, redis, frontend, nginx)
docker compose up -d --build

# 3. Create an admin user (optional at this stage)
docker compose exec api python manage.py createsuperuser
```

| Service          | URL                                                   |
| ---------------- | ----------------------------------------------------- |
| Web application  | <http://localhost/>                                   |
| API index        | <http://localhost/api/v1/>                            |
| Health (deep)    | <http://localhost/api/v1/health/>                     |
| Swagger UI       | <http://localhost/api/v1/docs/> (`ENABLE_API_DOCS=true`) |
| ReDoc            | <http://localhost/api/v1/redoc/>                       |
| Django admin     | <http://localhost/admin/>                             |

PostgreSQL and Redis are **not** published to the host — they are reachable only
inside the internal Docker network. To inspect the database, use
`make shell-db` (runs `psql` inside the container).

### Developer workflow with Docker

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
# Django runserver:  http://localhost:8000
# Vite dev server:   http://localhost:5173  (HMR, proxies /api to the API)
```

---

## Local development (no Docker)

**Backend**

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

cp .env.example backend/.env      # local values; backend/.env is gitignored

cd backend
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

**Frontend**

```bash
cd frontend
cp .env.example .env.local        # optional overrides
npm install
npm run dev                       # http://localhost:5173, proxies /api → :8000
```

**PostgreSQL + Redis without Docker**

`pgserver` and `redislite` (development dependencies) provide embedded servers:

```bash
make dev-services                 # prints the connection URLs, keeps running
# or: .venv/bin/python scripts/dev_services.py
```

**One-shot bootstrap (services + data + embedded-preview settings)**

```bash
.venv/bin/python scripts/dev_sandbox.py            # keeps PostgreSQL/Redis running
# then, in two more terminals:
#   cd backend  && python manage.py runserver 0.0.0.0:8000
#   cd frontend && npx vite --host 0.0.0.0
```

It writes `backend/.env`, migrates, syncs the RBAC registry and seeds a demo
organization with role-scoped users, so a fresh database is immediately usable:

| Account                 | Role                  | Scope                       | Password                    |
| ----------------------- | --------------------- | --------------------------- | --------------------------- |
| `dev-admin@wims.local`  | Platform administrator | platform                    | `Dev-Only-Passw0rd-2026!`   |
| `manager@wims.local`    | Warehouse Manager     | ACME (all warehouses)       | `Wims-Demo-Password-2026!`  |
| `controller@wims.local` | Inventory Controller  | Bhopal Main Warehouse       | `Wims-Demo-Password-2026!`  |
| `operator@wims.local`   | Warehouse Operator    | Bhopal Main Warehouse       | `Wims-Demo-Password-2026!`  |
| `viewer@wims.local`     | Management Viewer     | ACME (all warehouses)       | `Wims-Demo-Password-2026!`  |

> Development credentials only — they exist in a local database, never in a
> deployment. `manage.py seed_demo_data` re-creates them idempotently and
> refuses to run with production settings.

### When the browser preview cannot sign in

Sign-in needs the browser to keep a session credential. Two situations break it,
both handled by the bootstrap above:

* **Cookies are dropped** (the client is embedded on another registrable domain,
  where `SameSite=Lax` cookies are never sent on API calls) — `dev_sandbox.py`
  writes `DJANGO_COOKIE_SAMESITE=None`, `DJANGO_COOKIE_SECURE=true` and
  `AUTH_ENABLE_TOKEN_FALLBACK=true`, so the client can fall back to an
  `Authorization: Bearer` session token.
* **Third-party cookies are blocked outright** (Safari, hardened Chrome) — the
  bearer fallback is what keeps the preview working; opening the preview in its
  own tab always restores plain cookie authentication.

Production keeps the stricter posture: `SameSite=Lax`, `Secure`, `__Host-`
cookie names and the bearer fallback disabled (see
[docs/rbac.md](docs/rbac.md#authentication-controls)).

---

## Environment variables

Every variable is documented in **[.env.example](.env.example)**; the table below
covers the essentials.

| Variable                           | Purpose                                                        |
| ---------------------------------- | -------------------------------------------------------------- |
| `DJANGO_SECRET_KEY`                | **Required.** Cryptographic signing key (never hard-coded).    |
| `DJANGO_DEBUG`                     | Must be `false` in production (production settings refuse `true`). |
| `DJANGO_ALLOWED_HOSTS`             | Comma-separated hostnames; wildcards are rejected.             |
| `CORS_ALLOWED_ORIGINS`             | Exact frontend origins allowed to call the API.                |
| `DJANGO_CSRF_TRUSTED_ORIGINS`      | Origins trusted for unsafe browser requests.                   |
| `POSTGRES_*`                       | Database connection (`db` inside compose).                     |
| `REDIS_URL`, `REDIS_PASSWORD`      | Cache + Celery broker, password protected.                     |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Celery transport (separate Redis DBs by default).    |
| `ENABLE_API_DOCS`                  | Serve Swagger/ReDoc (disabled by default in production).       |
| `DJANGO_COOKIE_SAMESITE`           | `Lax` (default; production pins it) or `None` for embedded clients. |
| `DJANGO_COOKIE_SECURE`             | Forces the `Secure` cookie flag; implied by `SameSite=None`.   |
| `AUTH_ENABLE_TOKEN_FALLBACK`       | Opt-in `Authorization: Bearer` session tokens (off by default). |
| `VITE_API_BASE_URL`                | Public API base path (`/api/v1`, relative).                    |

Frontend variables (`VITE_*`) are **public** – they are compiled into the
browser bundle. Never place secrets there.

---

## API

* Base path: **`/api/v1/`** (versioning by URL namespace; `DEFAULT_VERSION=v1`).
* Schema: `/api/v1/schema/` (OpenAPI 3.0), UI: `/api/v1/docs/`, `/api/v1/redoc/`.
* Index: `GET /api/v1/` lists the version and every mounted module.
* Pagination: DRF page-number pagination, 25 items per page.
* Errors: a single JSON envelope for every failure —

  ```json
  { "error": { "code": "not_found", "message": "Resource not found.", "detail": null } }
  ```

* Every response carries `X-Request-ID` (echoed from the request or generated),
  which is also written to the access log.

```bash
curl http://localhost/api/v1/health/
# {"status":"ok","environment":"production","version":"v1","checks":{...}}
```

---

## Domain modules

All 25 modules exist as Django apps with `models / serializers / views / services
/ tasks / urls / admin / tests` scaffolds and a DRF router, are mounted at
`/api/v1/<module>/`, and appear in the frontend navigation with a landing page.
Business logic lands in the module that owns it — see
[docs/architecture.md](docs/architecture.md#module-boundaries).

| Group                     | Modules                                                                 |
| ------------------------- | ----------------------------------------------------------------------- |
| Network                   | `organizations`, `warehouses`                                            |
| Inbound & Procurement     | `suppliers`, `procurement`, `receiving`, `putaway`                       |
| Inventory Operations      | `locations`, `inventory`, `transfers`, `replenishment`, `stock_counts`   |
| Outbound & Orders         | `orders`, `fulfillment`, `returns`                                       |
| Catalog & Coding          | `products`, `pricing`, `barcode`, `rfid`                                 |
| Platform & Governance     | `identity`, `reports`, `notifications`, `integrations`, `audit`, `security`, `configuration` |

---

## Security model

| Requirement                        | Implementation                                                                 |
| ---------------------------------- | ------------------------------------------------------------------------------ |
| No hard-coded secrets              | Everything read from environment variables (`config/env.py`); `.env` gitignored; production settings fail fast when a secret is missing. |
| `DEBUG=false` in production        | `config/settings/production.py` raises `ImproperlyConfigured` if `DJANGO_DEBUG` is true. |
| Database not publicly exposed      | `db` has no host port, attached to an `internal: true` Docker network.         |
| Redis not publicly exposed         | `redis` has no host port, internal network, `requirepass` authentication.      |
| Secure CORS                        | Exact origin allow-list; wildcards are rejected in production.                 |
| Security headers                   | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, COOP/CORP, and a strict CSP at the edge; Django sets nosniff/XSS/clickjacking protection too. |
| Secure cookies                     | `HttpOnly`, `SameSite=Lax`, `Secure`, `__Host-` prefixed names in production; HSTS enabled at the edge. |
| No sensitive data in logs          | `SensitiveDataFilter` redacts passwords/tokens/authorization headers; access logs omit query strings on credential endpoints; error responses hide internals. |
| Least privilege / non-root         | Backend containers run as an unprivileged `app` user; only the edge proxy publishes ports; API endpoints are rate limited. |
| Auditable identity                 | Every request carries an `X-Request-ID` logged with the access line.            |

Details and threat notes: [docs/architecture.md](docs/architecture.md#security-architecture).

---

## Health checks & observability

| Endpoint                        | Purpose                                            | Success |
| ------------------------------- | -------------------------------------------------- | ------- |
| `/api/v1/health/live/`          | Liveness — process is up (no dependencies).         | 200     |
| `/api/v1/health/ready/`         | Readiness — database reachable.                     | 200/503 |
| `/api/v1/health/`               | Deep check — PostgreSQL + Redis with latency.       | 200/503 |
| `/nginx-healthz`                | Edge proxy liveness (nginx only).                   | 200     |

The UI surfaces the same data: the sidebar badge polls the deep health endpoint,
and `/system/health` renders a read-only operations console with per-dependency
status, latency and probe paths.

* Logging: JSON-ish console logging with level, timestamp, logger, request id and
  redacted message; optional rotating file handler via `LOG_DIR`.
* Docker health checks are declared for `db`, `redis`, `api`, `frontend` and
  `nginx`, and `depends_on: service_healthy` gates startup order.

---

## Testing & quality gates

```bash
make test          # backend (Django test runner) + frontend (Vitest)
make lint          # Ruff (lint + format check) + TypeScript typecheck
make check         # lint + tests
```

* Backend: `backend/apps/**/tests*` — health endpoints, JSON error envelope,
  request-id propagation, OpenAPI schema availability.
* Frontend: Vitest + Testing Library — shell rendering, registry-driven routing,
  module landing pages, 404 handling, live API health indicator (network mocked).

---

## Common tasks

```bash
make help                  # list every shortcut
make up / down / logs      # stack lifecycle
make migrate               # apply migrations in the api container
make test / lint / fmt     # quality gates
make dev-services          # embedded PostgreSQL + Redis (no Docker)
make clean                 # remove build artefacts
```

Backend-only commands:

```bash
cd backend
python manage.py spectacular --file openapi.yaml   # export the schema
python manage.py check --deploy                    # production hardening check
celery -A config worker -l info                    # run a worker locally
celery -A config beat -l info                      # run the scheduler
```

---

## Roadmap

Part 1 delivers the foundation. The module build order from here:

1. ~~**Part 2 — Identity & organizations:** users, RBAC, SSO-ready auth, tenants,
   warehouses and locations (master data).~~ **Delivered** — 56 permissions,
   10 system roles, scoped enforcement on every endpoint, and automated
   authorization suites (`docs/rbac.md`).
2. **Part 3 — Catalog & inventory ledger:** products, pricing, inventory balances,
   movements, reservations.
3. **Part 4 — Inbound:** suppliers, procurement, receiving, putaway.
4. **Part 5 — Outbound:** orders, allocation, picking/packing, fulfilment, returns.
5. **Part 6 — Optimization & insight:** replenishment, stock counts, barcode/RFID,
   reports, notifications, integrations, audit and configuration.

---

## Further documentation

* **[docs/rbac.md](docs/rbac.md)** — the permission catalog, role matrix,
  authorization semantics, grant lifecycle and authentication controls.
* **[docs/architecture.md](docs/architecture.md)** — system architecture, module
  boundaries, request lifecycle, data flow, security architecture, deployment
  topologies, ADR-style decision log and the part-by-part roadmap.
* **[backend/.env.example](.env.example)** — every environment variable.
* **[frontend/.env.example](frontend/.env.example)** — client-side configuration.

---

## License

Proprietary — all rights reserved unless stated otherwise in the repository.
