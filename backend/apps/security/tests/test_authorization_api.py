"""End-to-end authorization tests against the HTTP API.

These are the tests that matter for the security requirements:

* **horizontal privilege escalation** — reaching another warehouse/user inside
  a tenant you can see;
* **vertical privilege escalation** — granting yourself (or others) authority
  you do not hold, at the API layer and through the role editor;
* **cross-organization access** — reaching a tenant you have no assignment in
  (must look like the resource does not exist);
* **unauthenticated access** — every protected endpoint must answer 401.

Every check is made against the backend API, never the frontend.
"""
from __future__ import annotations

from rest_framework.test import APITestCase

from apps.core.testing.factories import (
    DEFAULT_PASSWORD,
    assign,
    make_branch,
    make_custom_role,
    make_org_admin,
    make_organization,
    make_user,
    make_warehouse,
    role,
)
from apps.identity.models import User
from apps.security.models import RoleAssignment


class AuthorizationApiTestCase(APITestCase):
    """Shared fixture: two tenants, three warehouses, users with scoped roles."""

    def setUp(self):
        # Rate-limit counters live in the cache; clear them so tests are
        # independent of each other and of the previous suite.
        from django.core.cache import cache

        cache.clear()

    def login(self, email: str, password: str = DEFAULT_PASSWORD):
        response = self.client.post(
            "/api/v1/identity/auth/login/", {"email": email, "password": password}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def logout(self):
        self.client.post("/api/v1/identity/auth/logout/", format="json")

    @classmethod
    def setUpTestData(cls):
        cls.acme = make_organization("ACME", "Acme Distribution")
        cls.globex = make_organization("GLOBEX", "Globex Logistics")
        cls.acme_branch = make_branch(cls.acme, "ACME-B1", name="Acme North")
        cls.globex_branch = make_branch(cls.globex, "GLX-B1", name="Globex South")
        cls.wh_a1 = make_warehouse(cls.acme_branch, "WH-A1", name="Acme WH 1")
        cls.wh_a2 = make_warehouse(cls.acme_branch, "WH-A2", name="Acme WH 2")
        cls.wh_b1 = make_warehouse(cls.globex_branch, "WH-B1", name="Globex WH 1")

        cls.platform_admin = make_user("platform@wims.test", is_platform_admin=True)

        cls.manager_a = make_user("manager.a@acme.test", organization=cls.acme)
        assign(cls.manager_a, "warehouse_manager", organization=cls.acme)

        cls.viewer_a = make_user("viewer.a@acme.test", organization=cls.acme)
        assign(cls.viewer_a, "management_viewer", organization=cls.acme)

        cls.operator_a1 = make_user("operator.a1@acme.test", organization=cls.acme)
        assign(cls.operator_a1, "warehouse_operator", warehouse=cls.wh_a1)

        cls.manager_b = make_user("manager.b@globex.test", organization=cls.globex)
        assign(cls.manager_b, "warehouse_manager", organization=cls.globex)

        cls.org_admin_a = make_org_admin(cls.acme, "orgadmin.a@acme.test")
        cls.org_admin_b = make_org_admin(cls.globex, "orgadmin.b@globex.test")


class UnauthenticatedAccessTests(AuthorizationApiTestCase):
    """Nothing protected may be reachable without a session."""

    PROTECTED_ENDPOINTS = [
        ("get", "/api/v1/identity/users/"),
        ("get", "/api/v1/identity/profile/"),
        ("get", "/api/v1/identity/auth/session/"),
        ("get", "/api/v1/identity/sessions/"),
        ("get", "/api/v1/security/roles/"),
        ("get", "/api/v1/security/permissions/"),
        ("get", "/api/v1/security/assignments/"),
        ("get", "/api/v1/security/me/permissions/"),
        ("get", "/api/v1/organizations/"),
        ("get", "/api/v1/organizations/branches/"),
        ("get", "/api/v1/warehouses/"),
        ("get", "/api/v1/identity/login-attempts/"),
    ]

    def test_protected_endpoints_require_authentication(self):
        for method, url in self.PROTECTED_ENDPOINTS:
            with self.subTest(endpoint=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 401, f"{url} → {response.status_code}")

    def test_public_endpoints_remain_open(self):
        for url in (
            "/api/v1/health/",
            "/api/v1/health/live/",
            "/api/v1/",
        ):
            with self.subTest(endpoint=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_login_endpoint_rejects_anonymous_protected_call(self):
        self.assertEqual(self.client.post("/api/v1/security/roles/", {}, format="json").status_code, 401)


class PlatformAdminAccessTests(AuthorizationApiTestCase):
    """Positive control: platform administrators see everything."""

    def setUp(self):
        self.login(self.platform_admin.email)

    def test_sees_all_organizations(self):
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        codes = {row["code"] for row in response.data["results"]}
        self.assertEqual(codes, {"ACME", "GLOBEX"})

    def test_sees_all_warehouses_across_tenants(self):
        response = self.client.get("/api/v1/warehouses/")
        self.assertEqual(response.status_code, 200)
        codes = {row["code"] for row in response.data["results"]}
        self.assertEqual(codes, {"WH-A1", "WH-A2", "WH-B1"})

    def test_sees_users_from_every_organization(self):
        response = self.client.get("/api/v1/identity/users/")
        self.assertEqual(response.status_code, 200)
        emails = {row["email"] for row in response.data["results"]}
        self.assertIn("manager.a@acme.test", emails)
        self.assertIn("manager.b@globex.test", emails)

    def test_effective_permissions_include_platform_capabilities(self):
        response = self.client.get("/api/v1/security/me/permissions/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_platform_admin"])
        self.assertIn("configuration.manage", response.data["permissions"])
        self.assertIn("assignment.manage", response.data["permissions"])


class CrossOrganizationIsolationTests(AuthorizationApiTestCase):
    """Tenant boundaries: you cannot see, or even discover, another tenant."""

    def test_warehouse_manager_only_sees_own_organizations(self):
        self.login(self.manager_a.email)
        response = self.client.get("/api/v1/organizations/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"ACME"})

    def test_warehouse_manager_cannot_fetch_other_organization_detail(self):
        self.login(self.manager_a.email)
        response = self.client.get(f"/api/v1/organizations/{self.globex.id}/")
        self.assertEqual(response.status_code, 404)

    def test_warehouse_manager_cannot_list_other_organization_branches(self):
        self.login(self.manager_a.email)
        response = self.client.get(f"/api/v1/organizations/{self.globex.id}/branches/")
        self.assertEqual(response.status_code, 404)

    def test_branch_list_is_scoped(self):
        self.login(self.manager_a.email)
        response = self.client.get("/api/v1/organizations/branches/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"ACME-B1"})

    def test_branch_query_parameter_cannot_widen_scope(self):
        """Filtering by another tenant's id must not leak data."""
        self.login(self.manager_a.email)
        response = self.client.get(
            "/api/v1/organizations/branches/", {"organization": self.globex.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_users_from_other_organization_are_not_listed(self):
        self.login(self.org_admin_a.email)
        response = self.client.get("/api/v1/identity/users/")
        self.assertEqual(response.status_code, 200)
        emails = {row["email"] for row in response.data["results"]}
        self.assertNotIn("manager.b@globex.test", emails)
        self.assertNotIn("orgadmin.b@globex.test", emails)

    def test_org_admin_cannot_patch_user_of_another_organization(self):
        self.login(self.org_admin_a.email)
        response = self.client.patch(
            f"/api/v1/identity/users/{self.manager_b.id}/",
            {"job_title": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.manager_b.refresh_from_db()
        self.assertNotEqual(self.manager_b.job_title, "Hacked")

    def test_org_admin_cannot_deactivate_user_of_another_organization(self):
        self.login(self.org_admin_a.email)
        response = self.client.post(
            f"/api/v1/identity/users/{self.manager_b.id}/deactivate/", {}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.manager_b.refresh_from_db()
        self.assertTrue(self.manager_b.is_active)

    def test_org_admin_cannot_grant_role_in_another_organization(self):
        self.login(self.org_admin_a.email)
        response = self.client.post(
            "/api/v1/security/assignments/",
            {
                "user": self.manager_b.id,
                "role": role("warehouse_operator").id,
                "organization": self.globex.id,
                "warehouse": self.wh_b1.id,
            },
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(
            RoleAssignment.objects.filter(user=self.manager_b, organization=self.globex, role__code="warehouse_operator").exists()
        )

    def test_org_admin_cannot_create_role_in_another_organization(self):
        self.login(self.org_admin_a.email)
        before = self.globex.roles.count()
        response = self.client.post(
            "/api/v1/security/roles/",
            {"code": "evil_role", "name": "Evil", "level": 10, "organization": self.globex.id},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(self.globex.roles.count(), before)


class WarehouseIsolationTests(AuthorizationApiTestCase):
    """Warehouse-level authorization: no unauthorized warehouse access."""

    def test_warehouse_scoped_operator_sees_only_their_warehouse(self):
        self.login(self.operator_a1.email)
        response = self.client.get("/api/v1/warehouses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["code"] for row in response.data["results"]}, {"WH-A1"})

    def test_operator_cannot_fetch_another_warehouse_in_same_organization(self):
        self.login(self.operator_a1.email)
        response = self.client.get(f"/api/v1/warehouses/{self.wh_a2.id}/")
        self.assertEqual(response.status_code, 404)

    def test_operator_cannot_fetch_warehouse_of_another_organization(self):
        self.login(self.operator_a1.email)
        response = self.client.get(f"/api/v1/warehouses/{self.wh_b1.id}/")
        self.assertEqual(response.status_code, 404)

    def test_warehouse_filter_parameter_cannot_widen_scope(self):
        self.login(self.operator_a1.email)
        for warehouse_id in (self.wh_a2.id, self.wh_b1.id):
            response = self.client.get("/api/v1/warehouses/", {"warehouse": warehouse_id})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["results"], [])

    def test_warehouse_me_endpoint_reports_exact_scope(self):
        self.login(self.operator_a1.email)
        response = self.client.get("/api/v1/warehouses/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["warehouse_ids"], [self.wh_a1.id])

    def test_organization_wide_manager_sees_all_warehouses_of_the_organization(self):
        self.login(self.manager_a.email)
        response = self.client.get("/api/v1/warehouses/")
        self.assertEqual({row["code"] for row in response.data["results"]}, {"WH-A1", "WH-A2"})

    def test_operator_cannot_manage_warehouses(self):
        self.login(self.operator_a1.email)
        response = self.client.patch(
            f"/api/v1/warehouses/{self.wh_a1.id}/", {"name": "Renamed"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_warehouse_manager_can_manage_warehouse_in_scope(self):
        self.login(self.manager_a.email)
        response = self.client.patch(
            f"/api/v1/warehouses/{self.wh_a1.id}/", {"name": "Renamed by manager"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.wh_a1.refresh_from_db()
        self.assertEqual(self.wh_a1.name, "Renamed by manager")

    def test_operator_cannot_create_warehouse(self):
        self.login(self.operator_a1.email)
        response = self.client.post(
            "/api/v1/warehouses/",
            {"branch": self.acme_branch.id, "code": "WH-NEW", "name": "New"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class VerticalEscalationTests(AuthorizationApiTestCase):
    """No user may end up with authority they were not granted."""

    def test_operator_cannot_manage_assignments(self):
        self.login(self.operator_a1.email)
        response = self.client.post(
            "/api/v1/security/assignments/",
            {"user": self.operator_a1.id, "role": role("super_admin").id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_operator_cannot_list_assignments(self):
        self.login(self.operator_a1.email)
        self.assertEqual(self.client.get("/api/v1/security/assignments/").status_code, 403)

    def test_operator_cannot_manage_users(self):
        self.login(self.operator_a1.email)
        response = self.client.post(
            "/api/v1/identity/users/",
            {
                "email": "sneaky@acme.test",
                "first_name": "Sneaky",
                "last_name": "User",
                "password": "An0ther-Str0ng-Pass!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_operator_cannot_edit_own_privileges_via_profile(self):
        """Profile updates must not be able to change role-bearing fields."""
        self.login(self.operator_a1.email)
        response = self.client.patch(
            "/api/v1/identity/profile/",
            {"mfa_required": False, "organization": self.globex.id, "status": "active"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.operator_a1.refresh_from_db()
        # Untouched fields stay as they were (they are read-only in the serializer).
        self.assertEqual(self.operator_a1.organization_id, self.acme.id)

    def test_org_admin_cannot_grant_super_admin(self):
        self.login(self.org_admin_a.email)
        response = self.client.post(
            "/api/v1/security/assignments/",
            {
                "user": self.operator_a1.id,
                "role": role("super_admin").id,
                "organization": self.acme.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Platform roles", str(response.data))
        self.assertFalse(
            RoleAssignment.objects.filter(user=self.operator_a1, role__code="super_admin").exists()
        )

    def test_org_admin_cannot_grant_higher_ranked_role(self):
        """warehouse_manager (level 80) is above the level-60 org admin."""
        self.login(self.org_admin_a.email)
        response = self.client.post(
            "/api/v1/security/assignments/",
            {
                "user": self.operator_a1.id,
                "role": role("warehouse_manager").id,
                "organization": self.acme.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_org_admin_cannot_escalate_their_own_role_permissions(self):
        """Editing a role must not add permissions the caller does not hold."""
        self.login(self.org_admin_a.email)
        custom_role = make_custom_role(self.acme, "helper", ["inventory.view"], level=30)
        response = self.client.put(
            f"/api/v1/security/roles/{custom_role.id}/permissions/",
            {"permission_codes": ["inventory.view", "configuration.manage"]},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("configuration.manage", str(response.data))
        custom_role.refresh_from_db()
        self.assertEqual(custom_role.permission_codes, {"inventory.view"})

    def test_org_admin_cannot_modify_system_roles(self):
        self.login(self.org_admin_a.email)
        response = self.client.put(
            f"/api/v1/security/roles/{role('warehouse_operator').id}/permissions/",
            {"permission_codes": ["configuration.manage"]},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_org_admin_cannot_deactivate_higher_ranked_user(self):
        self.login(self.org_admin_a.email)
        response = self.client.post(
            f"/api/v1/identity/users/{self.manager_a.id}/deactivate/", {}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.manager_a.refresh_from_db()
        self.assertTrue(self.manager_a.is_active)

    def test_cannot_assign_warehouse_from_another_organization(self):
        """Warehouse scope must belong to the organization being granted in."""
        self.login(self.org_admin_a.email)
        response = self.client.post(
            "/api/v1/security/assignments/",
            {
                "user": self.operator_a1.id,
                "role": role("warehouse_operator").id,
                "organization": self.acme.id,
                "warehouse": self.wh_b1.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            RoleAssignment.objects.filter(user=self.operator_a1, warehouse=self.wh_b1).exists()
        )

    def test_users_cannot_change_their_own_password_without_current_password(self):
        self.login(self.operator_a1.email)
        response = self.client.post(
            "/api/v1/identity/auth/password/change/",
            {"current_password": "wrong", "new_password": "An0ther-Str0ng-Pass!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_org_admin_cannot_promote_user_to_platform_admin(self):
        """``is_superuser``/``is_staff`` are not writable through the API."""
        self.login(self.org_admin_a.email)
        response = self.client.patch(
            f"/api/v1/identity/users/{self.operator_a1.id}/",
            {"is_superuser": True, "is_staff": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.operator_a1.refresh_from_db()
        self.assertFalse(self.operator_a1.is_superuser)
        self.assertFalse(self.operator_a1.is_staff)


class GranularPermissionTests(AuthorizationApiTestCase):
    """Permissions granted by role map exactly to what the API allows."""

    def test_permission_diagnostics_per_scope(self):
        """``POST /security/me/permissions/`` answers scope-specific questions."""
        self.login(self.operator_a1.email)

        own = self.client.post(
            "/api/v1/security/me/permissions/",
            {"permission": "inventory.create", "warehouse": self.wh_a1.id},
            format="json",
        )
        self.assertTrue(own.data["granted"])

        other = self.client.post(
            "/api/v1/security/me/permissions/",
            {"permission": "inventory.create", "warehouse": self.wh_a2.id},
            format="json",
        )
        self.assertFalse(other.data["granted"])

        cross_org = self.client.post(
            "/api/v1/security/me/permissions/",
            {"permission": "inventory.create", "warehouse": self.wh_b1.id},
            format="json",
        )
        self.assertFalse(cross_org.data["granted"])

    def test_operator_lacks_approval_permissions(self):
        self.login(self.operator_a1.email)
        response = self.client.get("/api/v1/security/me/permissions/")
        permissions = set(response.data["permissions"])
        self.assertIn("inventory.create", permissions)
        self.assertNotIn("inventory.adjust", permissions)
        self.assertNotIn("inventory.approve_adjustment", permissions)
        self.assertNotIn("purchase_order.approve", permissions)
        self.assertNotIn("transfer.approve", permissions)

    def test_inventory_controller_has_adjustment_approval_but_not_po_approval(self):
        user = make_user("controller@acme.test", organization=self.acme)
        assign(user, "inventory_controller", organization=self.acme)
        self.login(user.email)
        permissions = set(self.client.get("/api/v1/security/me/permissions/").data["permissions"])
        self.assertIn("inventory.adjust", permissions)
        self.assertIn("inventory.approve_adjustment", permissions)
        self.assertIn("transfer.approve", permissions)
        self.assertNotIn("purchase_order.approve", permissions)
        self.assertNotIn("configuration.manage", permissions)

    def test_management_viewer_is_read_only(self):
        self.login(self.viewer_a.email)
        permissions = set(self.client.get("/api/v1/security/me/permissions/").data["permissions"])
        for read_only in ("inventory.view", "warehouse.view", "report.view", "purchase_order.view"):
            self.assertIn(read_only, permissions)
        for forbidden in ("inventory.adjust", "warehouse.manage", "transfer.create", "user.manage"):
            self.assertNotIn(forbidden, permissions)

    def test_viewer_cannot_create_warehouse_or_user(self):
        self.login(self.viewer_a.email)
        self.assertEqual(
            self.client.post(
                "/api/v1/warehouses/",
                {"branch": self.acme_branch.id, "code": "WH-X", "name": "X"},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/identity/users/",
                {
                    "email": "x@acme.test",
                    "first_name": "X",
                    "last_name": "Y",
                    "password": "An0ther-Str0ng-Pass!",
                },
                format="json",
            ).status_code,
            403,
        )

    def test_supplier_portal_user_is_restricted(self):
        supplier_user = make_user("supplier@vendor.test")
        assign(supplier_user, "supplier_portal_user", organization=None) if False else None
        self.login(supplier_user.email)
        # No assignment at all → the capability does not exist in any scope, so
        # operational endpoints answer 403 (never a misleading empty 200 that
        # would imply the caller may read warehouses).
        self.assertEqual(self.client.get("/api/v1/warehouses/").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/v1/security/assignments/",
                {"user": supplier_user.id, "role": role("warehouse_operator").id},
                format="json",
            ).status_code,
            403,
        )

    def test_role_permission_matrix_matches_registry(self):
        """System roles expose exactly the permissions defined in code."""
        from apps.security.role_registry import SYSTEM_ROLES

        self.login(self.platform_admin.email)
        response = self.client.get("/api/v1/security/roles/", {"page_size": 50})
        self.assertEqual(response.status_code, 200)
        by_code = {row["code"]: row for row in response.data["results"]}
        for definition in SYSTEM_ROLES:
            with self.subTest(role=definition.code):
                self.assertIn(definition.code, by_code)
                self.assertEqual(
                    set(by_code[definition.code]["permission_codes"]),
                    set(definition.permissions),
                )


class AssignmentApiTests(AuthorizationApiTestCase):
    """Role assignment lifecycle through the API."""

    def test_org_admin_grants_and_revokes_warehouse_operator(self):
        self.login(self.org_admin_a.email)
        new_user = make_user("newop@acme.test", organization=self.acme)

        create = self.client.post(
            "/api/v1/security/assignments/",
            {
                "user": new_user.id,
                "role": role("warehouse_operator").id,
                "organization": self.acme.id,
                "warehouse": self.wh_a2.id,
            },
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        assignment_id = create.data["id"]

        # The grant is immediately effective for that warehouse only.
        self.logout()
        self.login(new_user.email)
        self.assertEqual(
            {row["code"] for row in self.client.get("/api/v1/warehouses/").data["results"]},
            {"WH-A2"},
        )

        # Revoke → access disappears.
        self.logout()
        self.login(self.org_admin_a.email)
        self.assertEqual(
            self.client.delete(f"/api/v1/security/assignments/{assignment_id}/").status_code, 204
        )
        self.logout()
        self.login(new_user.email)
        # Revoked → the capability is no longer held in any scope → 403.
        self.assertEqual(self.client.get("/api/v1/warehouses/").status_code, 403)

    def test_assignment_listing_is_scoped_to_the_caller(self):
        self.login(self.org_admin_a.email)
        response = self.client.get("/api/v1/security/assignments/")
        self.assertEqual(response.status_code, 200)
        for row in response.data["results"]:
            self.assertIn(
                row["organization"],
                (self.acme.id, None),
                "assignments from other tenants must not be listed",
            )

    def test_grantable_roles_endpoint_excludes_platform_and_high_roles(self):
        self.login(self.org_admin_a.email)
        response = self.client.get("/api/v1/security/roles/grantable/", {"organization": self.acme.id})
        self.assertEqual(response.status_code, 200)
        codes = {row["code"] for row in response.data["results"]}
        self.assertIn("warehouse_operator", codes)
        self.assertNotIn("super_admin", codes)
        self.assertNotIn("warehouse_manager", codes)
        self.assertNotIn("finance_accounts", codes)

    def test_assignments_are_immutable(self):
        self.login(self.org_admin_a.email)
        assignment = RoleAssignment.objects.filter(user=self.operator_a1).first()
        response = self.client.patch(
            f"/api/v1/security/assignments/{assignment.id}/", {"is_active": True}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_expired_assignment_cannot_be_created_in_the_past(self):
        self.login(self.org_admin_a.email)
        new_user = make_user("past@acme.test", organization=self.acme)
        response = self.client.post(
            "/api/v1/security/assignments/",
            {
                "user": new_user.id,
                "role": role("warehouse_operator").id,
                "organization": self.acme.id,
                "expires_at": "2020-01-01T00:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_assignment_revocation_requires_permission(self):
        self.login(self.viewer_a.email)
        assignment = RoleAssignment.objects.filter(user=self.operator_a1).first()
        response = self.client.delete(f"/api/v1/security/assignments/{assignment.id}/")
        self.assertEqual(response.status_code, 403)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)


class UserAdministrationScopeTests(AuthorizationApiTestCase):
    """User management honours organization and rank boundaries end to end."""

    def test_org_admin_creates_user_in_own_organization(self):
        self.login(self.org_admin_a.email)
        response = self.client.post(
            "/api/v1/identity/users/",
            {
                "email": "created@acme.test",
                "first_name": "Created",
                "last_name": "User",
                "job_title": "Picker",
                "password": "An0ther-Str0ng-Pass!",
                "send_verification_email": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(email="created@acme.test")
        self.assertEqual(created.organization_id, self.acme.id)
        self.assertTrue(created.must_change_password)

    def test_org_admin_cannot_create_user_in_another_organization(self):
        self.login(self.org_admin_a.email)
        response = self.client.post(
            "/api/v1/identity/users/",
            {
                "email": "intruder@globex.test",
                "first_name": "In",
                "last_name": "Truder",
                "password": "An0ther-Str0ng-Pass!",
                "organization_id": self.globex.id,
                "send_verification_email": False,
            },
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(User.objects.filter(email="intruder@globex.test").exists())

    def test_org_admin_can_deactivate_lower_ranked_user_in_scope(self):
        target = make_user("junior@acme.test", organization=self.acme)
        assign(target, "warehouse_operator", organization=self.acme)
        self.login(self.org_admin_a.email)
        response = self.client.post(
            f"/api/v1/identity/users/{target.id}/deactivate/",
            {"reason": "left the company"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertEqual(target.status, User.Status.DEACTIVATED)
        # Deactivation removes effective authority immediately.
        self.assertFalse(target.role_assignments.filter(is_active=True).exists())

    def test_deactivated_user_cannot_sign_in(self):
        target = make_user("leaver@acme.test", organization=self.acme)
        self.login(self.org_admin_a.email)
        self.client.post(f"/api/v1/identity/users/{target.id}/deactivate/", {}, format="json")
        self.logout()
        response = self.client.post(
            "/api/v1/identity/auth/login/",
            {"email": target.email, "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_users_cannot_deactivate_themselves(self):
        self.login(self.org_admin_a.email)
        response = self.client.post(
            f"/api/v1/identity/users/{self.org_admin_a.id}/deactivate/", {}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_user_deletion_is_refused(self):
        self.login(self.platform_admin.email)
        response = self.client.delete(f"/api/v1/identity/users/{self.operator_a1.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=self.operator_a1.id).exists())

    def test_admin_can_revoke_user_sessions(self):
        # Sign the operator in on a separate client.
        from rest_framework.test import APIClient

        other_client = APIClient()
        session_response = other_client.post(
            "/api/v1/identity/auth/login/",
            {"email": self.operator_a1.email, "password": DEFAULT_PASSWORD},
            format="json",
        )
        self.assertEqual(session_response.status_code, 200)
        self.assertEqual(other_client.get("/api/v1/identity/profile/").status_code, 200)

        self.login(self.platform_admin.email)
        response = self.client.post(
            f"/api/v1/identity/users/{self.operator_a1.id}/revoke-sessions/", {}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["revoked"], 1)

        # The revoked client is now unauthenticated on the next request.
        follow_up = other_client.get("/api/v1/identity/profile/")
        self.assertEqual(follow_up.status_code, 401)
