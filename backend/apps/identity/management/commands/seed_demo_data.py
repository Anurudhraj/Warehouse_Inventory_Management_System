"""``manage.py seed_demo_data`` — idempotent development/demo dataset.

Creates one organization with a branch and two warehouses plus a handful of
users covering the main specification roles, so a fresh database is immediately
usable (sign-in works, the Users/Roles/Permissions screens have content).

    python manage.py seed_demo_data
    python manage.py seed_demo_data --reset-passwords

Safe to re-run: everything is looked up by natural key and only created when
missing. Refuses to run against production settings unless ``--force``.
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity.models import User
from apps.organizations.models import Branch, Organization
from apps.security.models import Role, RoleAssignment
from apps.warehouses.models import Warehouse

DEMO_PASSWORD = "Wims-Demo-Password-2026!"  # noqa: S105 - demo fixture, documented in the README

ORGANIZATION = {"code": "ACME", "name": "Acme Distribution"}
BRANCH = {"code": "ACME-B1", "name": "Central Distribution Centre"}
WAREHOUSES = [
    {"code": "WH-A1", "name": "Bhopal Main Warehouse"},
    {"code": "WH-A2", "name": "Indore Overflow Warehouse"},
]

#: email → (first, last, job title, role code, scope)
USERS: list[tuple[str, str, str, str, str, str]] = [
    ("manager@wims.local", "Maya", "Ramteke", "Warehouse Manager", "warehouse_manager", "org"),
    ("controller@wims.local", "Chetan", "Iyer", "Inventory Controller", "inventory_controller", "warehouse"),
    ("operator@wims.local", "Omkar", "Patil", "Warehouse Operator", "warehouse_operator", "warehouse"),
    ("viewer@wims.local", "Vidya", "Nair", "Management Viewer", "management_viewer", "org"),
]


class Command(BaseCommand):
    help = "Create an idempotent demo organization, warehouses and role-scoped users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow seeding when the environment is 'production'.",
        )
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Reset the demo users' passwords to the documented demo password.",
        )

    def handle(self, *args, **options):
        if settings.ENVIRONMENT == "production" and not options["force"]:
            raise CommandError(
                "Refusing to seed demo data with production settings. Pass --force to override."
            )

        with transaction.atomic():
            organization, _ = Organization.objects.get_or_create(
                code=ORGANIZATION["code"], defaults={"name": ORGANIZATION["name"]}
            )
            branch, _ = Branch.objects.get_or_create(
                organization=organization,
                code=BRANCH["code"],
                defaults={"name": BRANCH["name"]},
            )

            warehouses: dict[str, Warehouse] = {}
            for spec in WAREHOUSES:
                warehouse, _ = Warehouse.objects.get_or_create(
                    branch=branch,
                    code=spec["code"],
                    defaults={"name": spec["name"]},
                )
                warehouses[spec["code"]] = warehouse

            created_users = 0
            for email, first, last, title, role_code, scope in USERS:
                user = User.objects.filter(email=email).first()
                if user is None:
                    user = User.objects.create_user(
                        email=email,
                        password=DEMO_PASSWORD,
                        first_name=first,
                        last_name=last,
                        job_title=title,
                        organization=organization,
                    )
                    user.mark_email_verified()
                    user.save(update_fields=["is_email_verified", "email_verified_at"])
                    created_users += 1
                elif options["reset_passwords"]:
                    user.set_password(DEMO_PASSWORD)
                    user.save(update_fields=["password", "password_changed_at"])

                role = Role.objects.filter(organization__isnull=True, code=role_code).first()
                if role is None:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Role '{role_code}' is missing — run 'manage.py sync_rbac' first."
                        )
                    )
                    continue

                if scope == "warehouse":
                    warehouse = warehouses[WAREHOUSES[0]["code"]]
                    if not RoleAssignment.objects.filter(
                        user=user, role=role, warehouse=warehouse, is_active=True
                    ).exists():
                        RoleAssignment.objects.create(
                            user=user,
                            role=role,
                            organization=organization,
                            warehouse=warehouse,
                        )
                elif not RoleAssignment.objects.filter(
                    user=user, role=role, organization=organization, warehouse__isnull=True
                ).exists():
                    RoleAssignment.objects.create(
                        user=user,
                        role=role,
                        organization=organization,
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: organization {organization.code}, "
                f"{len(warehouses)} warehouses, "
                f"{len(USERS) + 1} users visible in the console "
                f"({created_users} created now)."
            )
        )
        self.stdout.write(f"Demo password for all seeded users: {DEMO_PASSWORD}")
