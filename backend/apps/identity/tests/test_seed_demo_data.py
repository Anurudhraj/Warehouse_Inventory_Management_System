"""``seed_demo_data`` must be safe to re-run and produce usable accounts."""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.identity.management.commands.seed_demo_data import DEMO_PASSWORD
from apps.identity.models import User
from apps.organizations.models import Branch, Organization
from apps.security.models import RoleAssignment
from apps.warehouses.models import Warehouse


class SeedDemoDataTests(TestCase):
    def seed(self) -> str:
        out = StringIO()
        call_command("seed_demo_data", stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_seeds_organization_and_role_scoped_users(self):
        self.seed()

        self.assertTrue(Organization.objects.filter(code="ACME").exists())
        self.assertTrue(Branch.objects.filter(code="ACME-B1").exists())
        self.assertEqual(Warehouse.objects.filter(branch__code="ACME-B1").count(), 2)

        manager = User.objects.get(email="manager@wims.local")
        self.assertTrue(manager.is_email_verified)
        grants = RoleAssignment.objects.filter(user=manager, is_active=True)
        self.assertEqual([g.role.code for g in grants], ["warehouse_manager"])
        self.assertIsNone(grants.first().warehouse)  # organization-wide

        operator = User.objects.get(email="operator@wims.local")
        assignment = RoleAssignment.objects.get(user=operator, is_active=True)
        self.assertIsNotNone(assignment.warehouse)  # warehouse-scoped

    def test_is_idempotent(self):
        self.seed()
        users = User.objects.count()
        assignments = RoleAssignment.objects.count()

        self.seed()

        self.assertEqual(User.objects.count(), users)
        self.assertEqual(RoleAssignment.objects.count(), assignments)

    def test_seeded_users_can_sign_in(self):
        self.seed()
        response = self.client.post(
            "/api/v1/identity/auth/login/",
            {"email": "manager@wims.local", "password": DEMO_PASSWORD},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("warehouse.view", response.json()["permissions"])

    @override_settings(ENVIRONMENT="production")
    def test_refuses_to_run_in_production(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo_data", stdout=StringIO(), stderr=StringIO())
