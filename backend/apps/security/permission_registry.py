"""Canonical permission registry.

Permissions are **code**, not user data: this module is the single source of
truth, and ``manage.py sync_rbac`` (plus the data migration) projects it into
the database where roles reference it.

Naming: ``<module>.<action>`` — the codename is what appears in API
documentation, role editors and the ``require_permission`` decorator, e.g.
``inventory.adjust``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    codename: str
    name: str
    module: str
    description: str = ""
    #: Higher-risk permissions: assignment requires an explicit elevated role.
    sensitive: bool = False


def _perm(codename: str, name: str, description: str = "", sensitive: bool = False):
    module = codename.split(".", 1)[0]
    return PermissionDefinition(
        codename=codename, name=name, module=module, description=description, sensitive=sensitive
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
PERMISSIONS: tuple[PermissionDefinition, ...] = (
    # --- Platform / tenancy ------------------------------------------------
    _perm("organization.view", "View organizations", "See organizations you belong to"),
    _perm("organization.manage", "Manage organizations", "Create and edit organizations", True),
    _perm("branch.view", "View branches", "See branches inside your organizations"),
    _perm("branch.manage", "Manage branches", "Create and edit branches", True),
    # --- Warehouses --------------------------------------------------------
    _perm("warehouse.view", "View warehouses", "See warehouses you are granted access to"),
    _perm(
        "warehouse.manage",
        "Manage warehouses",
        "Create and configure warehouses, locations and policies",
        True,
    ),
    # --- Inventory ---------------------------------------------------------
    _perm("inventory.view", "View inventory", "See stock levels and movements"),
    _perm("inventory.create", "Create inventory records", "Receive stock into the ledger"),
    _perm("inventory.adjust", "Adjust inventory", "Post stock adjustments (needs approval)"),
    _perm(
        "inventory.approve_adjustment",
        "Approve inventory adjustments",
        "Approve adjustments posted by operators",
        True,
    ),
    # --- Products & pricing ------------------------------------------------
    _perm("product.view", "View products", "See the product/SKU catalogue"),
    _perm("product.manage", "Manage products", "Create and edit products, variants and UoM"),
    _perm("pricing.view", "View pricing", "See price lists and cost data"),
    _perm("pricing.manage", "Manage pricing", "Create and edit price lists and rules", True),
    # --- Procurement -------------------------------------------------------
    _perm("supplier.view", "View suppliers", "See vendor master data"),
    _perm("supplier.manage", "Manage suppliers", "Create and edit suppliers"),
    _perm("purchase_order.view", "View purchase orders", "See requisitions and purchase orders"),
    _perm("purchase_order.create", "Create purchase orders", "Raise requisitions and POs"),
    _perm(
        "purchase_order.approve",
        "Approve purchase orders",
        "Approve POs above the requester's authority",
        True,
    ),
    _perm("receiving.view", "View receiving", "See inbound shipments and receipts"),
    _perm("receiving.manage", "Manage receiving", "Book inbound receipts and discrepancies"),
    _perm("putaway.view", "View putaway", "See putaway tasks and rules"),
    _perm("putaway.manage", "Manage putaway", "Execute putaway and configure strategies"),
    # --- Transfers ---------------------------------------------------------
    _perm("transfer.create", "Create transfers", "Raise stock transfer requests"),
    _perm("transfer.approve", "Approve transfers", "Approve transfer requests", True),
    _perm("transfer.dispatch", "Dispatch transfers", "Pick, pack and dispatch transfers"),
    _perm("transfer.receive", "Receive transfers", "Receive transfers at the destination"),
    # --- Orders & fulfilment ----------------------------------------------
    _perm("order.view", "View orders", "See sales/outbound orders"),
    _perm("order.create", "Create orders", "Capture orders"),
    _perm("order.manage", "Manage orders", "Edit, allocate and cancel orders"),
    _perm("fulfillment.view", "View fulfillment", "See pick/pack/ship work"),
    _perm("fulfillment.execute", "Execute fulfillment", "Pick, pack and ship orders"),
    _perm("replenishment.view", "View replenishment", "See replenishment suggestions"),
    _perm("replenishment.manage", "Manage replenishment", "Configure and approve replenishment"),
    _perm("stock_count.view", "View stock counts", "See cycle counts and variances"),
    _perm("stock_count.manage", "Manage stock counts", "Run counts and post variances"),
    _perm("return.view", "View returns", "See returns and RMAs"),
    _perm("return.manage", "Manage returns", "Authorise returns and dispositions"),
    # --- Reporting ---------------------------------------------------------
    _perm("report.view", "View reports", "Open operational and analytical reports"),
    _perm(
        "report.export",
        "Export reports",
        "Download report data (CSV/XLSX) — data-egress control",
        sensitive=True,
    ),
    # --- Identity & access -------------------------------------------------
    _perm("user.view", "View users", "See user accounts in scope"),
    _perm("user.manage", "Manage users", "Create, edit, activate and deactivate users", True),
    _perm("role.view", "View roles", "See roles and their permissions"),
    _perm("role.manage", "Manage roles", "Create roles and change their permissions", True),
    _perm(
        "assignment.manage",
        "Manage role assignments",
        "Grant and revoke roles for users (organization/warehouse scoped)",
        True,
    ),
    _perm("session.view", "View sessions", "See active sessions for users in scope"),
    _perm("session.revoke", "Revoke sessions", "Force logout for users in scope", True),
    # --- Governance --------------------------------------------------------
    _perm("audit.view", "View audit trail", "Read the audit and login-attempt ledger"),
    _perm("configuration.view", "View configuration", "See settings and feature flags"),
    _perm("configuration.manage", "Manage configuration", "Change settings and feature flags", True),
    _perm("integration.view", "View integrations", "See connectors and sync logs"),
    _perm("integration.manage", "Manage integrations", "Configure connectors and API keys", True),
    _perm("barcode.manage", "Manage barcode rules", "Configure symbologies and label templates"),
    _perm("rfid.manage", "Manage RFID", "Configure EPC rules and readers"),
    _perm("notification.manage", "Manage notifications", "Configure channels and subscriptions"),
    _perm("supplier_portal.use", "Use supplier portal", "Supplier-facing, restricted API surface"),
)

PERMISSIONS_BY_CODE: dict[str, PermissionDefinition] = {p.codename: p for p in PERMISSIONS}

ALL_PERMISSION_CODES: tuple[str, ...] = tuple(p.codename for p in PERMISSIONS)

PERMISSION_MODULES: tuple[str, ...] = tuple(dict.fromkeys(p.module for p in PERMISSIONS))


def permission_codes_for_modules(*modules: str) -> list[str]:
    """All permission codenames belonging to the given modules."""
    wanted = set(modules)
    return [p.codename for p in PERMISSIONS if p.module in wanted]


def is_registered(codename: str) -> bool:
    return codename in PERMISSIONS_BY_CODE
