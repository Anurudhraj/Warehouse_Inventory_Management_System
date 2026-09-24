# Architecture — Warehouse & Inventory Management System

> **Scope of this document.** It describes the Part 1 foundation: how the pieces
> fit together, why the boundaries are drawn where they are, and the rules every
> later module must follow. Business modules are scaffolded only — their internal
> design is documented when they are implemented.
>
> **Part 2 (identity, organizations and RBAC) is documented separately in
> [rbac.md](rbac.md)**: permission catalog, role matrix, the authorization
> engine's decision rules, the grant lifecycle and the authentication
> controls.

---

## 1. Goals & constraints

| Goal | How the foundation addresses it |
| ---- | ------------------------------- |
| Operate multiple warehouses and tenants | Organization/warehouse scoping is a first-class concept: dedicated modules, module-per-domain boundaries, and an API surface that already reserves the paths. |
| Handle high-volume transactional flows | PostgreSQL as the system of record, Redis for cache + broker, Celery for anything slow (imports, exports, integrations, label generation). |
| Stay maintainable as modules land | Modular monolith: one Django app per domain, service layer for business logic, thin views. |
| Ship safely | Production settings fail fast on missing secrets, Docker defaults to non-root containers, edge proxy owns TLS/headers, and only the proxy publishes ports. |
| Be operable | Health/readiness endpoints, structured logs with request ids, Docker health checks, and a UI operations console. |

Non-goals for Part 1: business logic, authentication flows, real data models,
reporting pipelines. The identity/authorization layer landed in Part 2
([rbac.md](rbac.md)); remaining business modules are sequenced in the
[roadmap](#13-roadmap).

---

## 2. System context

```
                        ┌───────────────────────────────────────────┐
   Warehouse operators  │  React SPA (Vite build, served by nginx)  │
   Administrators   ────┤  – dashboard, module screens, health      │
   Integrators          └───────────────┬───────────────────────────┘
                                        │ /api/v1/… (same origin)
                        ┌───────────────▼───────────────────────────┐
                        │  Edge nginx — TLS, headers, rate limiting  │
                        └───────┬───────────────────────┬───────────┘
                                │                       │
                    ┌───────────▼─────────┐   ┌─────────▼──────────┐
                    │ Django + DRF        │   │ Static SPA assets  │
                    │ (gunicorn workers)  │   │ (frontend image)   │
                    └──┬───────────────┬──┘   └────────────────────┘
                       │               │
            ┌──────────▼──────┐   ┌────▼───────────────┐
            │ PostgreSQL      │   │ Redis              │
            │ system of record│   │ cache · broker     │
            └─────────────────┘   └────▲───────────────┘
                                       │
                              ┌────────┴─────────┐
                              │ Celery worker    │
                              │ Celery beat      │
                              └──────────────────┘
```

Deployment reality: `db`, `redis`, `api`, `worker` and `beat` live on an
`internal: true` Docker network with no route to or from the host. Only the edge
`nginx` container publishes ports.

---

## 3. Backend architecture

### 3.1 Layering

```
HTTP request
   │
   ▼
MIDDLEWARE      security → request context (id) → CORS → session → CSRF → auth → access log
   │
   ▼
URL ROUTING     config/urls.py → config/api_urls.py → apps/<module>/urls.py  (DRF router)
   │
   ▼
VIEWS           thin: validate input, call a service, serialise the result
   │
   ▼
SERVICES        business rules, transactions, cross-module orchestration      (apps/<module>/services.py)
   │
   ├──► MODELS / ORM (PostgreSQL)
   └──► TASKS (Celery) → Redis broker → worker
```

Rules that keep this honest:

1. **Views never contain business logic.** They translate between HTTP and the
   service layer; anything reusable (also used by tasks, management commands or
   other modules) lives in `services.py`.
2. **Cross-module writes go through the owning module's service**, never by
   importing another module's models into a view.
3. **Serializers validate shape, services enforce invariants.**
4. **Tasks are thin wrappers** around services so that retries and manual runs
   behave identically.

### 3.2 Configuration & settings

| Module | Purpose |
| ------ | ------- |
| `config/settings/base.py` | Shared configuration; the `DOMAIN_MODULES` list is the single source of truth for installed apps and API mounts. |
| `config/settings/development.py` | `DEBUG=true`, permissive hosts, development secret warning, verbose logging. |
| `config/settings/production.py` | Fails fast when a secret is missing, forces `DEBUG=false`, enables HSTS/secure cookies, requires explicit CORS/CSRF origins, disables API docs by default. |
| `config/settings/test.py` | Fast hashing, quiet logging, deterministic. |
| `config/env.py` | Typed environment access (`env_str`, `env_bool`, `env_int`, `env_list`, `env_choice`) plus optional `.env` loading for local runs. No secrets in code, ever. |

### 3.3 Module boundaries

All 25 modules are created in Part 1 with an identical skeleton
(`apps.py`, `models.py`, `serializers.py`, `views.py`, `services.py`, `tasks.py`,
`urls.py`, `admin.py`, `tests.py`, `migrations/`). Intended ownership:

| Module | Responsibility | Depends on (writes) |
| ------ | -------------- | ------------------- |
| `identity` | Users, credentials, sessions, MFA/SSO | — |
| `organizations` | Tenants, legal entities, business units | `identity` |
| `warehouses` | Facilities, calendars, capacity policy | `organizations` |
| `locations` | Zone/aisle/rack/bin hierarchy, constraints | `warehouses` |
| `products` | SKU catalogue, variants, UoM, tracking flags | `organizations` |
| `pricing` | Price lists, effective-dated rules, cost basis | `products` |
| `suppliers` | Vendor master, lead times, scorecards | `organizations` |
| `procurement` | Requisitions, purchase orders, approvals | `suppliers`, `products` |
| `receiving` | ASNs, dock appointments, receipt capture | `procurement` |
| `putaway` | Directed placement strategy | `receiving`, `locations`, `inventory` |
| `inventory` | Stock ledger, balances, reservations, ATP | `products`, `locations` |
| `transfers` | Inter/intra-warehouse movement | `inventory` |
| `orders` | Outbound orders, allocation, priority | `inventory`, `products` |
| `fulfillment` | Pick/pack/ship, carrier labels | `orders`, `inventory` |
| `replenishment` | Min/max & demand-driven replenishment | `inventory`, `locations` |
| `stock_counts` | Cycle counts, variance, adjustments | `inventory`, `locations` |
| `returns` | RMAs, inspection, disposition | `orders`, `inventory` |
| `barcode` | Symbologies, label templates, scan parsing | `products`, `locations` |
| `rfid` | EPC encoding, reader events | `products`, `inventory` |
| `reports` | Operational/analytical reports, exports | read-mostly |
| `notifications` | Channels, subscriptions, escalations | all (consumer) |
| `integrations` | ERP/carrier/marketplace connectors, webhooks | all (adapter) |
| `audit` | Immutable change history | all (consumer) |
| `security` | RBAC, API keys, session policy | `identity` |
| `configuration` | Settings registry, feature flags, reference data | — |

Dependency direction is acyclic: `configuration`/`identity` at the bottom,
execution modules in the middle, `audit`/`notifications`/`integrations` at the
top as consumers.

### 3.4 API structure & versioning

* All routes are mounted under **`/api/v1/`** by `config/api_urls.py`, which
  iterates `settings.DOMAIN_MODULES` and includes `apps.<module>.urls`
  (each exposes a DRF router).
* Versioning uses DRF's **`NamespaceVersioning`** (`DEFAULT_VERSION = "v1"`,
  `ALLOWED_VERSIONS = ("v1",)`), so `request.version` is populated from the URL
  namespace and a future `/api/v2/` can coexist without touching view code.
* `GET /api/v1/` returns an API index (version + module endpoints) that is
  generated from settings, not hand-maintained.
* OpenAPI 3 schema and UIs come from **drf-spectacular**:
  `/api/v1/schema/`, `/api/v1/docs/` (Swagger UI), `/api/v1/redoc/`
  (assets bundled by `drf-spectacular-sidecar` — no CDN dependency).
  Docs are disabled in production unless `ENABLE_API_DOCS=true`.

### 3.5 Errors & logging

* `apps/core/exceptions.py` installs a single DRF exception handler. Every error
  — validation, auth, not found, unexpected — is rendered as:

  ```json
  { "error": { "code": "validation_error", "message": "…", "detail": { … } } }
  ```

  Unexpected exceptions are logged with a stack trace (server side only) and
  returned as a generic 500 with the request id.
* Non-DRF paths (`/api/…` 404s, 500s) are handled by `apps/core/views_error.py`,
  which returns JSON for API callers and HTML for everything else.
* **Request ids**: `RequestContextMiddleware` accepts or generates
  `X-Request-ID`, stores it in a context variable, echoes it on the response and
  makes it available to every log line via `RequestContextFilter`.
* **Redaction**: `SensitiveDataFilter` scrubs `password`/`token`/`authorization`
  style values from log messages; `AccessLogMiddleware` drops query strings on
  credential-carrying paths so credentials never reach log storage.
* Log destinations: console (default, container-friendly) and an optional
  rotating file handler when `LOG_DIR` is set.

### 3.6 Async work

`config/celery.py` binds Celery to Django settings (`CELERY_*`) and
auto-discovers `apps/<module>/tasks.py`. Separate Redis databases isolate the
cache, the broker and results. Containers: `worker` (execution) and `beat`
(scheduling, file-based schedule on a container path). Long-running or
externally-triggered work (imports, exports, label generation, ERP sync) belongs
here, never in a request cycle.

---

## 4. Frontend architecture

### 4.1 Structure

```
src/
├── app/          router (registry-driven), providers (TanStack Query), fallbacks
├── components/
│   ├── layout/   app shell, sidebar, topbar, health indicator
│   └── ui/       design system primitives (button, card, table, badge, …)
├── config/       env access + MODULES registry (nav + routes + API paths)
├── features/     feature-first code (dashboard, health, … future modules)
├── hooks/        cross-cutting hooks (theme, …)
├── lib/
│   ├── api/      typed fetch client, error model, shared API types
│   └── utils/    cn(), formatting helpers
└── pages/        module landing pages, system pages, error pages
```

### 4.2 Routing

Routes are **generated from the module registry**
(`src/config/modules.ts`): each entry contributes a sidebar link and a lazy
route. Adding a module is a one-line change in that file — no router edits.
Pages are code-split with `React.lazy` + `Suspense`, so the initial bundle stays
small (vendor chunks are split by `manualChunks`). A catch-all renders the 404
page, and the router's `errorElement` renders the error page for render failures.

### 4.3 Data layer

* `src/lib/api/client.ts` — a thin, typed `fetch` wrapper: base URL from
  `VITE_API_BASE_URL`, query serialisation, JSON bodies, CSRF header for unsafe
  methods (Django session auth), request timeout via `AbortController`,
  `credentials: 'include'`, and normalisation of every failure into `ApiError`
  (status, code, message, request id).
* TanStack Query owns server state: caching, retries (never for 4xx), background
  refetch policy. The health indicator polls `/health/` and degrades gracefully
  when the API is unreachable.
* The API base URL is **relative** (`/api/v1`) so the browser stays same-origin
  in every environment: Vite proxies in development, nginx in production.

### 4.4 Design system

`src/index.css` declares the tokens once (Tailwind v4 `@theme` + CSS variables)
and exposes semantic utilities (`bg-card`, `text-muted-foreground`, `border-border`,
`bg-primary`, `text-success-foreground`, …). Light and dark themes swap the same
variables under `.dark`; the theme is applied before first paint to avoid flashes
and persisted in `localStorage`.

Primitives in `src/components/ui/` — `Button`, `Card`, `Badge`, `Input`/`Select`/
`Field`, `Table`, `Alert`, `Progress`, `StatCard`, `PageHeader`, `EmptyState`,
`Spinner`/`Skeleton`, `Tooltip` — are the only building blocks module screens
should use. Accessibility basics are built in: focus-visible rings, ARIA roles on
interactive/feedback components, skip-to-content link, keyboard-dismissible
drawer, `prefers-reduced-motion` support.

---

## 5. Request lifecycle

1. **Edge (nginx)** — TLS termination, security headers, CSP, rate limits
   (30 r/s general API, 5 r/s on `/api/v1/identity/`), compression, static asset
   caching, SPA fallback. `/api/*` and `/admin/*` are proxied to gunicorn;
   `/static/*` is served from the shared volume.
2. **Django middleware** — `SecurityMiddleware` → `RequestContextMiddleware`
   (request id) → CORS → session → CSRF → auth → `AccessLogMiddleware`.
3. **Routing** — `config/urls.py` → `/api/v1/` include → module router.
4. **View** — DRF content negotiation, authentication, permissions, throttling,
   validation; delegates to the module's service layer.
5. **Service** — business rules inside a transaction; may enqueue Celery tasks.
6. **Response** — DRF renderer (JSON only), optional pagination envelope, error
   handler on failure; the request id is echoed back.

---

## 6. Data architecture

* **PostgreSQL is the system of record.** Every module owns its tables; cross-module
  reads happen through service interfaces (later parts), never by joining across
  module boundaries in a view.
* **Immutability where it matters**: the stock ledger (Part 3) is append-only;
  balances are derived/projected, and `audit` records who changed what and when.
* **Multi-tenancy**: organization scoping is applied at the model layer (Part 2)
  and enforced in services; the API surface already isolates module paths.
* **Migrations** run automatically on API container start (`entrypoint.sh`),
  which keeps deployments deterministic for this stage; production pipelines can
  switch to an explicit migration job.
* **Connection handling**: `CONN_MAX_AGE` keeps connections warm per gunicorn
  worker; `celery` workers use their own pools.
* **Backups**: `postgres_data` is a named volume; production deployments should
  add `pg_dump`/PITR tooling (documented as a follow-up, not implemented here).

---

## 7. Security architecture

| Control | Implementation |
| ------- | -------------- |
| Secret management | Environment variables only (`config/env.py`); `.env` gitignored; production settings raise `ImproperlyConfigured` when `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `DJANGO_ALLOWED_HOSTS`, `CORS_*` or `DJANGO_CSRF_TRUSTED_ORIGINS` are missing. |
| Debug safety | `production.py` hard-sets `DEBUG=false` and refuses to boot if the environment asks for debug. |
| Network isolation | `db` and `redis` are on an `internal: true` network with no published ports; only the edge proxy publishes 80/443. Redis additionally requires a password. |
| Transport | TLS terminated at nginx (certificates mounted read-only); HSTS enabled; `SECURE_PROXY_SSL_HEADER` so Django knows the original scheme. |
| Cookies | `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `HttpOnly`, `SameSite=Lax`, `__Host-` prefixes in production. |
| Headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, and a restrictive CSP. Django adds its own protections (`SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS`, password validators). |
| CORS/CSRF | Explicit origin allow-lists; no wildcard support in production; credentials allowed only for listed origins. |
| Least privilege | Backend containers run as the non-root `app` user; API docs disabled in production by default; only the services that need a capability get it. |
| Rate limiting | Edge-level limits on `/api/` and tighter limits on identity endpoints; 429 responses. |
| Log hygiene | Redaction filter + credential-path query stripping + generic 500 payloads (no stack traces to clients). |
| Auditing | Request ids on every response/log line; the `audit` module (later) records domain-level changes. |

Threat notes / accepted gaps for this stage: TLS certificates are operator-provided
(no ACME automation), no WAF, no secret manager integration (env vars suffice for
compose-based deployment), and `docker compose` secrets are not used — swap in
Docker secrets or a vault when the deployment target is known.

---

## 8. Infrastructure & deployment

### 8.1 Container topology (`docker-compose.yml`)

| Service | Image / build | Networks | Ports | Notes |
| ------- | ------------- | -------- | ----- | ----- |
| `nginx` | `nginx:1.27-alpine` | edge + backend | `80`, `443` published | Edge proxy, static `/static/`, SPA routing, health `nginx-healthz`. |
| `frontend` | `frontend/Dockerfile` (node build → nginx) | edge | `80` internal | Serves the compiled SPA with immutable asset caching. |
| `api` | `backend/Dockerfile` | backend + edge | `8000` internal | gunicorn; entrypoint waits for db/redis, runs migrations and `collectstatic`. |
| `worker` | `backend/Dockerfile` | backend | — | `celery worker`, concurrency from `CELERY_CONCURRENCY`. |
| `beat` | `backend/Dockerfile` | backend | — | `celery beat` scheduler. |
| `db` | `postgres:16-alpine` | backend (internal) | — | Named volume, `pg_isready` health check. |
| `redis` | `redis:7-alpine` | backend (internal) | — | `requirepass`, AOF persistence, `noeviction`. |

Every service declares a health check; `depends_on: service_healthy` gates
startup order (db/redis → api → worker/beat; api/frontend → nginx).

### 8.2 Environments

* **Development** — `config.settings.development`, Django runserver, Vite dev
  server with HMR and API proxying. `docker-compose.dev.yml` provides this inside
  containers; `scripts/dev_services.py` provides PostgreSQL + Redis without Docker.
* **Test/CI** — `config.settings.test`; backend via `manage.py test`, frontend via
  Vitest; Ruff + TypeScript keep the surface clean.
* **Production** — `config.settings.production`, gunicorn behind edge nginx,
  containers non-root, secrets injected at runtime.

### 8.3 Scaling notes (future)

* API: scale `api` replicas horizontally; the proxy load-balances via Docker DNS.
* Celery: scale `worker` replicas; add dedicated queues per workload class
  (imports, exports, integrations) when volumes justify it.
* Database: move to a managed PostgreSQL for PITR/HA; read replicas for reports.
* Redis: managed instance with TLS; separate logical DBs (already the pattern).
* Static assets: put a CDN in front of `/static/` and the SPA assets.

---

## 9. Observability

* **Health**: `/api/v1/health/` (deep), `/health/live/`, `/health/ready/`, plus
  `/nginx-healthz` at the edge. The UI exposes the same data at `/system/health`.
* **Logs**: one access line per request (`method path -> status (latency) rid=…`)
  plus application logs with the redaction filter. Containers log to stdout so
  the platform collector can ship them.
* **Request tracing**: `X-Request-ID` is accepted from the edge (`$request_id`),
  propagated through logs and echoed to clients — the correlation id to quote in
  incidents.
* **Metrics**: not instrumented yet; `/api/v1/health/` is scrape-friendly and a
  Prometheus exporter (`django-prometheus`) can be added without architectural
  change.

---

## 10. Testing strategy

| Layer | Tooling | What it covers now | What later parts add |
| ----- | ------- | ------------------ | -------------------- |
| Backend unit/integration | Django test runner (`manage.py test apps`) | Health endpoints, error envelope, request-id propagation, OpenAPI availability | Service-layer logic, model invariants, task behaviour |
| Frontend | Vitest + Testing Library (jsdom) | Shell render, registry-driven routes, module pages, 404, live health indicator | Feature flows, form validation, API mocking via MSW |
| Static analysis | Ruff (lint + format), TypeScript strict (`tsc -b`) | Style, imports, security lint rules, type correctness | — |
| Contract | drf-spectacular schema | Schema generation is part of the test suite | Schema-diff checks between API versions |

Test settings use fast password hashing and quiet logging so suites stay fast.

---

## 11. Decision log (ADR-style)

| # | Decision | Rationale | Alternatives rejected |
| - | -------- | --------- | --------------------- |
| 1 | **Modular monolith** with one Django app per domain | Transactional consistency for inventory operations, one deployable, clear module boundaries that could be extracted later | Microservices (operational overhead, distributed transactions for stock movements), single `core` app (poor boundaries) |
| 2 | **URL-namespace API versioning** (`/api/v1/…`) | Explicit, cache-friendly, trivially observable in logs and the edge proxy | Header/accept versioning (harder to debug), query parameter versioning (breaks caching) |
| 3 | **Settings package** with explicit environment modules | Fail-fast production hardening, test overrides, no `if DEBUG` scattered through config | Single settings file with conditionals |
| 4 | **Environment variables only** for configuration | 12-factor, container-friendly, keeps secrets out of the repo | Committed config files, Docker build args (leak into image layers) |
| 5 | **Redis for both cache and broker** (separate logical DBs) | One dependency to operate; Celery needs a broker anyway | RabbitMQ (extra ops), database-backed cache (slower, more load on the DB) |
| 6 | **Edge nginx as the only published service** | Single place for TLS, headers, rate limits; db/redis unreachable from outside | Publishing API/DB ports, Traefik/Caddy (fine, but nginx is the stated requirement) |
| 7 | **React Router with a module registry** | Navigation, routes and API path naming stay consistent by construction | Hand-written route list (drifts), file-system routing (extra abstraction) |
| 8 | **Tailwind v4 with semantic tokens** | One place to change the visual language; dark mode for free; no CSS-in-JS runtime | Component library (opinionated, heavy), plain CSS modules (inconsistent) |
| 9 | **TanStack Query for server state** | Caching, retries, polling and loading states out of the box | Hand-rolled hooks (duplicated logic), Redux (overkill for server state) |
| 10 | **API docs in the app** (drf-spectacular sidecar) | No CDN dependency, versioned with the code, disabled by default in production | External docs site (drifts) |
| 11 | **Celery worker + beat** managed from settings | Async work is inevitable (imports, exports, integrations, label generation) | Synchronous processing (timeouts), cron sidecars (no retry semantics) |
| 12 | **Same-origin API calls** from the SPA | No CORS in the happy path, cookies work naturally, CSP can stay strict | Cross-origin API calls (CORS churn, cookie complexity) |

---

## 12. Conventions

**Backend**

* One Django app per domain module; `services.py` holds business logic.
* snake_case modules, PascalCase classes; imports grouped stdlib → Django → third
  party → local (enforced by Ruff).
* Every module keeps `models / serializers / views / services / tasks / urls /
  admin / tests` present, even if some files are placeholders.
* API paths are plural nouns (`/api/v1/warehouses/`); actions are sub-resources.
* Never log secrets or customer data; use the service layer for anything reused.

**Frontend**

* Feature-first folders (`features/<domain>/…`), shared code in `components/`,
  `lib/`, `config/`.
* kebab-case file names, `PascalCase` components, `useX` hooks.
* Import via the `@/` alias; no deep relative chains.
* Use design-system primitives; no ad-hoc colors/spacing outside the tokens.
* All network access goes through `lib/api/client.ts` and TanStack Query.

**Git/CI (recommended, not yet wired)**

* Conventional Commits; PRs run `make lint` + `make test`;
  container images built on tags; migrations reviewed in PRs.

---

## 13. Roadmap

| Part | Scope | Exit criteria |
| ---- | ----- | ------------- |
| **1 (done)** | Foundation: Django project, DRF API surface, React SPA, design system, PostgreSQL, Redis, Celery, Docker, nginx, env config, health checks, logging, error handling, OpenAPI | `make check` green, stack starts, health endpoint reports all dependencies `ok` |
| 2 | Identity & organizations: user model, RBAC, sessions/SSO hooks; tenants, legal entities, warehouses, locations master data | Authenticated CRUD with scoping, audit hooks, tests |
| 3 | Catalog & inventory ledger: products, pricing, stock ledger, balances, reservations, ATP | Movements and balances consistent under concurrency; ledger append-only |
| 4 | Inbound: suppliers, procurement, receiving, putaway | PO → ASN → receipt → putaway flow with discrepancies |
| 5 | Outbound: orders, allocation, picking/packing, fulfilment, returns | Order → ship → delivery flow with carrier integration stub |
| 6 | Optimization & insight: replenishment, stock counts, barcode/RFID, reports, notifications, integrations, audit, configuration | End-to-end operational cycle, KPI reporting, connector framework |

---

## 14. Operational runbook (Part 1)

| Task | Command |
| ---- | ------- |
| Start stack | `docker compose up -d --build` |
| Check status | `docker compose ps` · `docker compose logs -f api worker` |
| Apply migrations | `docker compose exec api python manage.py migrate` |
| Open a Django shell | `docker compose exec api python manage.py shell` |
| Inspect the database | `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB` |
| Verify health | `curl -s localhost/api/v1/health/ \| jq` |
| Export OpenAPI schema | `docker compose exec api python manage.py spectacular --file openapi.yaml` |
| Production hardening check | `docker compose exec api python manage.py check --deploy` |
| Rotate a secret | Update `.env`, then `docker compose up -d` (services pick up new values) |
| Rebuild after dependency changes | `docker compose build --pull api frontend && docker compose up -d` |

Rollback: `docker compose down` followed by `git checkout <previous-tag>` and
`docker compose up -d --build`. Database rollbacks use Django migrations
(`python manage.py migrate <app> <migration>`); take a volume snapshot first.
