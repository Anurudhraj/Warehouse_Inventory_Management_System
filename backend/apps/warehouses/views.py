"""Warehouse API (foundation).

The queryset is always restricted to the warehouses the caller is entitled to:
either because an organization-wide assignment covers them, or because the
caller holds a warehouse-scoped assignment for that warehouse. Requests naming
a warehouse outside that set return ``404`` — the caller cannot even learn it
exists.
"""
from __future__ import annotations

import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.pagination import StandardPagination
from apps.security.authorization import authorization_for
from apps.security.permissions import HasScopedPermission, IsAuthenticatedAndActive
from apps.warehouses.models import Warehouse
from apps.warehouses.serializers import WarehouseSerializer, WarehouseSummarySerializer

logger = logging.getLogger("apps.warehouses.api")


class WarehouseViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticatedAndActive, HasScopedPermission]
    pagination_class = StandardPagination
    search_fields = ["name", "code", "city"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    def get_queryset(self):
        service = authorization_for(self.request)
        qs = Warehouse.objects.select_related("branch", "branch__organization", "manager")

        # Entitlement first, filters second: a query parameter can only ever
        # narrow what the caller is allowed to see.
        if not service.is_platform_admin:
            qs = qs.filter(id__in=service.accessible_warehouse_ids())

        organization_id = self.request.query_params.get("organization")
        if organization_id:
            qs = qs.filter(branch__organization_id=organization_id)

        warehouse_id = self.request.query_params.get("warehouse") or self.request.query_params.get(
            "warehouse_id"
        )
        if warehouse_id:
            try:
                qs = qs.filter(pk=int(warehouse_id))
            except (TypeError, ValueError):
                qs = qs.none()

        return qs.order_by("code")

    def get_serializer_class(self):
        if self.action == "list":
            return WarehouseSummarySerializer
        return WarehouseSerializer

    @property
    def required_permissions(self) -> tuple[str, ...]:
        if self.action in ("list", "retrieve", "me"):
            return ("warehouse.view",)
        return ("warehouse.manage",)

    def perform_create(self, serializer):
        branch = serializer.validated_data.get("branch")
        service = authorization_for(self.request)
        service.ensure_organization_access(branch.organization)
        service.ensure_permission("warehouse.manage", organization=branch.organization)
        warehouse = serializer.save()
        logger.info(
            "Warehouse created (id=%s, organization=%s, by=%s)",
            warehouse.pk,
            branch.organization_id,
            self.request.user.pk,
        )

    def perform_update(self, serializer):
        warehouse = self.get_object()
        service = authorization_for(self.request)
        service.ensure_organization_access(warehouse.organization)
        service.ensure_permission("warehouse.manage", organization=warehouse.organization)
        serializer.save()

    def perform_destroy(self, instance):
        raise ValidationError(
            {
                "detail": (
                    "Warehouses are deactivated, never deleted: stock history and role "
                    "assignments reference them. Use the deactivate action."
                )
            }
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        warehouse = self.get_object()
        service = authorization_for(request)
        service.ensure_organization_access(warehouse.organization)
        service.ensure_permission("warehouse.manage", organization=warehouse.organization)
        warehouse.is_active = False
        warehouse.save(update_fields=["is_active"])
        return Response(WarehouseSerializer(warehouse).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        warehouse = self.get_object()
        service = authorization_for(request)
        service.ensure_organization_access(warehouse.organization)
        service.ensure_permission("warehouse.manage", organization=warehouse.organization)
        warehouse.is_active = True
        warehouse.save(update_fields=["is_active"])
        return Response(WarehouseSerializer(warehouse).data)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Warehouses the caller may access (scope introspection for the UI)."""
        service = authorization_for(request)
        ids = service.accessible_warehouse_ids()
        qs = Warehouse.objects.filter(id__in=ids).select_related("branch")
        return Response(
            {
                "count": len(ids),
                "warehouse_ids": sorted(ids),
                "results": WarehouseSummarySerializer(qs, many=True).data,
            }
        )
