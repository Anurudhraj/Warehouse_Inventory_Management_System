"""Organizations and branches API tests.

The tenancy boundary is the point of these tests: an organization is the root
of every authorization decision, so listing, reading, creating and editing
organizations/branches must all be scoped, and tenant-bounded resources must
look like they do not exist to outsiders.
"""
from __future__ import annotations

from rest_framework.test import APITestCase

from apps.core.testing.factories import (
    DEFAULT_PASSWORD,
    assign,
    make_branch,
    make_org_admin,
    make_organization,
    make_user,
    make_warehouse,
)
from apps.organizations.models import Branch, Organization

ORGS_URL = "/api/v1/organizations/"
BRANCHES_URL = "/api/v1/organizations/branches/"


class OrganizationApiTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.acme = make_organization("ACME", "Acme Distribution")
        cls.globex = make_organization("GLOBEX", "Globex Logistics")
        cls.acme_branch = make_branch(cls.acme, "ACME-B1", name="Acme North")
        cls.globex_branch = make_branch(cls.globex, "GLX-B1", name="Globex South")
        cls.acme_warehouse = make_warehouse(cls.acme_branch, "WH-A1", name="Acme WH 1")
        cls.globex_warehouse = make_warehouse(cls.globex_branch, "WH-B1", name="Globex WH 1")

        cls.platform = make_user("platform@wims.test", is_platform_admin=True)
        cls.admin_a = make_org_admin(cls.acme, "admin.a@acme.test")
        cls.admin_b = make_org_admin(cls.globex, "admin.b@globex.test")

    def login(self, email: str, password: str = DEFAULT_PASSWORD):
        response = self.client.post(
            "/api/v1/identity/auth/login/", {"email": email, "password": password}, format="json"
        )
        assert response.status_code == 200, response.data
        return response


class OrganizationListingTests(OrganizationApiTestCase):
    def test_unauthenticated_callers_are_rejected(self):
        self.assertEqual(self.client.get(ORGS_URL).status_code, 401)

    def test_organization_admin_only_sees_their_own_tenant(self):
        self.login(self.admin_a.email)
        response = self.client.get(ORGS_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"ACME"})

    def test_platform_administrator_sees_every_tenant(self):
        self.login(self.platform.email)
        response = self.client.get(ORGS_URL)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"ACME", "GLOBEX"})

    def test_cross_tenant_detail_looks_like_a_missing_resource(self):
        self.login(self.admin_a.email)
        response = self.client.get(f"{ORGS_URL}{self.globex.id}/")
        self.assertEqual(response.status_code, 404)

    def test_counts_are_reported_without_leaking_other_tenants(self):
        self.login(self.admin_a.email)
        detail = self.client.get(f"{ORGS_URL}{self.acme.id}/")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["branch_count"], 1)
        self.assertEqual(detail.data["warehouse_count"], 1)
        self.assertGreaterEqual(detail.data["user_count"], 1)

    def test_a_user_without_organization_view_is_refused(self):
        outsider = make_user("operator@acme.test", organization=self.acme)
        assign(outsider, "warehouse_operator", warehouse=self.acme_warehouse)

        self.login(outsider.email)
        self.assertEqual(self.client.get(ORGS_URL).status_code, 403)


class OrganizationMutationTests(OrganizationApiTestCase):
    def test_only_platform_administrators_create_tenants(self):
        self.login(self.admin_a.email)
        refused = self.client.post(
            ORGS_URL,
            {"code": "INITECH", "name": "Initech"},
            format="json",
        )
        self.assertEqual(refused.status_code, 403)
        self.assertFalse(Organization.objects.filter(code="INITECH").exists())

        self.login(self.platform.email)
        created = self.client.post(
            ORGS_URL,
            {
                "code": "INITECH",
                "name": "Initech",
                "contact_email": "ops@initech.test",
                "default_currency": "USD",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(Organization.objects.filter(code="INITECH").exists())

    def test_organization_admin_cannot_edit_their_tenant(self):
        """"organization.view" is not "organization.manage"."""
        self.login(self.admin_a.email)
        response = self.client.patch(f"{ORGS_URL}{self.acme.id}/", {"name": "Renamed"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.acme.refresh_from_db()
        self.assertEqual(self.acme.name, "Acme Distribution")

    def test_platform_administrator_can_edit_a_tenant(self):
        self.login(self.platform.email)
        response = self.client.patch(
            f"{ORGS_URL}{self.acme.id}/", {"legal_name": "Acme Distribution Ltd"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.acme.refresh_from_db()
        self.assertEqual(self.acme.legal_name, "Acme Distribution Ltd")

    def test_organizations_are_archived_never_deleted(self):
        self.login(self.platform.email)
        response = self.client.delete(f"{ORGS_URL}{self.globex.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Organization.objects.filter(pk=self.globex.id).exists())

    def test_duplicate_code_is_refused(self):
        self.login(self.platform.email)
        response = self.client.post(ORGS_URL, {"code": "acme", "name": "Clone"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_nested_branch_and_warehouse_actions_are_scoped(self):
        self.login(self.admin_a.email)

        own = self.client.get(f"{ORGS_URL}{self.acme.id}/branches/")
        self.assertEqual(own.status_code, 200)
        self.assertEqual({row["code"] for row in own.data["results"]}, {"ACME-B1"})
        # Regression: the annotated count must survive serialization.
        self.assertEqual(own.data["results"][0]["warehouse_count"], 1)

        foreign = self.client.get(f"{ORGS_URL}{self.globex.id}/branches/")
        self.assertEqual(foreign.status_code, 404)

        warehouses = self.client.get(f"{ORGS_URL}{self.acme.id}/warehouses/")
        self.assertEqual(warehouses.status_code, 200)
        self.assertEqual({row["code"] for row in warehouses.data["results"]}, {"WH-A1"})

        foreign_warehouses = self.client.get(f"{ORGS_URL}{self.globex.id}/warehouses/")
        self.assertEqual(foreign_warehouses.status_code, 404)


class BranchApiTests(OrganizationApiTestCase):
    def test_branch_listing_is_scoped_to_accessible_organizations(self):
        self.login(self.admin_a.email)
        response = self.client.get(BRANCHES_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"ACME-B1"})

    def test_branch_listing_cannot_be_widened_with_a_query_parameter(self):
        self.login(self.admin_a.email)
        response = self.client.get(BRANCHES_URL, {"organization": self.globex.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_branch_detail_of_another_tenant_is_not_found(self):
        self.login(self.admin_a.email)
        self.assertEqual(self.client.get(f"{BRANCHES_URL}{self.globex_branch.id}/").status_code, 404)

    def test_organization_admin_creates_a_branch_in_their_own_tenant(self):
        self.login(self.admin_a.email)
        response = self.client.post(
            BRANCHES_URL,
            {
                "organization": self.acme.id,
                "code": "ACME-B2",
                "name": "Acme South",
                "city": "Pune",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        branch = Branch.objects.get(code="ACME-B2")
        self.assertEqual(branch.organization_id, self.acme.id)

    def test_branch_cannot_be_created_in_another_tenant(self):
        self.login(self.admin_a.email)
        response = self.client.post(
            BRANCHES_URL,
            {"organization": self.globex.id, "code": "GLX-B2", "name": "Globex North"},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(Branch.objects.filter(code="GLX-B2").exists())

    def test_branch_can_be_deactivated_from_the_api(self):
        self.login(self.admin_a.email)
        response = self.client.post(f"{BRANCHES_URL}{self.acme_branch.id}/deactivate/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

        self.acme_branch.refresh_from_db()
        self.assertFalse(self.acme_branch.is_active)
        self.assertTrue(Branch.objects.filter(pk=self.acme_branch.pk).exists())

    def test_deactivating_a_foreign_branch_is_not_found(self):
        self.login(self.admin_a.email)
        response = self.client.post(f"{BRANCHES_URL}{self.globex_branch.id}/deactivate/", {}, format="json")
        self.assertEqual(response.status_code, 404)
        self.globex_branch.refresh_from_db()
        self.assertTrue(self.globex_branch.is_active)

    def test_branch_with_warehouses_cannot_be_deleted(self):
        self.login(self.admin_a.email)
        response = self.client.delete(f"{BRANCHES_URL}{self.acme_branch.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Branch.objects.filter(pk=self.acme_branch.pk).exists())

    def test_empty_branch_can_be_deleted(self):
        empty = make_branch(self.acme, "ACME-B9", name="Acme Temp")
        self.login(self.admin_a.email)

        response = self.client.delete(f"{BRANCHES_URL}{empty.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Branch.objects.filter(pk=empty.pk).exists())

    def test_a_user_without_branch_manage_cannot_create_branches(self):
        operator = make_user("operator@acme.test", organization=self.acme)
        assign(operator, "warehouse_operator", warehouse=self.acme_warehouse)

        self.login(operator.email)
        response = self.client.post(
            BRANCHES_URL,
            {"organization": self.acme.id, "code": "ACME-X", "name": "Nope"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
