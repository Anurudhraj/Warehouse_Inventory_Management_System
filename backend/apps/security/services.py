"""RBAC service layer — the only place roles and assignments are mutated.

Escalation defences live here (and are re-checked by the authorization engine):

* you may only grant a role you could hold yourself, at or below your level;
* you may only put permissions into a role if you hold them yourself;
* platform roles are grantable by platform administrators only;
* assignments are scope-checked against the target user, organization and
  warehouse — cross-organization grants are impossible;
* every mutation is written to the audit ledger.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.security.authorization import AuthorizationService
from apps.security.models import Permission, Role, RoleAssignment
from apps.security.role_registry import PLATFORM_ROLE_CODES

logger = logging.getLogger("apps.security.audit")


class RoleService:
    """Role and assignment management with escalation guards."""

    # -- roles -------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def create_role(
        *,
        actor,
        organization,
        code: str,
        name: str,
        description: str = "",
        level: int = 40,
        permission_codes: list[str] | None = None,
    ) -> Role:
        service = AuthorizationService(actor)
        service.ensure_permission("role.manage", organization=organization)
        service.ensure_organization_access(organization)

        if level > service.highest_level(organization=organization):
            raise PermissionDenied("You cannot create a role with higher authority than your own.")
        if Role.objects.filter(organization=organization, code=code).exists():
            raise ValidationError({"code": ["A role with this code already exists."]})

        role = Role.objects.create(
            organization=organization,
            code=code,
            name=name,
            description=description,
            level=level,
            is_system=False,
            is_platform=False,
        )
        if permission_codes:
            RoleService.set_permissions(
                actor=actor, role=role, permission_codes=permission_codes
            )
        logger.info(
            "Role created (role=%s, organization=%s, by=%s)",
            role.code,
            organization.pk,
            getattr(actor, "pk", None),
        )
        return role

    @staticmethod
    @transaction.atomic
    def set_permissions(*, actor, role: Role, permission_codes: list[str]) -> Role:
        service = AuthorizationService(actor)
        organization = role.organization
        service.ensure_permission("role.manage", organization=organization)
        if organization is not None:
            service.ensure_organization_access(organization)

        if role.is_system:
            raise PermissionDenied("System role permissions are defined by the platform.")
        if role.level > service.highest_level(organization=organization):
            raise PermissionDenied("You cannot modify a role with higher authority than your own.")

        # Privilege-escalation guard: you cannot grant what you do not hold.
        if not service.is_platform_admin:
            missing = [
                code
                for code in permission_codes
                if not service.has_permission(code, organization=organization)
            ]
            if missing:
                raise PermissionDenied(
                    "You cannot grant permissions you do not hold: " + ", ".join(sorted(missing))
                )

        permissions = list(Permission.objects.filter(codename__in=permission_codes))
        role.permissions.set(permissions)
        logger.info(
            "Role permissions updated (role=%s, count=%s, by=%s)",
            role.code,
            len(permissions),
            getattr(actor, "pk", None),
        )
        return role

    # -- assignments --------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def grant_role(
        *,
        actor,
        user,
        role: Role,
        organization=None,
        warehouse=None,
        expires_at=None,
        note: str = "",
    ) -> RoleAssignment:
        service = AuthorizationService(actor)

        if role.organization_id is not None and organization is None:
            organization = role.organization

        # Scope sanity: warehouse must live in the organization.
        if warehouse is not None:
            if organization is None:
                organization = warehouse.organization
            elif warehouse.organization_id != organization.id:
                raise ValidationError(
                    {"warehouse": ["The warehouse does not belong to the given organization."]}
                )

        if not service.is_platform_admin:
            if organization is None:
                raise PermissionDenied(
                    "Platform-scoped grants can only be created by platform administrators."
                )
            service.ensure_organization_access(organization)
            if warehouse is not None:
                service.ensure_warehouse_access(warehouse)
            # The target user must be visible/manageable by the actor.
            if user.organization_id and not service.can_access_organization(user.organization):
                raise ValidationError({"user": ["Unknown user."]})

        # Escalation guard: may the actor hand out this role in this scope?
        allowed, reason = service.can_grant_role(role, organization=organization, warehouse=warehouse)
        if not allowed:
            raise PermissionDenied(reason)

        if role.code in PLATFORM_ROLE_CODES and not service.is_platform_admin:
            raise PermissionDenied("Platform roles can only be granted by platform administrators.")

        if expires_at and expires_at <= timezone.now():
            raise ValidationError({"expires_at": ["Expiry must be in the future."]})

        assignment, created = RoleAssignment.objects.get_or_create(
            user=user,
            role=role,
            organization=organization,
            warehouse=warehouse,
            defaults={
                "granted_by": actor if getattr(actor, "pk", None) else None,
                "expires_at": expires_at,
                "note": note[:255],
                "is_active": True,
            },
        )
        if not created:
            assignment.is_active = True
            assignment.is_suspended = False
            assignment.expires_at = expires_at
            assignment.note = note[:255]
            assignment.save(
                update_fields=["is_active", "is_suspended", "expires_at", "note"]
            )

        logger.info(
            "Role granted (user=%s, role=%s, organization=%s, warehouse=%s, by=%s)",
            user.pk,
            role.code,
            getattr(organization, "pk", None),
            getattr(warehouse, "pk", None),
            getattr(actor, "pk", None),
        )
        return assignment

    @staticmethod
    @transaction.atomic
    def revoke_assignment(*, actor, assignment: RoleAssignment) -> None:
        service = AuthorizationService(actor)
        if not service.is_platform_admin:
            if assignment.organization_id is None:
                raise PermissionDenied(
                    "Only platform administrators can revoke platform-scoped grants."
                )
            service.ensure_organization_access(assignment.organization)
            service.ensure_permission(
                "assignment.manage",
                organization=assignment.organization,
                warehouse=assignment.warehouse,
            )
        assignment.is_active = False
        assignment.is_suspended = False  # an explicit revocation is final
        assignment.save(update_fields=["is_active", "is_suspended"])
        logger.info(
            "Role revoked (user=%s, role=%s, by=%s)",
            assignment.user_id,
            assignment.role.code,
            getattr(actor, "pk", None),
        )

    @staticmethod
    def accessible_roles_for(user, organization=None):
        """Roles whose permissions the user could grant (UI helper)."""
        service = AuthorizationService(user)
        return [
            role
            for role in Role.objects.filter(is_active=True).order_by("-level", "name")
            if service.can_grant_role(role, organization=organization)[0]
        ]


class PermissionService:
    """Registry projection (used by migrations and ``sync_rbac``)."""

    @staticmethod
    def sync_registry() -> dict:
        """Create/update permission rows and system roles from the registries."""
        from apps.security.permission_registry import PERMISSIONS
        from apps.security.role_registry import SYSTEM_ROLES

        created = updated = 0
        for definition in PERMISSIONS:
            _, was_created = Permission.objects.update_or_create(
                codename=definition.codename,
                defaults={
                    "name": definition.name,
                    "module": definition.module,
                    "description": definition.description,
                    "is_sensitive": definition.sensitive,
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        stale = Permission.objects.exclude(codename__in=[p.codename for p in PERMISSIONS])
        removed = stale.count()
        stale.delete()

        role_created = role_updated = 0
        for definition in SYSTEM_ROLES:
            role, was_created = Role.objects.update_or_create(
                organization=None,
                code=definition.code,
                defaults={
                    "name": definition.name,
                    "description": definition.description,
                    "level": definition.level,
                    "is_system": True,
                    "is_platform": definition.platform,
                    "is_active": True,
                },
            )
            role.permissions.set(Permission.objects.filter(codename__in=definition.permissions))
            role_created += int(was_created)
            role_updated += int(not was_created)

        return {
            "permissions_created": created,
            "permissions_updated": updated,
            "permissions_removed": removed,
            "roles_created": role_created,
            "roles_updated": role_updated,
        }
