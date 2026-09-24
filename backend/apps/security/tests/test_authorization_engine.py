"""Unit tests for the authorization engine.

These are the lowest-level guarantees the API builds on: deny-by-default,
scope matching (organization vs warehouse), and the delegation rules that stop
vertical privilege escalation.
"""
from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from apps.core.testing.factories import (
    assign,
    make_branch,
    make_custom_role,
    make_org_admin,
    make_organization,
    make_user,
    make_warehouse,
    role,
)
from apps.security.authorization import AuthorizationService
from apps.security.models import RoleAssignment


class AuthorizationEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.acme = make_organization("ACME", "Acme Distribution")
        cls.globex = make_organization("GLOBEX", "Globex Logistics")
        cls.acme_branch = make_branch(cls.acme, "ACME-B1")
        cls.globex_branch = make_branch(cls.globex, "GLX-B1")
        cls.wh_a1 = make_warehouse(cls.acme_branch, "WH-A1")
        cls.wh_a2 = make_warehouse(cls.acme_branch, "WH-A2")
        cls.wh_b1 = make_warehouse(cls.globex_branch, "WH-B1")

        # Platform administrator (no organization scope)
        cls.platform_admin = make_user("platform@wims.test", is_platform_admin=True)

        # Organization-wide grants
        cls.manager_a = make_user("manager.a@acme.test", organization=cls.acme)
        assign(cls.manager_a, "warehouse_manager", organization=cls.acme)

        cls.viewer_a = make_user("viewer.a@acme.test", organization=cls.acme)
        assign(cls.viewer_a, "management_viewer", organization=cls.acme)

        cls.manager_b = make_user("manager.b@globex.test", organization=cls.globex)
        assign(cls.manager_b, "warehouse_manager", organization=cls.globex)

        # Warehouse-scoped grant
        cls.operator_a1 = make_user("operator.a1@acme.test", organization=cls.acme)
        assign(cls.operator_a1, "warehouse_operator", warehouse=cls.wh_a1)

        cls.org_admin_a = make_org_admin(cls.acme, "orgadmin.a@acme.test")

        # A user with no assignments at all
        cls.nobody = make_user("nobody@acme.test", organization=cls.acme)

    # -- deny by default ---------------------------------------------------
    def test_user_without_assignments_has_no_permissions(self):
        service = AuthorizationService(self.nobody)
        self.assertFalse(service.has_permission("inventory.view"))
        self.assertFalse(service.has_permission("inventory.view", organization=self.acme))
        self.assertEqual(service.effective_permission_codes(), set())
        self.assertEqual(service.accessible_organization_ids(), set())
        self.assertEqual(service.accessible_warehouse_ids(), set())

    def test_inactive_user_has_no_permissions(self):
        self.nobody.is_active = False
        self.nobody.save(update_fields=["is_active"])
        service = AuthorizationService(self.nobody)
        self.assertFalse(service.has_permission("inventory.view", organization=self.acme))
        self.assertEqual(service.accessible_organization_ids(), set())

    def test_expired_assignment_grants_nothing(self):
        temp = make_user("temp@acme.test", organization=self.acme)
        assign(
            temp,
            "inventory_controller",
            organization=self.acme,
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        self.assertFalse(AuthorizationService(temp).has_permission("inventory.adjust", organization=self.acme))

    def test_inactive_assignment_grants_nothing(self):
        temp = make_user("inactive-assign@acme.test", organization=self.acme)
        assign(temp, "inventory_controller", organization=self.acme, is_active=False)
        self.assertFalse(
            AuthorizationService(temp).has_permission("inventory.adjust", organization=self.acme)
        )

    def test_platform_admin_is_unrestricted(self):
        service = AuthorizationService(self.platform_admin)
        self.assertTrue(service.is_platform_admin)
        self.assertTrue(service.has_permission("configuration.manage", organization=self.globex))
        self.assertIn(self.wh_b1.id, service.accessible_warehouse_ids())
        self.assertIn(self.acme.id, service.accessible_organization_ids())
        self.assertIn(self.globex.id, service.accessible_organization_ids())

    # -- permission content -------------------------------------------------
    def test_role_permissions_are_scoped_to_the_organization(self):
        service = AuthorizationService(self.manager_a)
        self.assertTrue(service.has_permission("inventory.adjust", organization=self.acme))
        # Same permission, different tenant → denied.
        self.assertFalse(service.has_permission("inventory.adjust", organization=self.globex))

    def test_unscoped_check_reports_any_scope(self):
        """A scope-less check answers "does the user hold this anywhere?"."""
        service = AuthorizationService(self.operator_a1)
        self.assertTrue(service.has_permission("inventory.create"))
        self.assertFalse(service.has_permission("inventory.approve_adjustment"))

    # -- warehouse scope ----------------------------------------------------
    def test_warehouse_scoped_grant_does_not_imply_organization_authority(self):
        service = AuthorizationService(self.operator_a1)
        # Inside the granted warehouse → allowed
        self.assertTrue(service.has_permission("inventory.create", warehouse=self.wh_a1))
        # Another warehouse in the same organization → denied
        self.assertFalse(service.has_permission("inventory.create", warehouse=self.wh_a2))
        # Organization-level question → denied (grant is warehouse-limited)
        self.assertFalse(service.has_permission("inventory.create", organization=self.acme))

    def test_organization_wide_grant_covers_every_warehouse(self):
        service = AuthorizationService(self.manager_a)
        for warehouse in (self.wh_a1, self.wh_a2):
            self.assertTrue(service.has_permission("inventory.view", warehouse=warehouse))
        # …but not warehouses of another organization
        self.assertFalse(service.has_permission("inventory.view", warehouse=self.wh_b1))

    def test_accessible_warehouses_are_limited_to_scope(self):
        self.assertEqual(
            AuthorizationService(self.operator_a1).accessible_warehouse_ids(), {self.wh_a1.id}
        )
        self.assertEqual(
            AuthorizationService(self.manager_a).accessible_warehouse_ids(),
            {self.wh_a1.id, self.wh_a2.id},
        )
        self.assertEqual(
            AuthorizationService(self.manager_b).accessible_warehouse_ids(), {self.wh_b1.id}
        )

    def test_can_access_helpers(self):
        service = AuthorizationService(self.operator_a1)
        self.assertTrue(service.can_access_organization(self.acme))
        self.assertFalse(service.can_access_organization(self.globex))
        self.assertTrue(service.can_access_warehouse(self.wh_a1))
        self.assertFalse(service.can_access_warehouse(self.wh_a2))

    # -- queryset scoping ---------------------------------------------------
    def test_scope_queryset_filters_by_organization(self):
        from apps.warehouses.models import Warehouse

        scoped = AuthorizationService(self.manager_a).scope_queryset(
            Warehouse.objects.all(), organization_field="branch__organization"
        )
        self.assertEqual(set(scoped.values_list("code", flat=True)), {"WH-A1", "WH-A2"})

        empty = AuthorizationService(self.nobody).scope_queryset(Warehouse.objects.all())
        self.assertEqual(empty.count(), 0)

    # -- delegation / escalation -------------------------------------------
    def test_cannot_grant_role_without_assignment_manage(self):
        service = AuthorizationService(self.manager_a)
        allowed, reason = service.can_grant_role(role("warehouse_operator"), organization=self.acme)
        self.assertFalse(allowed)
        self.assertIn("manage role assignments", reason)

    def test_cannot_grant_platform_role(self):
        service = AuthorizationService(self.org_admin_a)
        allowed, reason = service.can_grant_role(role("super_admin"), organization=self.acme)
        self.assertFalse(allowed)
        self.assertIn("Platform roles", reason)

    def test_cannot_grant_role_above_own_level(self):
        # org admin is level 60; warehouse manager is level 80
        service = AuthorizationService(self.org_admin_a)
        allowed, reason = service.can_grant_role(role("warehouse_manager"), organization=self.acme)
        self.assertFalse(allowed)
        self.assertTrue(
            "higher authority" in reason or "permissions you do not hold" in reason, reason
        )

    def test_cannot_grant_permissions_not_held(self):
        """A level-60 admin without configuration.manage cannot grant a role that has it."""
        narrow = make_user("narrow@acme.test", organization=self.acme)
        custom = make_custom_role(
            self.acme,
            "narrow_admin",
            ["assignment.manage", "role.manage", "user.view", "warehouse.view"],
            level=60,
        )
        assign(narrow, custom, organization=self.acme)

        target_role = make_custom_role(
            self.acme, "super_duper", ["configuration.manage"], level=50
        )
        allowed, reason = AuthorizationService(narrow).can_grant_role(
            target_role, organization=self.acme
        )
        self.assertFalse(allowed)
        self.assertIn("permissions you do not hold", reason)

    def test_can_grant_lower_authority_role_with_full_permission_cover(self):
        service = AuthorizationService(self.org_admin_a)
        allowed, reason = service.can_grant_role(role("warehouse_operator"), organization=self.acme)
        self.assertTrue(allowed, reason)

    def test_cannot_grant_role_in_another_organization(self):
        service = AuthorizationService(self.org_admin_a)
        allowed, _ = service.can_grant_role(role("warehouse_operator"), organization=self.globex)
        self.assertFalse(allowed)

    def test_platform_admin_can_grant_anything(self):
        service = AuthorizationService(self.platform_admin)
        allowed, _ = service.can_grant_role(role("super_admin"), organization=None)
        self.assertTrue(allowed)

    # -- user management guard ---------------------------------------------
    def test_cannot_manage_user_of_another_organization(self):
        allowed, reason = AuthorizationService(self.org_admin_a).can_manage_user(self.manager_b)
        self.assertFalse(allowed)
        self.assertIn("cannot access", reason)

    def test_cannot_manage_platform_account(self):
        allowed, reason = AuthorizationService(self.org_admin_a).can_manage_user(
            self.platform_admin
        )
        self.assertFalse(allowed)
        self.assertIn("platform", reason.lower())

    def test_cannot_manage_higher_ranked_user(self):
        # manager_a is level 80, org_admin_a is level 60
        allowed, reason = AuthorizationService(self.org_admin_a).can_manage_user(self.manager_a)
        self.assertFalse(allowed)
        self.assertIn("higher authority", reason)

    def test_can_manage_lower_ranked_user_in_scope(self):
        allowed, reason = AuthorizationService(self.org_admin_a).can_manage_user(self.operator_a1)
        self.assertTrue(allowed, reason)

    def test_users_may_manage_themselves(self):
        allowed, _ = AuthorizationService(self.operator_a1).can_manage_user(self.operator_a1)
        self.assertTrue(allowed)

    # -- highest level -------------------------------------------------------
    def test_highest_level(self):
        self.assertEqual(AuthorizationService(self.platform_admin).highest_level(), 100)
        self.assertEqual(AuthorizationService(self.manager_a).highest_level(), 80)
        self.assertEqual(AuthorizationService(self.nobody).highest_level(), 0)


class AssignmentIntegrityTests(TestCase):
    """The unique constraint keeps scope bookkeeping deterministic."""

    def test_duplicate_assignment_in_same_scope_is_rejected(self):
        from django.db import IntegrityError, transaction

        org = make_organization("DUP")
        user = make_user("dup@example.com", organization=org)
        assign(user, "management_viewer", organization=org)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RoleAssignment.objects.create(
                user=user, role=role("management_viewer"), organization=org
            )
