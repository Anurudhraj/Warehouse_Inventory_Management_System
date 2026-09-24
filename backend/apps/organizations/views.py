"""Organizations & branches API.

Scoping rules:

* a user only ever sees organizations they hold an assignment in;
* ``organization.manage`` is required to create/update an organization and is
  at minimum an organization-scoped authority (platform admins hold it in
  every organization);
* branches are scoped the same way — cross-organization access returns 404.
"""
from __future__ import annotations

import logging

from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.core.pagination import StandardPagination
from apps.organizations.models import Branch, Organization
from apps.organizations.serializers import (
    BranchSerializer,
    BranchSummarySerializer,
    OrganizationSerializer,
    OrganizationSummarySerializer,
)
from apps.security.authorization import authorization_for
from apps.security.permissions import HasScopedPermission, IsAuthenticatedAndActive

logger = logging.getLogger("apps.organizations.api")


class OrganizationViewSet(viewsets.ModelViewSet):
    """Tenant administration."""

    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticatedAndActive, HasScopedPermission]
    pagination_class = StandardPagination
    search_fields = ["name", "code", "legal_name", "city"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        service = authorization_for(self.request)
        qs = (
            Organization.objects.annotate(
                branch_total=Count("branches", distinct=True),
                user_total=Count("users", distinct=True),
            )
            .prefetch_related("branches")
            .order_by("name")
        )
        if service.is_platform_admin:
            return qs
        return qs.filter(id__in=service.accessible_organization_ids())

    def get_serializer_class(self):
        if self.action == "list":
            return OrganizationSummarySerializer
        return OrganizationSerializer

    @property
    def required_permissions(self) -> tuple[str, ...]:
        if self.action in ("list", "retrieve", "branches", "warehouses"):
            return ("organization.view",)
        return ("organization.manage",)

    def perform_create(self, serializer):
        # Only platform administrators create tenants: a new organization has
        # no scope to check against yet, and tenant creation is a platform act.
        if not authorization_for(self.request).is_platform_admin:
            raise PermissionDenied("Only platform administrators can create organizations.")
        organization = serializer.save()
        logger.info(
            "Organization created (id=%s, by=%s)", organization.pk, self.request.user.pk
        )

    def perform_update(self, serializer):
        organization = self.get_object()
        service = authorization_for(self.request)
        service.ensure_organization_access(organization)
        service.ensure_permission("organization.manage", organization=organization)
        serializer.save()

    def perform_destroy(self, instance):
        raise ValidationError(
            {
                "detail": (
                    "Organizations are archived, never deleted (referential integrity and "
                    "audit requirements). Set status to 'archived' instead."
                )
            }
        )

    @action(detail=True, methods=["get"])
    def branches(self, request, pk=None):
        organization = self.get_object()
        authorization_for(request).ensure_organization_access(organization)
        qs = organization.branches.select_related("manager").annotate(
            warehouse_total=Count("warehouses", distinct=True)
        )
        page = self.paginate_queryset(qs)
        serializer = BranchSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def warehouses(self, request, pk=None):
        organization = self.get_object()
        service = authorization_for(request)
        service.ensure_organization_access(organization)

        from apps.warehouses.models import Warehouse
        from apps.warehouses.serializers import WarehouseSerializer

        qs = Warehouse.objects.filter(
            branch__organization=organization, id__in=service.accessible_warehouse_ids(organization)
        ).select_related("branch", "manager")
        page = self.paginate_queryset(qs)
        serializer = WarehouseSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class BranchViewSet(viewsets.ModelViewSet):
    """Branch (business location) administration."""

    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticatedAndActive, HasScopedPermission]
    pagination_class = StandardPagination
    search_fields = ["name", "code", "city"]
    ordering_fields = ["name", "code", "created_at"]
    ordering = ["organization__name", "name"]

    def get_queryset(self):
        service = authorization_for(self.request)
        qs = (
            Branch.objects.select_related("organization", "manager")
            .annotate(warehouse_total=Count("warehouses", distinct=True))
            .order_by("organization__name", "name")
        )
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            qs = qs.filter(organization_id=organization_id)
        if service.is_platform_admin:
            return qs
        return qs.filter(organization_id__in=service.accessible_organization_ids())

    def get_serializer_class(self):
        if self.action == "list":
            return BranchSummarySerializer
        return BranchSerializer

    @property
    def required_permissions(self) -> tuple[str, ...]:
        if self.action in ("list", "retrieve"):
            return ("branch.view",)
        return ("branch.manage",)

    def perform_create(self, serializer):
        organization = serializer.validated_data.get("organization")
        service = authorization_for(self.request)
        service.ensure_organization_access(organization)
        service.ensure_permission("branch.manage", organization=organization)
        branch = serializer.save()
        logger.info("Branch created (id=%s, by=%s)", branch.pk, self.request.user.pk)

    def perform_update(self, serializer):
        branch = self.get_object()
        service = authorization_for(self.request)
        service.ensure_organization_access(branch.organization)
        service.ensure_permission("branch.manage", organization=branch.organization)
        serializer.save()

    def perform_destroy(self, instance):
        if instance.warehouses.exists():
            raise ValidationError(
                {
                    "detail": (
                        "This branch still has warehouses. Deactivate or move them first."
                    )
                }
            )
        service = authorization_for(self.request)
        try:
            service.ensure_organization_access(instance.organization)
        except Exception as exc:
            raise NotFound("Not found.") from exc
        instance.delete()

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        branch = self.get_object()
        service = authorization_for(request)
        service.ensure_organization_access(branch.organization)
        service.ensure_permission("branch.manage", organization=branch.organization)
        branch.is_active = False
        branch.save(update_fields=["is_active"])
        return Response(BranchSerializer(branch).data, status=status.HTTP_200_OK)
