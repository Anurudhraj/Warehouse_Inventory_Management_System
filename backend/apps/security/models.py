"""Authorization models: permissions, roles and scoped role assignments.

The engine that evaluates these models lives in ``apps/security/authorization.py``
and is documented in ``docs/rbac.md``.

Scoping model
-------------
A :class:`RoleAssignment` grants a role to a user within a scope:

* ``organization`` — the tenant the grant belongs to (``NULL`` only for
  platform roles such as *Super Admin*).
* ``warehouse`` — optional further narrowing. ``NULL`` means "every warehouse
  in the organization"; a value means "this warehouse only".

Every permission check therefore asks: *does this user hold a role containing
this permission within a scope that covers the requested organization and
warehouse?* Nothing outside that scope is ever visible (cross-organization and
cross-warehouse access are denied by construction).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Permission(models.Model):
    """A granular capability, e.g. ``inventory.adjust``.

    Rows are projected from ``apps/security/permission_registry.py`` — the
    registry is authoritative, the table exists so roles can reference
    permissions relationally.
    """

    codename = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=50, db_index=True)
    description = models.CharField(max_length=255, blank=True, default="")
    is_sensitive = models.BooleanField(
        default=False, help_text=_("High-risk permission; assignment is audited.")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("permission")
        verbose_name_plural = _("permissions")
        ordering = ["module", "codename"]

    def __str__(self) -> str:
        return self.codename


class Role(models.Model):
    """A named bundle of permissions.

    ``organization`` is ``NULL`` for the system roles defined in the
    specification; organizations may later define their own roles.
    """

    code = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
        help_text=_("Empty for system-wide roles."),
    )
    level = models.PositiveSmallIntegerField(
        default=50,
        help_text=_("Authority rank (0-100). Higher ranks may manage lower ones."),
    )
    is_system = models.BooleanField(
        default=False, help_text=_("Seeded from the specification; cannot be deleted.")
    )
    is_platform = models.BooleanField(
        default=False, help_text=_("Only grantable outside an organization (platform staff).")
    )
    is_active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ["-level", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="unique_role_code_per_organization"
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(organization__isnull=True),
                name="unique_system_role_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    @property
    def permission_codes(self) -> set[str]:
        return set(self.permissions.values_list("codename", flat=True))


class RoleAssignment(models.Model):
    """Grants a role to a user inside an organization / warehouse scope."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_assignments",
        help_text=_("Empty only for platform-scoped roles."),
    )
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_assignments",
        help_text=_("Empty = all warehouses in the organization."),
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="granted_role_assignments",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_suspended = models.BooleanField(
        default=False,
        help_text=_(
            "Grant paused because the account was deactivated. Reactivating the "
            "account restores exactly this grant; deliberate revocation does not."
        ),
    )
    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("role assignment")
        verbose_name_plural = _("role assignments")
        ordering = ["-granted_at"]
        indexes = [
            models.Index(fields=["user", "organization"]),
            models.Index(fields=["user", "warehouse"]),
        ]
        constraints = [
            # PostgreSQL treats NULLs as distinct, so one 4-column constraint
            # would allow duplicate organization-wide grants. Two partial
            # constraints close that gap (see apps/security/tests).
            models.UniqueConstraint(
                fields=["user", "role", "organization"],
                condition=models.Q(warehouse__isnull=True),
                name="unique_assignment_org_scope",
            ),
            models.UniqueConstraint(
                fields=["user", "role", "organization", "warehouse"],
                condition=models.Q(warehouse__isnull=False),
                name="unique_assignment_warehouse_scope",
            ),
        ]

    def __str__(self) -> str:
        scope = self.organization_id or "platform"
        if self.warehouse_id:
            scope = f"{scope}/warehouse:{self.warehouse_id}"
        return f"{self.user_id} → {self.role.code} @ {scope}"

    @property
    def is_effective(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return self.role.is_active

    @property
    def scope_label(self) -> str:
        if self.organization_id is None:
            return "Platform"
        if self.warehouse_id is None:
            return f"{self.organization} (all warehouses)"
        return f"{self.warehouse}"
