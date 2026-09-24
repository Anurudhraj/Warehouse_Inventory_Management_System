"""``manage.py sync_rbac`` — project the code-defined RBAC registry into the DB.

Idempotent: run it after deploying changes to
``apps/security/permission_registry.py`` or ``role_registry.py``.

    python manage.py sync_rbac
    python manage.py sync_rbac --check   # exit 1 when the DB is out of sync
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.security.models import Permission, Role
from apps.security.permission_registry import PERMISSIONS
from apps.security.role_registry import SYSTEM_ROLES
from apps.security.services import PermissionService


class Command(BaseCommand):
    help = "Synchronise permissions and system roles with the code registry."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Report drift without writing anything (exits non-zero when out of sync).",
        )

    def handle(self, *args, **options):
        if options["check"]:
            problems = self._check_drift()
            if problems:
                raise CommandError("RBAC registry is out of sync:\n  - " + "\n  - ".join(problems))
            self.stdout.write(self.style.SUCCESS("RBAC registry is in sync."))
            return

        result = PermissionService.sync_registry()
        self.stdout.write(
            self.style.SUCCESS(
                "RBAC synced: "
                f"{result['permissions_created']} permissions created, "
                f"{result['permissions_updated']} updated, "
                f"{result['permissions_removed']} removed; "
                f"{result['roles_created']} roles created, "
                f"{result['roles_updated']} updated."
            )
        )

    def _check_drift(self) -> list[str]:
        problems: list[str] = []

        known = {p.codename for p in PERMISSIONS}
        stored = set(Permission.objects.values_list("codename", flat=True))
        for missing in sorted(known - stored):
            problems.append(f"permission missing from database: {missing}")
        for extra in sorted(stored - known):
            problems.append(f"permission in database but not in the registry: {extra}")

        for definition in SYSTEM_ROLES:
            role = Role.objects.filter(organization__isnull=True, code=definition.code).first()
            if role is None:
                problems.append(f"system role missing: {definition.code}")
                continue
            if role.level != definition.level:
                problems.append(
                    f"role {definition.code}: level {role.level} != registry {definition.level}"
                )
            actual = set(role.permissions.values_list("codename", flat=True))
            expected = set(definition.permissions)
            for codename in sorted(expected - actual):
                problems.append(f"role {definition.code} is missing permission {codename}")
            for codename in sorted(actual - expected):
                problems.append(f"role {definition.code} has unexpected permission {codename}")
        return problems
