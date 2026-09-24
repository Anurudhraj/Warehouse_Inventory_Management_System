"""DRF permission classes and view mixins.

Every protected endpoint declares the permission(s) it needs — either through
``required_permissions`` on the view or the :func:`require_permission`
decorator — and the check is always evaluated by the authorization engine
against the caller's *scoped* assignments. There is no alternative code path a
view could use to skip the engine.

Scope resolution order for the requested organization/warehouse:

1. explicit ``scope_kwargs`` provided by the view,
2. URL keyword arguments (``organization_pk``, ``warehouse_pk``, …),
3. query parameters (``organization``, ``warehouse``),
4. the object being acted on (object-level checks in serializers/services).

Failure semantics (important for avoiding information disclosure):

* not authenticated          → ``401``
* authenticated, no permission in a scope **you can see** → ``403``
* resource in a scope you cannot see (another organization/warehouse) → ``404``
"""
from __future__ import annotations

import functools
from collections.abc import Sequence

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from rest_framework import exceptions, permissions

from apps.security.authorization import authorization_for

ORGANIZATION_URL_KWARGS = ("organization_pk", "organization_id", "organization")
WAREHOUSE_URL_KWARGS = ("warehouse_pk", "warehouse_id", "warehouse")
ORGANIZATION_QUERY_PARAMS = ("organization", "organization_id")
WAREHOUSE_QUERY_PARAMS = ("warehouse", "warehouse_id")


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_UNSET = object()


def resolve_scope(view, request) -> tuple[int | None, int | None]:
    """``(organization_id, warehouse_id)`` addressed by *this URL*.

    Only URL path parameters count: a ``?warehouse=`` query parameter is a
    filter, and filters must never be able to widen access. Objects reached by
    primary key are resolved through scoped querysets instead (out-of-scope →
    404), which is why an unscoped capability check is safe here.
    """
    organization_id = warehouse_id = None

    for kwarg in ORGANIZATION_URL_KWARGS:
        if kwarg in getattr(view, "kwargs", {}):
            organization_id = _as_int(view.kwargs[kwarg])
            break
    for kwarg in WAREHOUSE_URL_KWARGS:
        if kwarg in getattr(view, "kwargs", {}):
            warehouse_id = _as_int(view.kwargs[kwarg])
            break

    return organization_id, warehouse_id


def query_scope(request) -> tuple[int | None, int | None]:
    """``(organization_id, warehouse_id)`` named in the query string."""
    organization_id = warehouse_id = None
    for param in ORGANIZATION_QUERY_PARAMS:
        value = request.query_params.get(param)
        if value:
            organization_id = _as_int(value)
            break
    for param in WAREHOUSE_QUERY_PARAMS:
        value = request.query_params.get(param)
        if value:
            warehouse_id = _as_int(value)
            break
    return organization_id, warehouse_id


def _load_scope_objects(organization_id, warehouse_id):
    from apps.organizations.models import Organization
    from apps.warehouses.models import Warehouse

    organization = (
        Organization.objects.filter(pk=organization_id).first() if organization_id else None
    )
    warehouse = Warehouse.objects.filter(pk=warehouse_id).first() if warehouse_id else None
    return organization, warehouse


class BaseScopedPermission(permissions.BasePermission):
    """Shared machinery for permission classes that resolve request scope."""

    message = "You do not have permission to perform this action."
    #: "all" → every declared permission required; "any" → at least one.
    mode = "all"

    def required_permissions(self, view) -> Sequence[str]:
        perms = getattr(view, "required_permissions", None)
        if perms:
            return tuple(perms)
        single = getattr(view, "required_permission", None)
        return (single,) if single else ()

    def scope(self, view, request):
        """Resolve the scope this request *addresses* (URL, or the view's own rules)."""
        explicit = getattr(view, "scope_kwargs", None)
        if callable(explicit):  # bound method: scope_kwargs(request)
            ids = explicit(request) or {}
            return _load_scope_objects(
                _as_int(ids.get("organization_id")), _as_int(ids.get("warehouse_id"))
            )
        if isinstance(explicit, dict):
            return _load_scope_objects(
                _as_int(explicit.get("organization_id")), _as_int(explicit.get("warehouse_id"))
            )
        return _load_scope_objects(*resolve_scope(view, request))

    def effective_mode(self, view) -> str:
        return getattr(view, "permission_mode", None) or self.mode

    def handle_denial(self, request, organization, warehouse):
        """Translate a denial into 401 / 403 / 404 without disclosing scope."""
        service = authorization_for(request)
        if not service.is_authenticated:
            raise exceptions.NotAuthenticated(
                "Authentication credentials were not provided."
            )
        # Visible scope but missing capability → 403.
        if organization is None and warehouse is None:
            return False
        if organization is not None and service.can_access_organization(organization):
            return False
        if warehouse is not None and service.can_access_warehouse(warehouse):
            return False
        # Out-of-scope resource → pretend it does not exist.
        raise exceptions.NotFound("Not found.")


class HasScopedPermission(BaseScopedPermission):
    """Requires the declared permission(s) inside the resolved request scope."""

    def has_permission(self, request, view) -> bool:
        service = authorization_for(request)

        # A write request that names a scope in the query string must prove
        # access to that scope before anything else happens.
        if request.method not in SAFE_METHODS:
            query_organization, query_warehouse = query_scope(request)
            if query_warehouse is not None or query_organization is not None:
                organization, warehouse = _load_scope_objects(query_organization, query_warehouse)
                self.handle_denial(request, organization, warehouse)

        codenames = self.required_permissions(view)
        if not codenames:
            return True

        organization, warehouse = self.scope(view, request)
        results = [
            service.has_permission(codename, organization=organization, warehouse=warehouse)
            for codename in codenames
        ]

        if self.effective_mode(view) == "any":
            if any(results):
                return True
            return self.handle_denial(request, organization, warehouse)

        if all(results):
            return True
        return self.handle_denial(request, organization, warehouse)


class HasAnyScopedPermission(HasScopedPermission):
    """Requires at least one of the declared permissions."""

    mode = "any"


class IsAuthenticatedAndActive(permissions.BasePermission):
    """Authenticated with an active account."""

    message = "Authentication credentials were not provided or the account is inactive."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class IsPlatformAdmin(permissions.BasePermission):
    message = "Platform administrator access required."

    def has_permission(self, request, view) -> bool:
        service = authorization_for(request)
        if not service.is_authenticated:
            raise exceptions.NotAuthenticated("Authentication credentials were not provided.")
        return service.is_platform_admin


def require_permission(
    *codenames: str,
    mode: str = "all",
    organization_kwarg: str | None = None,
    warehouse_kwarg: str | None = None,
):
    """Decorator for function-based views and ``APIView`` methods.

    Usage::

        @require_permission("inventory.adjust", warehouse_kwarg="warehouse_pk")
        def post(self, request, warehouse_pk): ...
    """

    def decorator(view_method):
        @functools.wraps(view_method)
        def wrapper(view, request, *args, **kwargs):
            service = authorization_for(request)
            organization = warehouse = None

            if organization_kwarg and kwargs.get(organization_kwarg):
                from apps.organizations.models import Organization

                organization = Organization.objects.filter(
                    pk=_as_int(kwargs[organization_kwarg])
                ).first()
            if warehouse_kwarg and kwargs.get(warehouse_kwarg):
                from apps.warehouses.models import Warehouse

                warehouse = Warehouse.objects.filter(
                    pk=_as_int(kwargs[warehouse_kwarg])
                ).first()
            if organization is None and warehouse is None:
                organization, warehouse = _load_scope_objects(*resolve_scope(view, request))

            results = [
                service.has_permission(code, organization=organization, warehouse=warehouse)
                for code in codenames
            ]
            granted = any(results) if mode == "any" else all(results)
            if granted:
                return view_method(view, request, *args, **kwargs)

            if not service.is_authenticated:
                raise exceptions.NotAuthenticated(
                    "Authentication credentials were not provided."
                )
            if organization is not None and not service.can_access_organization(organization):
                raise exceptions.NotFound("Not found.")
            if warehouse is not None and not service.can_access_warehouse(warehouse):
                raise exceptions.NotFound("Not found.")
            raise DjangoPermissionDenied("You do not have permission to perform this action.")

        return wrapper

    return decorator


def require_authenticated(view_method):
    """Decorator enforcing an authenticated, active session."""

    @functools.wraps(view_method)
    def wrapper(view, request, *args, **kwargs):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            raise exceptions.NotAuthenticated("Authentication credentials were not provided.")
        return view_method(view, request, *args, **kwargs)

    return wrapper


def ensure_object_scope(request, organization=None, warehouse=None) -> None:
    """Object-level scope guard for services/serializers (fail closed)."""
    if organization is None and warehouse is None:
        return
    service = authorization_for(request)
    if organization is not None and not service.can_access_organization(organization):
        raise exceptions.NotFound("Not found.")
    if warehouse is not None and not service.can_access_warehouse(warehouse):
        raise exceptions.NotFound("Not found.")


__all__ = [
    "BaseScopedPermission",
    "HasAnyScopedPermission",
    "HasScopedPermission",
    "IsAuthenticatedAndActive",
    "IsPlatformAdmin",
    "ensure_object_scope",
    "query_scope",
    "require_authenticated",
    "require_permission",
    "resolve_scope",
]
