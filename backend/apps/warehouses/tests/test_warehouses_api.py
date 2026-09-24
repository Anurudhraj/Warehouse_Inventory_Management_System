"""Warehouse API tests: scoped visibility, unauthorized-warehouse protection,
activation lifecycle and the "never delete" policy.

Warehouse scope is the finest-grained authorization boundary in the platform,
so these tests cover both directions: an operator must not reach a warehouse
they were not granted, and an organization-wide manager must reach all of them.
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
from apps.warehouses.models import Warehouse

WAREHOUSES_URL = "/api/v1/warehouses/"


class WarehouseApiTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.acme = make_organization("ACME", "Acme Distribution")
        cls.globex = make_organization("GLOBEX", "Globex Logistics")
        cls.acme_branch = make_branch(cls.acme, "ACME-B1", name="Acme North")
        cls.globex_branch = make_branch(cls.globex, "GLX-B1", name="Globex South")
        cls.wh_a1 = make_warehouse(cls.acme_branch, "WH-A1", name="Acme WH 1")
        cls.wh_a2 = make_warehouse(cls.acme_branch, "WH-A2", name="Acme WH 2")
        cls.wh_b1 = make_warehouse(cls.globex_branch, "WH-B1", name="Globex WH 1")

        cls.platform = make_user("platform@wims.test", is_platform_admin=True)
        cls.admin_a = make_org_admin(cls.acme, "admin.a@acme.test")

        cls.manager = make_user("manager@acme.test", organization=cls.acme)
        assign(cls.manager, "warehouse_manager", organization=cls.acme)

        cls.operator = make_user("operator@acme.test", organization=cls.acme)
        assign(cls.operator, "warehouse_operator", warehouse=cls.wh_a1)

    def login(self, email: str, password: str = DEFAULT_PASSWORD):
        response = self.client.post(
            "/api/v1/identity/auth/login/", {"email": email, "password": password}, format="json"
        )
        assert response.status_code == 200, response.data
        return response


class WarehouseVisibilityTests(WarehouseApiTestCase):
    def test_unauthenticated_callers_are_rejected(self):
        self.assertEqual(self.client.get(WAREHOUSES_URL).status_code, 401)

    def test_operator_only_sees_the_granted_warehouse(self):
        self.login(self.operator.email)
        response = self.client.get(WAREHOUSES_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"WH-A1"})

    def test_organization_wide_manager_sees_every_warehouse_of_the_tenant(self):
        self.login(self.manager.email)
        response = self.client.get(WAREHOUSES_URL)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"WH-A1", "WH-A2"})

    def test_platform_administrator_sees_every_warehouse(self):
        self.login(self.platform.email)
        response = self.client.get(WAREHOUSES_URL)
        self.assertEqual(
            {row["code"] for row in response.data["results"]}, {"WH-A1", "WH-A2", "WH-B1"}
        )

    def test_foreign_warehouse_detail_is_not_found(self):
        self.login(self.operator.email)
        self.assertEqual(self.client.get(f"{WAREHOUSES_URL}{self.wh_b1.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"{WAREHOUSES_URL}{self.wh_a2.id}/").status_code, 404)

    def test_query_parameters_can_only_narrow_the_scope(self):
        self.login(self.operator.email)

        allowed = self.client.get(WAREHOUSES_URL, {"warehouse": self.wh_a1.id})
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual({row["code"] for row in allowed.data["results"]}, {"WH-A1"})

        for parameter, value in (
            ("warehouse", self.wh_a2.id),
            ("warehouse_id", self.wh_b1.id),
            ("organization", self.globex.id),
            ("warehouse", "not-an-integer"),
        ):
            with self.subTest(parameter=parameter, value=value):
                response = self.client.get(WAREHOUSES_URL, {parameter: value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["results"], [])

    def test_search_cannot_escape_the_scope(self):
        self.login(self.operator.email)
        response = self.client.get(WAREHOUSES_URL, {"search": "Globex"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_me_endpoint_reports_the_exact_scope(self):
        self.login(self.operator.email)
        response = self.client.get(f"{WAREHOUSES_URL}me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["warehouse_ids"], [self.wh_a1.id])
        self.assertEqual(response.data["count"], 1)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"WH-A1"})

    def test_a_user_without_any_grant_cannot_list_warehouses(self):
        nobody = make_user("nobody@acme.test", organization=self.acme)
        self.login(nobody.email)

        response = self.client.get(WAREHOUSES_URL)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(f"{WAREHOUSES_URL}me/").status_code, 403)


class WarehouseMutationTests(WarehouseApiTestCase):
    def test_operator_cannot_create_warehouses(self):
        self.login(self.operator.email)
        response = self.client.post(
            WAREHOUSES_URL,
            {"branch": self.acme_branch.id, "code": "WH-A3", "name": "Acme WH 3"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Warehouse.objects.filter(code="WH-A3").exists())

    def test_manager_creates_a_warehouse_inside_the_tenant(self):
        self.login(self.manager.email)
        response = self.client.post(
            WAREHOUSES_URL,
            {
                "branch": self.acme_branch.id,
                "code": "WH-A3",
                "name": "Acme WH 3",
                "warehouse_type": "distribution",
                "city": "Pune",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        created = Warehouse.objects.get(code="WH-A3")
        self.assertEqual(created.organization_id, self.acme.id)

    def test_warehouse_cannot_be_created_in_another_tenant(self):
        self.login(self.manager.email)
        response = self.client.post(
            WAREHOUSES_URL,
            {"branch": self.globex_branch.id, "code": "WH-B2", "name": "Globex WH 2"},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(Warehouse.objects.filter(code="WH-B2").exists())

    def test_duplicate_code_within_a_branch_is_refused(self):
        self.login(self.manager.email)
        response = self.client.post(
            WAREHOUSES_URL,
            {"branch": self.acme_branch.id, "code": "WH-A1", "name": "Duplicate"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_manager_can_rename_a_warehouse_in_scope(self):
        self.login(self.manager.email)
        response = self.client.patch(
            f"{WAREHOUSES_URL}{self.wh_a2.id}/", {"name": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.wh_a2.refresh_from_db()
        self.assertEqual(self.wh_a2.name, "Renamed")

    def test_operator_cannot_rename_the_warehouse_they_work_in(self):
        self.login(self.operator.email)
        response = self.client.patch(
            f"{WAREHOUSES_URL}{self.wh_a1.id}/", {"name": "Mine now"}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.wh_a1.refresh_from_db()
        self.assertEqual(self.wh_a1.name, "Acme WH 1")

    def test_warehouses_are_deactivated_never_deleted(self):
        self.login(self.manager.email)

        deleted = self.client.delete(f"{WAREHOUSES_URL}{self.wh_a2.id}/")
        self.assertEqual(deleted.status_code, 400)
        self.assertTrue(Warehouse.objects.filter(pk=self.wh_a2.id).exists())

        deactivated = self.client.post(f"{WAREHOUSES_URL}{self.wh_a2.id}/deactivate/", {}, format="json")
        self.assertEqual(deactivated.status_code, 200, deactivated.data)
        self.wh_a2.refresh_from_db()
        self.assertFalse(self.wh_a2.is_active)
        self.assertEqual(Warehouse.objects.filter(pk=self.wh_a2.id).count(), 1)

        self.assertEqual(self.client.post(f"{WAREHOUSES_URL}{self.wh_a2.id}/activate/").status_code, 200)
        self.wh_a2.refresh_from_db()
        self.assertTrue(self.wh_a2.is_active)

    def test_other_tenants_warehouse_cannot_be_modified_or_toggled(self):
        self.login(self.manager.email)

        self.assertEqual(
            self.client.patch(f"{WAREHOUSES_URL}{self.wh_b1.id}/", {"name": "Hijacked"}, format="json").status_code,
            404,
        )
        self.assertEqual(
            self.client.post(f"{WAREHOUSES_URL}{self.wh_b1.id}/deactivate/", {}, format="json").status_code,
            404,
        )
        self.wh_b1.refresh_from_db()
        self.assertEqual(self.wh_b1.name, "Globex WH 1")
        self.assertTrue(self.wh_b1.is_active)
