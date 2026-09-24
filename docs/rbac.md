# RBAC — roles, permissions and authorization

> **Scope.** This document describes Part 2: the identity and authorization
> foundation. It is the reference for *who may do what*, why the model is shaped
> this way, and how every later module (inventory, inbound, outbound, …) is
> expected to enforce it.

**The governing rule:**

> Authorization is enforced by the backend on every request. The frontend may
> hide a control, but hiding never protects anything — every endpoint resolves
> the caller's scoped permissions through the authorization engine and answers
> `401`, `403` or `404` accordingly.

---

## 1. Vocabulary

| Term | Meaning |
| ---- | ------- |
| **Organization** | The tenant root. Every user (except platform staff) belongs to exactly one, and every business record hangs off one. |
| **Branch** | A business location inside an organization (legal entity, plant, depot). |
| **Warehouse** | The operational unit inside a branch. The finest scope a grant can name. |
| **Permission** | A capability named `<module>.<action>` (e.g. `inventory.adjust`). Defined in code, never created by users. |
| **Role** | A named bundle of permissions with an **authority level** (0–100). System roles ship with the platform; organizations may add custom roles. |
| **Assignment** | The grant of a role to a user in a scope (`organization` only, or `organization` + `warehouse`), optionally time-boxed. |
| **Effective permission** | A permission the caller actually holds right now — the intersection of active assignments, active roles, unexpired windows and account state. |

---

## 2. Where the model lives

```
backend/apps/security/
├── permission_registry.py   # 56 permissions — the single source of truth
├── role_registry.py         # 10 system roles with levels
├── models.py                # Permission, Role, RoleAssignment
├── authorization.py         # AuthorizationService — the only authority check
├── permissions.py           # DRF permission classes & decorators
├── services.py              # RoleService / PermissionService (sync, grants)
└── management/commands/sync_rbac.py
```

The registries are **code**: `manage.py sync_rbac` (and the data migration
`security/0002_seed_rbac_registry`) project them into the database, and
`python manage.py sync_rbac --check` reports drift (used in CI). Adding a
capability means editing the registry — never the database.

---

## 3. Permission catalog (56)

| Module | Permissions |
| ------ | ----------- |
| `organization` | `organization.view`, `organization.manage` |
| `branch` | `branch.view`, `branch.manage` |
| `warehouse` | `warehouse.view`, `warehouse.manage` |
| `inventory` | `inventory.view`, `inventory.create`, `inventory.adjust`, `inventory.approve_adjustment` |
| `product` | `product.view`, `product.manage` |
| `pricing` | `pricing.view`, `pricing.manage` |
| `supplier` | `supplier.view`, `supplier.manage` |
| `purchase_order` | `purchase_order.view`, `purchase_order.create`, `purchase_order.approve` |
| `receiving` | `receiving.view`, `receiving.manage` |
| `putaway` | `putaway.view`, `putaway.manage` |
| `transfer` | `transfer.create`, `transfer.approve`, `transfer.dispatch`, `transfer.receive` |
| `order` | `order.view`, `order.create`, `order.manage` |
| `fulfillment` | `fulfillment.view`, `fulfillment.execute` |
| `replenishment` | `replenishment.view`, `replenishment.manage` |
| `stock_count` | `stock_count.view`, `stock_count.manage` |
| `return` | `return.view`, `return.manage` |
| `report` | `report.view`, `report.export` |
| `user` | `user.view`, `user.manage` |
| `role` | `role.view`, `role.manage` |
| `assignment` | `assignment.manage` |
| `session` | `session.view`, `session.revoke` |
| `audit` | `audit.view` |
| `configuration` | `configuration.view`, `configuration.manage` |
| `integration` | `integration.view`, `integration.manage` |
| `barcode` | `barcode.manage` |
| `rfid` | `rfid.manage` |
| `notification` | `notification.manage` |
| `supplier_portal` | `supplier_portal.use` |

Permissions marked **sensitive** in the registry (`organization.manage`,
`branch.manage`, `warehouse.manage`, `inventory.approve_adjustment`, approval
rights, …) are the ones a role editor warns about: they can change money, stock
or access boundaries.

---

## 4. System roles (10)

| Role | Code | Level | Permissions |
| ---- | ---- | ----- | ----------- |
| Super Admin | `super_admin` | 100 | 56 (platform-only) |
| Warehouse Manager | `warehouse_manager` | 80 | 33 |
| Finance / Accounts | `finance_accounts` | 75 | 14 |
| Inventory Controller | `inventory_controller` | 70 | 18 |
| Procurement Manager | `procurement_manager` | 70 | 17 |
| Dispatch Coordinator | `dispatch_coordinator` | 60 | 13 |
| Management Viewer | `management_viewer` | 55 | 18 |
| Sales / Order User | `sales_order_user` | 50 | 12 |
| Warehouse Operator | `warehouse_operator` | 40 | 17 |
| Supplier Portal User | `supplier_portal_user` | 20 | 4 |

<details>
<summary>Permission sets per role</summary>

**`super_admin`** (platform staff; not assignable by tenants) — every
permission, including `organization.manage`, `role.manage`, `user.manage`,
`assignment.manage`, `audit.view`, `session.revoke`.

**`warehouse_manager`** — `organization.view`, `branch.view`,
`warehouse.view`, `warehouse.manage`, `user.view`, `session.view`,
`inventory.view/create/adjust/approve_adjustment`, `product.view`,
`pricing.view`, `supplier.view`, `purchase_order.view`, `receiving.view/manage`,
`putaway.view/manage`, `transfer.create/approve/dispatch/receive`,
`order.view`, `fulfillment.view/execute`, `replenishment.view/manage`,
`stock_count.view/manage`, `return.view/manage`, `report.view/export`.

**`finance_accounts`** — `audit.view`, `branch.view`, `configuration.view`,
`inventory.view`, `order.view`, `organization.view`, `pricing.view/manage`,
`purchase_order.view/approve`, `report.view/export`, `supplier.view`,
`warehouse.view`.

**`inventory_controller`** — `inventory.view/create/adjust/approve_adjustment`,
`organization.view`, `pricing.view`, `product.view`, `putaway.view`,
`replenishment.view/manage`, `report.view/export`, `stock_count.view/manage`,
`transfer.create/approve/receive`, `warehouse.view`.

**`procurement_manager`** — `inventory.view`, `organization.view`,
`pricing.view/manage`, `product.view`, `purchase_order.view/create/approve`,
`putaway.view`, `receiving.view/manage`, `replenishment.view`,
`report.view/export`, `supplier.view/manage`, `warehouse.view`.

**`dispatch_coordinator`** — `fulfillment.view/execute`, `inventory.view`,
`order.view/manage`, `product.view`, `report.view`, `return.view/manage`,
`transfer.create/dispatch/receive`, `warehouse.view`.

**`management_viewer`** — read-only across the tenant: `audit.view`,
`branch.view`, `fulfillment.view`, `inventory.view`, `order.view`,
`organization.view`, `pricing.view`, `product.view`, `purchase_order.view`,
`putaway.view`, `receiving.view`, `replenishment.view`, `report.view/export`,
`return.view`, `stock_count.view`, `supplier.view`, `warehouse.view`.

**`sales_order_user`** — `fulfillment.view`, `inventory.view`,
`order.view/create/manage`, `organization.view`, `pricing.view`, `product.view`,
`report.view`, `return.view/manage`, `warehouse.view`.

**`warehouse_operator`** — shop-floor execution: `fulfillment.view/execute`,
`inventory.view/create`, `order.view`, `product.view`, `putaway.view/manage`,
`receiving.view/manage`, `return.view`, `stock_count.view/manage`,
`transfer.create/dispatch/receive`, `warehouse.view`. Cannot approve anything,
cannot adjust stock, cannot manage users or warehouses.

**`supplier_portal_user`** — `product.view`, `purchase_order.view`,
`receiving.view`, `supplier_portal.use`.

</details>

---

## 5. How a permission is evaluated

```python
AuthorizationService(user).has_permission(
    "transfer.approve", organization=acme, warehouse=wh_a1
)
```

The engine (`apps/security/authorization.py`) is **deny-by-default** and answers
strictly:

1. **Platform admins** (`is_superuser` / `is_staff`) hold everything.
2. Otherwise the caller's **assignments** are loaded and filtered:
   `is_active=True`, `is_suspended=False`, `role.is_active=True`, and not expired.
3. An assignment matches a scope only when:
   * the question names an **organization** → the grant must be organization-wide
     (a warehouse-scoped grant does not answer organization-wide questions);
   * the question names a **warehouse** → the grant must cover that warehouse, or
     be organization-wide for the same organization;
   * the question names **no scope** → the grant counts if the caller holds the
     permission anywhere (used only for endpoints that then scope their own
     queryset).
4. Anything else — including an inactive account — grants nothing.

Helpers built on the same primitive: `has_any`, `has_all`,
`effective_permission_codes`, `accessible_organization_ids`,
`accessible_warehouse_ids`, `highest_level`, `scope_queryset` (fails closed to
`.none()`), `ensure_permission`, `ensure_organization_access`,
`can_grant_role`, `can_manage_user`, `roles_grantable_by`.

### Failure semantics (no information leaks)

| Situation | Answer |
| --------- | ------ |
| Not authenticated | `401` (+ `WWW-Authenticate` challenge) |
| Authenticated, capability missing in a scope the caller can see | `403` |
| Authenticated, capability missing everywhere (no grant at all) | `403` |
| Resource belongs to a scope the caller cannot see | **`404`** (existence is not revealed) |

Query parameters can only **narrow** a scope: `?organization=`/`?warehouse=` are
filters applied *after* the entitlement filter, and writes that name a foreign
scope in the URL are rejected. Objects reached by primary key resolve through
scoped querysets, so horizontal probing returns `404`.

DRF integration (`apps/security/permissions.py`): views declare
`required_permissions = ("inventory.adjust",)` (or the `require_permission`
decorator); scope comes from URL kwargs, the view's `scope_kwargs`, or the object
being acted on.

---

## 6. Grant lifecycle

| Event | Effect on grants |
| ----- | ---------------- |
| Grant (`POST /security/assignments/`) | New row, `is_active=True`; re-granting an existing pair reactivates and clears suspension. |
| Expiry (`expires_at`) | Grant stops counting the moment it passes; the row is kept for audit. |
| Revoke (`DELETE /security/assignments/<id>/`) | `is_active=False`, `is_suspended=False` — an explicit revocation is **final**. |
| Account deactivated | Assignments are suspended (`is_active=False, is_suspended=True`): they grant nothing but are not lost. |
| Account reactivated | Suspended assignments are restored exactly as they were (including warehouse scope). |
| Account inactive | The engine denies **everything**, whatever the grants say. |

Only a caller who *already holds* `assignment.manage`, whose level is ≥ the
role's level, and who already holds every permission inside that role (and never
above level 90) may grant it — this is what blocks vertical privilege
escalation. Custom roles can never contain platform permissions and cannot
exceed the editor's own authority.

---

## 7. Authentication controls that back the model

| Control | Behaviour |
| ------- | --------- |
| Password hashing | Argon2id first (Django `PASSWORD_HASHERS`), `MD5PasswordHasher` only in tests. |
| Login identifier | Email, case-insensitive, unique. |
| Login attempts | Every attempt is recorded (`success`, `invalid_credentials`, `locked`, `inactive`, `unverified_email`, `mfa_required`, `mfa_failed`, `mfa_passed`, `throttled`). Failures increment a counter; 5 failures lock the account for 15 minutes. |
| Rate limiting | DRF scoped throttles: `login` 10/min, `password_reset` 5/h, `email` 5/h, `mfa` 10/min. |
| Enumeration | Unknown email, wrong password and inactive account all answer the same generic `401`; password reset always answers `202`. |
| Sessions | Tracked in `UserSession` (device label, IP, expiry). Login rotates the session key (fixation defence); revocation/idle expiry is enforced by middleware. Change-password and reset revoke other sessions; deactivation revokes all. |
| MFA / TOTP | Encrypted secrets (HKDF-SHA256 + Fernet), ±1 step window, replay-protected, 10 single-use recovery codes. Administrators are challenged once a device is confirmed. |
| Email verification | Single-use, SHA-256-hashed tokens (raw value only in the email), 24 h TTL; enforcement is a policy switch (`AUTH_REQUIRE_EMAIL_VERIFICATION`). |
| Password reset | Single-use token, 1 h TTL; the token is only consumed once the new password passes policy. |

Relevant settings (all environment-driven, see `config/settings/base.py`):
`AUTH_MAX_FAILED_ATTEMPTS`, `AUTH_LOCKOUT_SECONDS`, `AUTH_LOGIN_THROTTLE_RATE`,
`AUTH_PASSWORD_RESET_THROTTLE_RATE`, `AUTH_EMAIL_THROTTLE_RATE`,
`AUTH_MFA_THROTTLE_RATE`, `AUTH_MFA_VALID_WINDOW`, `AUTH_MFA_RECOVERY_CODE_COUNT`,
`AUTH_PASSWORD_RESET_TTL`, `AUTH_EMAIL_VERIFICATION_TTL`,
`AUTH_REQUIRE_EMAIL_VERIFICATION`, `AUTH_REQUIRE_MFA_FOR_ADMINS`,
`SESSION_COOKIE_AGE`, `SESSION_IDLE_TIMEOUT`.

---

## 8. API surface

| Area | Endpoints |
| ---- | --------- |
| Authentication | `POST auth/login/`, `POST auth/mfa/verify/`, `POST auth/logout/`, `GET auth/session/`, `POST auth/password/change/`, `POST auth/password/reset/`, `POST auth/password/reset/confirm/`, `POST auth/password/reset/validate/`, `POST auth/email/verify/`, `POST auth/email/resend/` |
| Self-service | `GET/PATCH profile/`, `GET sessions/`, `POST sessions/<id>/revoke/`, `POST sessions/revoke-all/`, `GET/POST mfa/`, `mfa/enrol/`, `mfa/confirm/`, `mfa/disable/`, `mfa/recovery-codes/` |
| User administration | `GET/POST users/`, `GET/PATCH users/<id>/`, `POST users/<id>/{activate,deactivate,set-password,resend-verification,revoke-sessions}/`, `GET users/<id>/sessions/` |
| Audit | `GET login-attempts/` — own attempts; with `audit.view` in scope, every account in the caller's organizations |
| Roles & permissions | `GET permissions/`, `GET permissions/grouped/`, `GET/POST roles/`, `GET/PATCH/DELETE roles/<id>/`, `PUT roles/<id>/permissions/`, `GET roles/grantable/`, `GET/POST assignments/`, `GET assignments/for-user/`, `DELETE assignments/<id>/`, `GET me/permissions/` |
| Tenancy | `GET/POST organizations/`, `GET/PATCH organizations/<id>/`, `GET organizations/<id>/{branches,warehouses}/`, `GET/POST organizations/branches/`, `POST organizations/branches/<id>/deactivate/`, `GET/POST warehouses/`, `POST warehouses/<id>/{activate,deactivate}/`, `GET warehouses/me/` |

Deletion policy: organizations and warehouses are **archived/deactivated**, never
deleted (`DELETE` answers `400` with an explanation); users are deactivated;
branches may only be deleted while they have no warehouses.

`me/permissions/` returns the caller's effective permissions, organization ids
and warehouse ids — the frontend uses it to decide which controls to *offer*.

---

## 9. Frontend responsibilities

* `AuthProvider` mirrors `GET identity/auth/session/` (identity, permissions,
  organization/warehouse scope) and exposes `hasPermission()`.
* `RequireAuth` gates the application shell; `RequirePermission` renders an
  explicit "you do not have access" state instead of a broken screen.
* Administration screens (Users, Roles, Permissions) only appear in the sidebar
  when the matching permission is present — but every action they trigger is
  authorized again by the API, which is the only enforcement point that matters.

---

## 10. Extending the model

1. Add the permission to `apps/security/permission_registry.py`
   (`_perm("module.action", "Human name", "What it allows", sensitive=False)`).
2. Add it to any system role in `role_registry.py` that should hold it.
3. Run `manage.py makemigrations security` (the seed migration re-runs) and
   `manage.py sync_rbac`; verify with `sync_rbac --check`.
4. Declare it on the endpoints that need it — `required_permissions` on the view
   or `@require_permission("module.action")` — and add an authorization test
   (see `apps/security/tests/test_authorization_api.py` as the template).

Never create permissions at runtime, never grant a permission directly to a
user, and never let the frontend be the only thing standing between a caller and
an action.
