"""Authorization engine — the single place permission decisions are made.

Everything in the API (views, services, querysets) asks this module whether a
user may do something, *in which scope*. Views never inspect roles directly,
so a decision can never drift between endpoints.

Guarantees
----------
* **Deny by default** — no assignment, no access.
* **Scoped** — a grant only ever applies to its organization/warehouse scope
  (prevents cross-organization and cross-warehouse access).
* **Vertical safety** — a user can only delegate roles/permissions they
  themselves hold, at or below their own authority level
  (``can_grant_role`` / ``can_grant_permission``).
* **Fail closed** — inactive/expired assignments, deactivated users and
  locked accounts grant nothing.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.security.models import Permission, Role, RoleAssignment
from apps.security.role_registry import MAX_DELEGABLE_LEVEL, PLATFORM_ROLE_CODES

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ScopeViolation(PermissionDenied):
    """Raised when a request tries to act outside the caller's scope.

    Views translate this into ``404`` for cross-organization/warehouse object
    access (do not disclose that the object exists) and ``403`` when the
    caller can see the scope but lacks the permission.
    """


@dataclass(frozen=True)
class PermissionCheck:
    """Result of a permission evaluation (kept for logging/diagnostics)."""

    codename: str
    granted: bool
    reason: str = ""


class AuthorizationService:
    """Per-request authorization context for a user.

    Instantiate once per request (``AuthorizationService(request.user)``); the
    effective data is memoised so a request performs at most a couple of
    queries regardless of how many checks it makes.
    """

    def __init__(self, user):
        self.user = user
        self._assignments: list[RoleAssignment] | None = None

    # -- context ----------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return bool(self.user and getattr(self.user, "is_authenticated", False))

    @property
    def is_platform_admin(self) -> bool:
        """Platform staff: unrestricted scope (still fully authenticated/active)."""
        if not self.is_authenticated or not self.user.is_active:
            return False
        return bool(self.user.is_superuser or self.user.is_platform_admin)

    @property
    def organization_id(self) -> int | None:
        return getattr(self.user, "organization_id", None)

    # -- assignment loading -------------------------------------------------
    @staticmethod
    def _active_assignments_qs(user) -> QuerySet[RoleAssignment]:
        now = timezone.now()
        return (
            RoleAssignment.objects.filter(
                user=user, is_active=True, is_suspended=False, role__is_active=True
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .select_related("role", "organization", "warehouse")
        )

    @property
    def assignments(self) -> list[RoleAssignment]:
        if self._assignments is None:
            self._assignments = list(self._active_assignments_qs(self.user)) if self.is_authenticated else []
        return self._assignments

    def _assignment_matches(self, assignment: RoleAssignment, organization, warehouse) -> bool:
        """Does this grant cover the requested scope?

        Strictness matters for privilege escalation: a grant limited to one
        warehouse must **not** imply organization-wide authority.

        ====================  ====================================================
        requested scope       requirement
        ====================  ====================================================
        platform grant        any (``organization`` is NULL on the assignment)
        ``organization`` only assignment is organization-wide (``warehouse`` NULL)
        ``warehouse``         assignment is that warehouse *or* organization-wide
        neither (unscoped)    any assignment — "does the user hold this at all?"
        ====================  ====================================================
        """
        if assignment.organization_id is None:
            return True  # platform-scoped grant covers everything

        if organization is None and warehouse is None:
            return True  # unscoped check: "holds this permission in some scope"

        if organization is not None and assignment.organization_id != _id_of(organization):
            return False

        if warehouse is None:
            # Organization-level question: a warehouse-limited grant cannot answer it.
            return assignment.warehouse_id is None

        return assignment.warehouse_id in (None, _id_of(warehouse))

    # -- permission evaluation ---------------------------------------------
    def has_permission(self, codename: str, *, organization=None, warehouse=None) -> bool:
        """Deny-by-default permission check, optionally scoped."""
        if not self.is_authenticated or not self.user.is_active:
            return False
        if self.is_platform_admin:
            return True

        # A warehouse implies its organization: keep callers honest.
        if warehouse is not None and organization is None:
            organization = getattr(warehouse, "organization", None)

        for assignment in self.assignments:
            if not self._assignment_matches(assignment, organization, warehouse):
                continue
            if codename in assignment.role.permission_codes:
                return True
        return False

    def has_any_permission(self, codenames: Iterable[str], **scope) -> bool:
        return any(self.has_permission(code, **scope) for code in codenames)

    def has_all_permissions(self, codenames: Iterable[str], **scope) -> bool:
        return all(self.has_permission(code, **scope) for code in codenames)

    # -- scope helpers -------------------------------------------------------
    def accessible_organization_ids(self) -> set[int]:
        """Organizations this user may act in (empty set = none)."""
        if not self.is_authenticated or not self.user.is_active:
            return set()
        if self.is_platform_admin:
            from apps.organizations.models import Organization

            return set(Organization.objects.values_list("id", flat=True))

        return {
            assignment.organization_id
            for assignment in self.assignments
            if assignment.organization_id
        }

    def accessible_warehouse_ids(self, organization=None) -> set[int]:
        """Warehouse ids in scope.

        Org-wide assignments (``warehouse`` NULL) expose every warehouse of the
        organization; warehouse-scoped assignments expose only that warehouse.
        """
        from apps.warehouses.models import Warehouse

        if not self.is_authenticated or not self.user.is_active:
            return set()
        if self.is_platform_admin:
            qs = Warehouse.objects.all()
            if organization is not None:
                qs = qs.filter(branch__organization=organization)
            return set(qs.values_list("id", flat=True))

        org_ids = {_id_of(organization)} if organization is not None else self.accessible_organization_ids()
        if not org_ids:
            return set()

        open_org_ids: set[int] = set()
        explicit_ids: set[int] = set()
        for assignment in self.assignments:
            if assignment.organization_id is None:
                continue
            if assignment.organization_id not in org_ids:
                continue
            if assignment.warehouse_id is None:
                open_org_ids.add(assignment.organization_id)
            else:
                explicit_ids.add(assignment.warehouse_id)

        ids = set(
            Warehouse.objects.filter(branch__organization_id__in=open_org_ids).values_list(
                "id", flat=True
            )
        )
        if explicit_ids:
            allowed = Warehouse.objects.filter(
                id__in=explicit_ids, branch__organization_id__in=org_ids
            ).values_list("id", flat=True)
            ids.update(allowed)
        return ids

    def can_access_organization(self, organization) -> bool:
        if organization is None:
            return False
        return _id_of(organization) in self.accessible_organization_ids()

    def can_access_warehouse(self, warehouse) -> bool:
        if warehouse is None:
            return False
        return _id_of(warehouse) in self.accessible_warehouse_ids()

    # -- enforcement helpers -------------------------------------------------
    def ensure_organization_access(self, organization) -> None:
        """Raise :class:`ScopeViolation` when the organization is out of scope."""
        if not self.can_access_organization(organization):
            raise ScopeViolation("You do not have access to this organization.")

    def ensure_warehouse_access(self, warehouse) -> None:
        if not self.can_access_warehouse(warehouse):
            raise ScopeViolation("You do not have access to this warehouse.")

    def ensure_permission(self, codename: str, *, organization=None, warehouse=None) -> None:
        if not self.has_permission(codename, organization=organization, warehouse=warehouse):
            raise PermissionDenied(f"Missing permission: {codename}")

    # -- effective permissions (for UI + diagnostics) -------------------------
    def effective_permission_codes(self, *, organization=None, warehouse=None) -> set[str]:
        if not self.is_authenticated or not self.user.is_active:
            return set()
        if self.is_platform_admin:
            return {p.codename for p in Permission.objects.all()}

        codes: set[str] = set()
        for assignment in self.assignments:
            if self._assignment_matches(assignment, organization, warehouse):
                codes |= assignment.role.permission_codes
        return codes

    def highest_level(self, organization=None) -> int:
        """Authority rank of the user's strongest role in scope."""
        if self.is_platform_admin:
            return 100
        level = 0
        for assignment in self.assignments:
            if self._assignment_matches(assignment, organization, None):
                level = max(level, assignment.role.level)
        return level

    # -- delegation safety (prevents vertical privilege escalation) -----------
    def can_grant_role(self, role: Role, *, organization=None, warehouse=None) -> tuple[bool, str]:
        """May the caller grant ``role`` in this scope?

        Rules (all must hold):

        1. caller holds ``assignment.manage`` in the scope;
        2. platform-only roles require a platform admin;
        3. the role's authority level must not exceed the caller's own;
        4. every permission in the role must already be held by the caller;
        5. non-platform admins cannot grant at/above the reserved ceiling.
        """
        if self.is_platform_admin:
            return True, ""

        if not self.has_permission(
            "assignment.manage", organization=organization, warehouse=warehouse
        ):
            return False, "You do not have permission to manage role assignments."

        if role.code in PLATFORM_ROLE_CODES or role.is_platform:
            return False, "Platform roles can only be granted by platform administrators."

        if role.level > MAX_DELEGABLE_LEVEL:
            return False, "This role exceeds the maximum delegable authority level."

        if role.level > self.highest_level(organization=organization):
            return False, "You cannot grant a role with higher authority than your own."

        missing = [
            code
            for code in role.permission_codes
            if not self.has_permission(code, organization=organization, warehouse=warehouse)
        ]
        if missing:
            preview = ", ".join(sorted(missing)[:5])
            return False, f"You cannot grant permissions you do not hold ({preview})."

        return True, ""

    def can_manage_user(self, target_user, *, organization=None) -> tuple[bool, str]:
        """May the caller administer ``target_user``?"""
        if self.is_platform_admin:
            return True, ""
        if not self.user or not self.user.is_authenticated:
            return False, "Authentication required."
        if target_user.id == self.user.id:
            return True, ""  # self-service (profile, own sessions)
        if target_user.is_superuser or target_user.is_staff:
            return False, "Only platform administrators can manage platform accounts."
        scope_org = organization or getattr(target_user, "organization", None)
        if target_user.organization_id and not self.can_access_organization(target_user.organization):
            return False, "This user belongs to an organization you cannot access."
        if not self.has_permission("user.manage", organization=scope_org):
            return False, "Missing permission: user.manage"
        if target_user.highest_role_level() > self.highest_level(organization=scope_org):
            return False, "This user has higher authority than you."
        return True, ""

    # -- queryset scoping -----------------------------------------------------
    def scope_queryset(self, queryset: QuerySet, *, organization_field="organization", warehouse_field=None) -> QuerySet:
        """Restrict a queryset to the caller's accessible scope (fail closed)."""
        if not self.is_authenticated or not self.user.is_active:
            return queryset.none()
        if self.is_platform_admin:
            return queryset
        org_ids = self.accessible_organization_ids()
        if not org_ids:
            return queryset.none()
        queryset = queryset.filter(**{f"{organization_field}__in": org_ids})
        if warehouse_field:
            warehouse_ids = self.accessible_warehouse_ids()
            queryset = queryset.filter(
                Q(**{f"{warehouse_field}__in": warehouse_ids})
                | Q(**{f"{warehouse_field}__isnull": True})
            )
        return queryset


def _id_of(obj) -> int | None:
    if obj is None:
        return None
    return getattr(obj, "pk", obj)


def authorization_for(request) -> AuthorizationService:
    """Return (and cache) the authorization service for a request."""
    service = getattr(request, "_authorization_service", None)
    if service is None:
        service = AuthorizationService(request.user)
        request._authorization_service = service
    return service


def accessible_organizations_for(user):
    from apps.organizations.models import Organization

    service = AuthorizationService(user)
    return Organization.objects.filter(id__in=service.accessible_organization_ids())


def accessible_warehouses_for(user, organization=None):
    from apps.warehouses.models import Warehouse

    service = AuthorizationService(user)
    return Warehouse.objects.filter(id__in=service.accessible_warehouse_ids(organization))


def ensure_assignable_scope(assignment: RoleAssignment, actor) -> None:
    """Defence in depth for stored assignments (used by tests and services)."""
    service = AuthorizationService(actor)
    if not service.is_platform_admin and assignment.organization_id not in service.accessible_organization_ids():
        raise ScopeViolation("Assignment target is outside your scope.")


def roles_grantable_by(user, organization=None) -> Sequence[Role]:
    """Roles the user may hand out in a scope (drives the assignment UI)."""
    service = AuthorizationService(user)
    qs = Role.objects.filter(is_active=True)
    if not service.is_platform_admin:
        qs = qs.filter(is_platform=False, level__lte=MAX_DELEGABLE_LEVEL)
        if organization is not None:
            qs = qs.filter(Q(organization__isnull=True) | Q(organization=organization))
    return [role for role in qs if service.can_grant_role(role, organization=organization)[0]]
