"""Test factories shared by the identity, security, organizations and
warehouses test suites.

Deliberately explicit (no randomness in defaults) so failures are reproducible
and tests read like the domain story: an organization, its branches and
warehouses, users with scoped role assignments.
"""
from __future__ import annotations

from django.utils import timezone

from apps.identity.models import User
from apps.organizations.models import Branch, Organization
from apps.security.models import Role, RoleAssignment
from apps.warehouses.models import Warehouse

DEFAULT_PASSWORD = "Wims-Test-Password-2026!"  # noqa: S105 - test fixture, not a secret


def make_organization(code: str = "ACME", name: str | None = None, **kwargs) -> Organization:
    return Organization.objects.create(
        code=code.upper(), name=name or f"{code.title()} Holdings", **kwargs
    )


def make_branch(organization: Organization, code: str = "BR1", **kwargs) -> Branch:
    return Branch.objects.create(
        organization=organization, code=code.upper(), name=kwargs.pop("name", f"Branch {code}"), **kwargs
    )


def make_warehouse(branch: Branch, code: str = "WH1", **kwargs) -> Warehouse:
    return Warehouse.objects.create(
        branch=branch,
        code=code.upper(),
        name=kwargs.pop("name", f"Warehouse {code}"),
        **kwargs,
    )


def make_user(
    email: str,
    *,
    organization: Organization | None = None,
    password: str | None = DEFAULT_PASSWORD,
    is_platform_admin: bool = False,
    **kwargs,
) -> User:
    kwargs.setdefault("first_name", email.split("@")[0].title())
    kwargs.setdefault("last_name", "Tester")
    if is_platform_admin:
        return User.objects.create_superuser(
            email=email, password=password, organization=organization, **kwargs
        )
    return User.objects.create_user(email=email, password=password, organization=organization, **kwargs)


def role(code: str) -> Role:
    """Fetch a seeded system role (see apps/security/role_registry.py)."""
    return Role.objects.get(organization__isnull=True, code=code)


def make_custom_role(
    organization: Organization,
    code: str,
    permission_codes: list[str],
    *,
    level: int = 50,
    name: str | None = None,
) -> Role:
    from apps.security.models import Permission

    custom = Role.objects.create(
        organization=organization,
        code=code,
        name=name or code.replace("_", " ").title(),
        level=level,
        is_system=False,
    )
    custom.permissions.set(Permission.objects.filter(codename__in=permission_codes))
    return custom


def assign(
    user: User,
    role_or_code: Role | str,
    *,
    organization: Organization | None = None,
    warehouse: Warehouse | None = None,
    actor: User | None = None,
    expires_at=None,
    is_active: bool = True,
) -> RoleAssignment:
    """Grant a role to a user in a scope (bypasses service guards on purpose:
    tests build state directly, then exercise the guards through the API)."""
    the_role = role(role_or_code) if isinstance(role_or_code, str) else role_or_code
    if organization is None and warehouse is not None:
        organization = warehouse.organization
    return RoleAssignment.objects.create(
        user=user,
        role=the_role,
        organization=organization,
        warehouse=warehouse,
        granted_by=actor,
        expires_at=expires_at or None,
        is_active=is_active,
    )


#: Broad administrative permission set used to build an "organization admin"
#: custom role in tests (also documents what an org admin must hold to be able
#: to delegate the operational roles).
ORG_ADMIN_PERMISSIONS: list[str] = [
    "organization.view",
    "branch.view",
    "branch.manage",
    "warehouse.view",
    "warehouse.manage",
    "user.view",
    "user.manage",
    "role.view",
    "role.manage",
    "assignment.manage",
    "session.view",
    "session.revoke",
    "audit.view",
    "inventory.view",
    "inventory.create",
    "product.view",
    "pricing.view",
    "supplier.view",
    "purchase_order.view",
    "receiving.view",
    "receiving.manage",
    "putaway.view",
    "putaway.manage",
    "transfer.create",
    "transfer.dispatch",
    "transfer.receive",
    "order.view",
    "fulfillment.view",
    "fulfillment.execute",
    "replenishment.view",
    "stock_count.view",
    "stock_count.manage",
    "return.view",
    "report.view",
    "report.export",
    "configuration.view",
    "notification.manage",
]


def make_org_admin(organization: Organization, email: str = "orgadmin@example.com", **kwargs) -> User:
    """A user holding a custom organization-admin role (level 60)."""
    user = make_user(email, organization=organization, **kwargs)
    custom = make_custom_role(
        organization,
        "org_admin",
        ORG_ADMIN_PERMISSIONS,
        level=60,
        name="Organization Admin",
    )
    assign(user, custom, organization=organization)
    return user


def expired(**kwargs):
    return timezone.now() - timezone.timedelta(**kwargs)


def future(**kwargs):
    return timezone.now() + timezone.timedelta(**kwargs)
