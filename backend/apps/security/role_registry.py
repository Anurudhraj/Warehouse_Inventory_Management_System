"""Canonical role definitions from the specification.

Ten roles are defined system-wide. ``level`` expresses the *authority rank*
used for escalation checks (a user may never grant a role whose level is
higher than their own, and never grant permissions they do not hold).

Roles are seeded by ``manage.py sync_rbac`` and a data migration; organizations
may clone a system role into their own space later, but the system set is
immutable from the API.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.security.permission_registry import ALL_PERMISSION_CODES, permission_codes_for_modules


@dataclass(frozen=True)
class RoleDefinition:
    code: str
    name: str
    description: str
    level: int
    permissions: tuple[str, ...] = field(default_factory=tuple)
    #: True only for platform-scoped roles (assigned outside any organization).
    platform: bool = False


def _codes(*codenames: str) -> tuple[str, ...]:
    return tuple(codenames)


# Read-only reporting surface shared by most operational roles.
_REPORT_READ = _codes("report.view", "report.export")

SYSTEM_ROLES: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        code="super_admin",
        name="Super Admin",
        description=(
            "Platform administrator. Unrestricted access across every "
            "organization, warehouse and module. Reserved for platform staff."
        ),
        level=100,
        platform=True,
        permissions=ALL_PERMISSION_CODES,
    ),
    RoleDefinition(
        code="warehouse_manager",
        name="Warehouse Manager",
        description=(
            "Runs one or more warehouses end to end: inbound, inventory, "
            "transfers, counts, fulfilment and the teams operating them."
        ),
        level=80,
        permissions=_codes(
            "organization.view",
            "branch.view",
            "warehouse.view",
            "warehouse.manage",
            "inventory.view",
            "inventory.create",
            "inventory.adjust",
            "inventory.approve_adjustment",
            "product.view",
            "pricing.view",
            "supplier.view",
            "purchase_order.view",
            "receiving.view",
            "receiving.manage",
            "putaway.view",
            "putaway.manage",
            "transfer.create",
            "transfer.approve",
            "transfer.dispatch",
            "transfer.receive",
            "order.view",
            "fulfillment.view",
            "fulfillment.execute",
            "replenishment.view",
            "replenishment.manage",
            "stock_count.view",
            "stock_count.manage",
            "return.view",
            "return.manage",
            "report.view",
            "report.export",
            "user.view",
            "session.view",
        ),
    ),
    RoleDefinition(
        code="inventory_controller",
        name="Inventory Controller",
        description=(
            "Owns inventory accuracy: adjustments and approvals, cycle counts, "
            "replenishment and stock movement control."
        ),
        level=70,
        permissions=_codes(
            "organization.view",
            "warehouse.view",
            "inventory.view",
            "inventory.create",
            "inventory.adjust",
            "inventory.approve_adjustment",
            "product.view",
            "pricing.view",
            "transfer.create",
            "transfer.approve",
            "transfer.receive",
            "replenishment.view",
            "replenishment.manage",
            "stock_count.view",
            "stock_count.manage",
            "putaway.view",
            "report.view",
            "report.export",
        ),
    ),
    RoleDefinition(
        code="procurement_manager",
        name="Procurement Manager",
        description="Supplier management, purchase orders and approvals, inbound planning.",
        level=70,
        permissions=_codes(
            "organization.view",
            "warehouse.view",
            "supplier.view",
            "supplier.manage",
            "purchase_order.view",
            "purchase_order.create",
            "purchase_order.approve",
            "receiving.view",
            "receiving.manage",
            "putaway.view",
            "product.view",
            "pricing.view",
            "pricing.manage",
            "inventory.view",
            "replenishment.view",
            "report.view",
            "report.export",
        ),
    ),
    RoleDefinition(
        code="dispatch_coordinator",
        name="Dispatch Coordinator",
        description="Outbound execution: allocation, picking/packing, dispatch and returns intake.",
        level=60,
        permissions=_codes(
            "warehouse.view",
            "inventory.view",
            "order.view",
            "order.manage",
            "fulfillment.view",
            "fulfillment.execute",
            "transfer.create",
            "transfer.dispatch",
            "transfer.receive",
            "return.view",
            "return.manage",
            "product.view",
            "report.view",
        ),
    ),
    RoleDefinition(
        code="warehouse_operator",
        name="Warehouse Operator",
        description=(
            "Shop-floor execution in assigned warehouses: receiving, putaway, "
            "picking, transfers and counts. Cannot approve or adjust."
        ),
        level=40,
        permissions=_codes(
            "warehouse.view",
            "inventory.view",
            "inventory.create",
            "product.view",
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
            "stock_count.view",
            "stock_count.manage",
            "return.view",
        ),
    ),
    RoleDefinition(
        code="sales_order_user",
        name="Sales / Order User",
        description="Takes and manages customer orders, monitors fulfilment progress.",
        level=50,
        permissions=_codes(
            "organization.view",
            "warehouse.view",
            "product.view",
            "pricing.view",
            "order.view",
            "order.create",
            "order.manage",
            "fulfillment.view",
            "inventory.view",
            "return.view",
            "return.manage",
            "report.view",
        ),
    ),
    RoleDefinition(
        code="finance_accounts",
        name="Finance / Accounts",
        description=(
            "Financial oversight: pricing and cost data, purchase order approvals, "
            "valuation reporting and report exports."
        ),
        level=75,
        permissions=_codes(
            "organization.view",
            "branch.view",
            "warehouse.view",
            "pricing.view",
            "pricing.manage",
            "purchase_order.view",
            "purchase_order.approve",
            "inventory.view",
            "supplier.view",
            "order.view",
            "report.view",
            "report.export",
            "audit.view",
            "configuration.view",
        ),
    ),
    RoleDefinition(
        code="management_viewer",
        name="Management Viewer",
        description="Read-only executive visibility across the organization.",
        level=55,
        permissions=_codes(
            "organization.view",
            "branch.view",
            "warehouse.view",
            "inventory.view",
            "product.view",
            "pricing.view",
            "supplier.view",
            "purchase_order.view",
            "receiving.view",
            "putaway.view",
            "order.view",
            "fulfillment.view",
            "replenishment.view",
            "stock_count.view",
            "return.view",
            "report.view",
            "report.export",
            "audit.view",
        ),
    ),
    RoleDefinition(
        code="supplier_portal_user",
        name="Supplier Portal User",
        description=(
            "External supplier identity. Restricted to its own supplier records, "
            "purchase orders addressed to it and ASN submission."
        ),
        level=20,
        permissions=_codes(
            "supplier_portal.use",
            "purchase_order.view",
            "receiving.view",
            "product.view",
        ),
    ),
)

SYSTEM_ROLES_BY_CODE: dict[str, RoleDefinition] = {r.code: r for r in SYSTEM_ROLES}

#: Roles that may only ever be granted outside an organization (platform scope).
PLATFORM_ROLE_CODES: frozenset[str] = frozenset(r.code for r in SYSTEM_ROLES if r.platform)

#: Maximum authority rank a non-platform administrator may grant (see rbac.md).
MAX_DELEGABLE_LEVEL = 90


def role_definition(code: str) -> RoleDefinition | None:
    return SYSTEM_ROLES_BY_CODE.get(code)


def module_permissions_for_role(code: str) -> dict[str, list[str]]:
    """Role permissions grouped by module — used by the role editor UI."""
    definition = SYSTEM_ROLES_BY_CODE.get(code)
    if not definition:
        return {}
    grouped: dict[str, list[str]] = {}
    for codename in definition.permissions:
        grouped.setdefault(codename.split(".", 1)[0], []).append(codename)
    return grouped


__all__ = [
    "MAX_DELEGABLE_LEVEL",
    "PLATFORM_ROLE_CODES",
    "SYSTEM_ROLES",
    "SYSTEM_ROLES_BY_CODE",
    "RoleDefinition",
    "module_permissions_for_role",
    "permission_codes_for_modules",
    "role_definition",
]
