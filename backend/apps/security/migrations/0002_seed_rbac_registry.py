"""Seed permissions and system roles from the code registries.

Keeping the seed in a migration makes the RBAC baseline deterministic: every
environment (including test databases) starts with exactly the permissions and
roles defined in code. Later changes are applied with ``manage.py sync_rbac``,
which is idempotent — the migration simply calls the same projection.
"""
from django.db import migrations


def seed(apps, schema_editor):
    Permission = apps.get_model("security", "Permission")
    Role = apps.get_model("security", "Role")

    from apps.security.permission_registry import PERMISSIONS
    from apps.security.role_registry import SYSTEM_ROLES

    for definition in PERMISSIONS:
        Permission.objects.update_or_create(
            codename=definition.codename,
            defaults={
                "name": definition.name,
                "module": definition.module,
                "description": definition.description,
                "is_sensitive": definition.sensitive,
            },
        )

    for definition in SYSTEM_ROLES:
        role, _ = Role.objects.update_or_create(
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
        role.permissions.set(
            Permission.objects.filter(codename__in=list(definition.permissions))
        )


def unseed(apps, schema_editor):
    Role = apps.get_model("security", "Role")
    Permission = apps.get_model("security", "Permission")
    Role.objects.filter(organization__isnull=True, is_system=True).delete()
    Permission.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
