"""RBAC API views: permissions, roles, role assignments and effective access.

Enforcement rules (see ``docs/rbac.md``):

* permissions are read-only — they are code-defined, not user data;
* system roles are read-only through the API (name/level/permissions fixed);
* organization admins can create custom roles inside their own organization;
* granting a role requires ``assignment.manage`` **and** every permission the
  role contains (no privilege escalation), plus scope checks on the target user,
  organization and warehouse.
"""
from __future__ import annotations

import logging

from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.identity.models import User
from apps.organizations.models import Organization
from apps.security.authorization import authorization_for, roles_grantable_by
from apps.security.models import Permission, Role, RoleAssignment
from apps.security.permission_registry import (
    ALL_PERMISSION_CODES,
    PERMISSION_MODULES,
    PERMISSIONS,
)
from apps.security.permissions import HasScopedPermission, IsAuthenticatedAndActive
from apps.security.serializers import (
    PermissionSerializer,
    RoleAssignmentCreateSerializer,
    RoleAssignmentSerializer,
    RoleCreateSerializer,
    RolePermissionUpdateSerializer,
    RoleSerializer,
)
from apps.security.services import RoleService
from apps.warehouses.models import Warehouse

logger = logging.getLogger("apps.security.api")


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """The permission registry (code-defined, read-only)."""

    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticatedAndActive, HasScopedPermission]
    required_permissions = ("role.view",)
    pagination_class = None  # ~56 rows: return them all, grouped by the client
    queryset = Permission.objects.all().order_by("module", "codename")

    @action(detail=False, methods=["get"])
    def grouped(self, request):
        """Permissions grouped by module — convenient for role editors."""
        grouped: dict[str, list[dict]] = {module: [] for module in PERMISSION_MODULES}
        for permission in Permission.objects.all().order_by("codename"):
            grouped.setdefault(permission.module, []).append(
                {
                    "codename": permission.codename,
                    "name": permission.name,
                    "description": permission.description,
                    "is_sensitive": permission.is_sensitive,
                }
            )
        return Response({"count": len(ALL_PERMISSION_CODES), "modules": grouped})

    @action(detail=False, methods=["get"], url_path="registry")
    def registry(self, request):
        """Registry straight from code (includes the module/sensitivity metadata)."""
        return Response(
            {
                "count": len(PERMISSIONS),
                "modules": PERMISSION_MODULES,
                "permissions": [
                    {
                        "codename": p.codename,
                        "name": p.name,
                        "module": p.module,
                        "description": p.description,
                        "is_sensitive": p.sensitive,
                    }
                    for p in PERMISSIONS
                ],
            }
        )


class RoleViewSet(viewsets.ModelViewSet):
    """Roles: system roles (read-only) and organization-scoped custom roles."""

    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticatedAndActive, HasScopedPermission]
    pagination_class = StandardPagination
    ordering = ["-level", "name"]

    def get_queryset(self):
        service = authorization_for(self.request)
        qs = (
            Role.objects.select_related("organization")
            .annotate(assignment_total=Count("assignments", distinct=True))
            .order_by("-level", "name")
        )
        if service.is_platform_admin:
            return qs
        org_ids = service.accessible_organization_ids()
        return qs.filter(Q(organization__isnull=True) | Q(organization_id__in=org_ids))

    def get_required_permissions(self) -> tuple[str, ...]:
        if self.action in ("list", "retrieve", "grantable"):
            return ("role.view",)
        return ("role.manage",)

    @property
    def required_permissions(self) -> tuple[str, ...]:
        return self.get_required_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return RoleCreateSerializer
        if self.action in ("update", "partial_update"):
            return RoleCreateSerializer
        return RoleSerializer

    def create(self, request, *args, **kwargs):
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        organization = request.user.organization
        organization_id = request.data.get("organization")
        if organization_id:
            organization = Organization.objects.filter(pk=organization_id).first()
            if organization is None:
                raise ValidationError({"organization": ["Unknown organization."]})
        service = authorization_for(request)
        if organization is None:
            raise ValidationError(
                {"organization": ["An organization is required to create a custom role."]}
            )
        service.ensure_organization_access(organization)

        role = RoleService.create_role(
            actor=request.user,
            organization=organization,
            code=data["code"],
            name=data["name"],
            description=data.get("description", ""),
            level=data.get("level", 40),
            permission_codes=data.get("permission_codes", []),
        )
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        role = self.get_object()
        self._assert_role_editable(role)
        serializer = RoleCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if "permission_codes" in data:
            RoleService.set_permissions(
                actor=request.user, role=role, permission_codes=data["permission_codes"]
            )
        for field in ("name", "description", "level"):
            if field in data:
                setattr(role, field, data[field])
        role.save()
        return Response(RoleSerializer(role).data)

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        self._assert_role_editable(role)
        if role.assignments.exists():
            raise ValidationError(
                {
                    "detail": (
                        "This role is still assigned to users. Revoke those assignments "
                        "before deleting it."
                    )
                }
            )
        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _assert_role_editable(self, role: Role) -> None:
        if role.is_system:
            raise PermissionDenied(
                "System roles are defined by the platform and cannot be modified. "
                "Clone the role to customize it."
            )
        service = authorization_for(request=self.request)
        if role.organization_id is None or not service.can_access_organization(role.organization):
            raise NotFound("Not found.")
        if role.level > service.highest_level(organization=role.organization):
            raise PermissionDenied("You cannot modify a role with higher authority than your own.")

    @action(detail=False, methods=["get"])
    def grantable(self, request):
        """Roles the caller may grant (drives the assignment UI)."""
        organization = None
        organization_id = request.query_params.get("organization")
        if organization_id:
            organization = Organization.objects.filter(pk=organization_id).first()
            if organization is None:
                raise ValidationError({"organization": ["Unknown organization."]})
            authorization_for(request).ensure_organization_access(organization)
        roles = roles_grantable_by(request.user, organization=organization)
        return Response({"count": len(roles), "results": RoleSerializer(roles, many=True).data})

    @action(detail=True, methods=["put", "patch"], url_path="permissions")
    def set_permissions(self, request, pk=None):
        role = self.get_object()
        self._assert_role_editable(role)
        serializer = RolePermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        RoleService.set_permissions(
            actor=request.user, role=role, permission_codes=serializer.validated_data["permission_codes"]
        )
        return Response(RoleSerializer(role).data)


class RoleAssignmentViewSet(viewsets.ModelViewSet):
    """Role assignments (user ↔ role ↔ organization/warehouse scope)."""

    serializer_class = RoleAssignmentSerializer
    permission_classes = [IsAuthenticatedAndActive, HasScopedPermission]
    required_permissions = ("assignment.manage",)
    pagination_class = StandardPagination
    ordering = ["-granted_at"]

    def get_queryset(self):
        service = authorization_for(self.request)
        qs = RoleAssignment.objects.select_related("role", "user", "organization", "warehouse")
        if service.is_platform_admin:
            return qs

        org_ids = service.accessible_organization_ids()
        warehouse_ids = service.accessible_warehouse_ids()
        return qs.filter(
            Q(organization_id__in=org_ids) | Q(warehouse_id__in=warehouse_ids)
        ).distinct()

    def get_serializer_class(self):
        return RoleAssignmentCreateSerializer if self.action == "create" else RoleAssignmentSerializer

    def create(self, request, *args, **kwargs):
        serializer = RoleAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.filter(pk=data["user"]).first()
        role = Role.objects.filter(pk=data["role"]).first()
        organization = (
            Organization.objects.filter(pk=data.get("organization")).first()
            if data.get("organization")
            else None
        )
        warehouse = (
            Warehouse.objects.filter(pk=data.get("warehouse")).first()
            if data.get("warehouse")
            else None
        )
        if user is None:
            raise ValidationError({"user": ["Unknown user."]})
        if role is None:
            raise ValidationError({"role": ["Unknown role."]})

        assignment = RoleService.grant_role(
            actor=request.user,
            user=user,
            role=role,
            organization=organization,
            warehouse=warehouse,
            expires_at=data.get("expires_at"),
            note=data.get("note", ""),
        )
        return Response(RoleAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        raise ValidationError(
            {"detail": "Assignments are immutable. Revoke the assignment and create a new one."}
        )

    def destroy(self, request, *args, **kwargs):
        assignment = self.get_object()
        RoleService.revoke_assignment(actor=request.user, assignment=assignment)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="for-user")
    def for_user(self, request):
        """All assignments of one user (admin view of who can do what)."""
        user_id = request.query_params.get("user")
        if not user_id:
            raise ValidationError({"user": ["This query parameter is required."]})
        target = User.objects.filter(pk=user_id).first()
        if target is None:
            raise NotFound("Not found.")
        service = authorization_for(request)
        if not service.is_platform_admin:
            if target.organization_id and not service.can_access_organization(target.organization):
                raise NotFound("Not found.")
            if target.id != request.user.id:
                allowed, reason = service.can_manage_user(target)
                if not allowed:
                    raise PermissionDenied(reason)
        assignments = (
            RoleAssignment.objects.filter(user=target)
            .select_related("role", "organization", "warehouse")
            .order_by("-granted_at")
        )
        return Response(RoleAssignmentSerializer(assignments, many=True).data)


class EffectivePermissionsView(APIView):
    """Effective access for the authenticated caller.

    This is what the frontend uses to hide unavailable actions — the backend
    still enforces every call independently.
    """

    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        service = authorization_for(request)
        assignments = service.assignments
        return Response(
            {
                "is_platform_admin": service.is_platform_admin,
                "permissions": sorted(service.effective_permission_codes()),
                "organizations": sorted(service.accessible_organization_ids()),
                "warehouses": sorted(service.accessible_warehouse_ids()),
                "roles": [
                    {
                        "role": assignment.role.code,
                        "name": assignment.role.name,
                        "level": assignment.role.level,
                        "organization_id": assignment.organization_id,
                        "warehouse_id": assignment.warehouse_id,
                        "scope": assignment.scope_label,
                        "expires_at": assignment.expires_at,
                    }
                    for assignment in assignments
                ],
                "highest_level": service.highest_level(),
            }
        )

    def post(self, request):
        """Diagnostic check: "can I do X in scope Y?" (never a security boundary)."""
        codename = request.data.get("permission")
        if not codename:
            raise ValidationError({"permission": ["This field is required."]})
        organization = None
        warehouse = None
        if request.data.get("organization"):
            organization = Organization.objects.filter(pk=request.data["organization"]).first()
        if request.data.get("warehouse"):
            warehouse = Warehouse.objects.filter(pk=request.data["warehouse"]).first()
        service = authorization_for(request)
        granted = service.has_permission(codename, organization=organization, warehouse=warehouse)
        return Response(
            {
                "permission": codename,
                "granted": granted,
                "organization": getattr(organization, "id", None),
                "warehouse": getattr(warehouse, "id", None),
            }
        )
