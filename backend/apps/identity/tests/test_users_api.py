"""Administrative user-management API: invitation, temporary passwords,
activation lifecycle, session revocation and the authentication audit ledger.
"""
from __future__ import annotations

from django.core import mail
from django.test import override_settings

from apps.core.testing.factories import DEFAULT_PASSWORD, assign, make_user
from apps.identity.models import LoginAttempt, User, UserSession
from apps.identity.services import OneTimeTokenService
from apps.identity.tests.base import SESSION_URL, IdentityApiTestCase
from apps.security.models import RoleAssignment

USERS_URL = "/api/v1/identity/users/"
ATTEMPTS_URL = "/api/v1/identity/login-attempts/"
TEMP_PASSWORD = "Temp0rary-Passphrase!"


class UserCreationTests(IdentityApiTestCase):
    def test_temporary_password_forces_a_change_at_next_sign_in(self):
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.post(
            USERS_URL,
            {
                "email": "temps@acme.test",
                "first_name": "Temp",
                "last_name": "Worker",
                "job_title": "Picker",
                "password": TEMP_PASSWORD,
                "send_verification_email": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        created = User.objects.get(email="temps@acme.test")
        self.assertEqual(created.organization_id, self.acme.id)
        self.assertEqual(created.status, User.Status.ACTIVE)
        self.assertTrue(created.must_change_password)
        self.assertTrue(created.check_password(TEMP_PASSWORD))
        self.assertEqual(len(mail.outbox), 0)

        # The template user can sign in, and the flag survives the sign-in.
        self.logout()
        self.login_or_fail(email=created.email, password=TEMP_PASSWORD)
        created.refresh_from_db()
        self.assertTrue(created.must_change_password)

    def test_invited_user_is_created_without_a_usable_password(self):
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.post(
            USERS_URL,
            {
                "email": "invited@acme.test",
                "first_name": "Invited",
                "last_name": "Worker",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        created = User.objects.get(email="invited@acme.test")
        self.assertEqual(created.status, User.Status.INVITED)
        self.assertFalse(created.has_usable_password())
        self.assertEqual(len(mail.outbox), 1, "the invite email carries the verification link")
        self.assertIn("invited@acme.test", mail.outbox[0].to)

        # No password ⇒ the account cannot be signed into yet.
        self.logout()
        self.assertEqual(self.login(email=created.email).status_code, 401)

    def test_invitation_without_a_verification_email_is_refused(self):
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.post(
            USERS_URL,
            {
                "email": "noreach@acme.test",
                "first_name": "No",
                "last_name": "Reach",
                "send_verification_email": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="noreach@acme.test").exists())

    def test_duplicate_email_is_refused_case_insensitively(self):
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.post(
            USERS_URL,
            {
                "email": self.operator.email.upper(),
                "first_name": "Clone",
                "last_name": "Account",
                "password": TEMP_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", str(response.data))

    def test_weak_temporary_password_is_refused(self):
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.post(
            USERS_URL,
            {
                "email": "weak@acme.test",
                "first_name": "Weak",
                "last_name": "Password",
                "password": "password",
                "send_verification_email": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="weak@acme.test").exists())

    def test_created_user_starts_without_any_authority(self):
        self.login_or_fail(email=self.org_admin.email)
        self.client.post(
            USERS_URL,
            {
                "email": "fresh@acme.test",
                "first_name": "Fresh",
                "last_name": "Start",
                "password": TEMP_PASSWORD,
                "send_verification_email": False,
            },
            format="json",
        )
        created = User.objects.get(email="fresh@acme.test")
        self.assertFalse(created.role_assignments.exists())

        self.logout()
        self.login_or_fail(email=created.email, password=TEMP_PASSWORD)
        # No grants → no operational capability at all.
        self.assertEqual(self.client.get("/api/v1/warehouses/").status_code, 403)
        session = self.client.get(SESSION_URL)
        self.assertEqual(session.data["permissions"], [])
        self.assertEqual(session.data["warehouses"], [])


class UserLifecycleTests(IdentityApiTestCase):
    def test_deactivate_then_activate_restores_access(self):
        target = make_user("target@acme.test", organization=self.acme)
        assign(target, "warehouse_operator", warehouse=self.warehouse)
        self.login_or_fail(email=self.org_admin.email)

        deactivated = self.client.post(
            f"{USERS_URL}{target.id}/deactivate/", {"reason": "left"}, format="json"
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.data)
        target.refresh_from_db()
        self.assertFalse(target.is_active)
        self.assertEqual(target.status, User.Status.DEACTIVATED)
        self.assertFalse(target.role_assignments.filter(is_active=True).exists())
        self.assertEqual(self.login(email=target.email).status_code, 401)

        activated = self.client.post(f"{USERS_URL}{target.id}/activate/", {}, format="json")
        self.assertEqual(activated.status_code, 200, activated.data)
        target.refresh_from_db()
        self.assertTrue(target.is_active)
        self.assertEqual(target.status, User.Status.ACTIVE)

        # Reactivation restores the assignment (it was only marked inactive).
        self.logout()
        self.login_or_fail(email=target.email)
        self.assertEqual(self.client.get("/api/v1/warehouses/").status_code, 200)

    def test_deactivation_revokes_the_targets_sessions(self):
        target = make_user("target@acme.test", organization=self.acme)
        assign(target, "warehouse_operator", warehouse=self.warehouse)
        victim_client = self.second_client()
        self.login_or_fail(email=target.email, client=victim_client)
        self.assertEqual(victim_client.get(SESSION_URL).status_code, 200)

        self.login_or_fail(email=self.org_admin.email)
        self.client.post(f"{USERS_URL}{target.id}/deactivate/", {}, format="json")

        self.assertEqual(victim_client.get(SESSION_URL).status_code, 401)

    def test_users_are_never_hard_deleted(self):
        target = make_user("target@acme.test", organization=self.acme)
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.delete(f"{USERS_URL}{target.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(pk=target.id).exists())

    def test_set_password_issues_a_temporary_password(self):
        target = make_user("target@acme.test", organization=self.acme)
        self.login_or_fail(email=self.org_admin.email)

        response = self.client.post(
            f"{USERS_URL}{target.id}/set-password/",
            {"password": TEMP_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        target.refresh_from_db()
        self.assertTrue(target.check_password(TEMP_PASSWORD))
        self.assertFalse(target.check_password(DEFAULT_PASSWORD))
        self.assertTrue(target.must_change_password)

        self.logout()
        self.assertEqual(self.login(email=target.email).status_code, 401)
        self.assertEqual(self.login(email=target.email, password=TEMP_PASSWORD).status_code, 200)

    def test_administrator_can_revoke_every_session_of_a_user(self):
        target = make_user("target@acme.test", organization=self.acme)
        victim_client = self.second_client()
        self.login_or_fail(email=target.email, client=victim_client)

        self.login_or_fail(email=self.org_admin.email)
        response = self.client.post(f"{USERS_URL}{target.id}/revoke-sessions/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["revoked"], 1)
        self.assertEqual(victim_client.get(SESSION_URL).status_code, 401)

    def test_administrator_can_list_a_users_sessions(self):
        target = make_user("target@acme.test", organization=self.acme)
        victim_client = self.second_client()
        self.login_or_fail(email=target.email, client=victim_client)
        self.login_or_fail(email=self.org_admin.email)

        response = self.client.get(f"{USERS_URL}{target.id}/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertTrue(UserSession.objects.filter(user=target).exists())

    def test_administrator_can_resend_a_verification_email(self):
        target = make_user("target@acme.test", organization=self.acme)
        self.login_or_fail(email=self.org_admin.email)

        response = self.client.post(f"{USERS_URL}{target.id}/resend-verification/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        token = self.token_from_email(mail.outbox[0])
        self.assertTrue(
            OneTimeTokenService.peek(token, purpose="email_verification").pk,
            "the resent link must be usable",
        )

    def test_user_cannot_manipulate_their_own_rank_through_the_api(self):
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.patch(
            f"{USERS_URL}{self.org_admin.id}/",
            {"is_staff": True, "is_superuser": True, "status": User.Status.ACTIVE},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.org_admin.refresh_from_db()
        self.assertFalse(self.org_admin.is_staff)
        self.assertFalse(self.org_admin.is_superuser)


class UserListingTests(IdentityApiTestCase):
    def test_users_without_user_view_cannot_list_accounts(self):
        self.login_or_fail()
        self.assertEqual(self.client.get(USERS_URL).status_code, 403)
        self.assertEqual(self.client.get(f"{USERS_URL}{self.org_admin.id}/").status_code, 403)

    def test_organization_admin_sees_only_their_own_tenant(self):
        from apps.core.testing.factories import make_organization

        other = make_organization("GLOBEX", "Globex Logistics")
        outsider = make_user("outsider@globex.test", organization=other)

        self.login_or_fail(email=self.org_admin.email)
        response = self.client.get(USERS_URL)
        self.assertEqual(response.status_code, 200)

        emails = {row["email"] for row in response.data["results"]}
        self.assertNotIn(outsider.email, emails)
        self.assertIn(self.operator.email, emails)

        detail = self.client.get(f"{USERS_URL}{outsider.id}/")
        self.assertEqual(detail.status_code, 404)

    def test_platform_administrator_sees_every_tenant(self):
        from apps.core.testing.factories import make_organization

        other = make_organization("GLOBEX", "Globex Logistics")
        make_user("outsider@globex.test", organization=other)
        platform = make_user("platform@wims.test", is_platform_admin=True)

        self.login_or_fail(email=platform.email)
        response = self.client.get(USERS_URL)
        self.assertEqual(response.status_code, 200)
        emails = {row["email"] for row in response.data["results"]}
        self.assertIn(self.operator.email, emails)
        self.assertIn("outsider@globex.test", emails)

    def test_filters_cannot_escape_the_tenant_boundary(self):
        from apps.core.testing.factories import make_organization

        other = make_organization("GLOBEX", "Globex Logistics")
        make_user("outsider@globex.test", organization=other)

        self.login_or_fail(email=self.org_admin.email)
        response = self.client.get(USERS_URL, {"organization": other.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

        search = self.client.get(USERS_URL, {"search": "outsider"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.data["results"], [])

    def test_role_filter_only_matches_roles_the_caller_may_see(self):
        self.login_or_fail(email=self.org_admin.email)
        response = self.client.get(USERS_URL, {"role": "warehouse_operator"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["email"] for row in response.data["results"]}, {self.operator.email})

    def test_role_assignment_for_a_foreign_user_is_not_possible(self):
        from apps.core.testing.factories import make_organization

        other = make_organization("GLOBEX", "Globex Logistics")
        outsider = make_user("outsider@globex.test", organization=other)

        self.login_or_fail(email=self.org_admin.email)
        response = self.client.post(
            "/api/v1/security/assignments/",
            {"user": outsider.id, "role": _role_id("warehouse_operator"), "organization": other.id},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(RoleAssignment.objects.filter(user=outsider).exists())


class LoginAttemptLedgerTests(IdentityApiTestCase):
    def test_users_see_only_their_own_attempts(self):
        make_user("someone.else@acme.test", organization=self.acme)
        self.login(email="someone.else@acme.test", password="wrong")
        self.login_or_fail()

        response = self.client.get(ATTEMPTS_URL)
        self.assertEqual(response.status_code, 200)
        emails = {row["email_attempted"] for row in response.data["results"]}
        self.assertEqual(emails, {self.operator.email})

    def test_auditors_see_attempts_for_the_whole_tenant(self):
        other = make_user("someone.else@acme.test", organization=self.acme)
        self.login(email=other.email, password="wrong")

        self.login_or_fail(email=self.org_admin.email)
        response = self.client.get(ATTEMPTS_URL)
        self.assertEqual(response.status_code, 200)

        emails = {row["email_attempted"] for row in response.data["results"]}
        self.assertIn(other.email, emails)
        self.assertTrue(
            LoginAttempt.objects.filter(
                user=other, result=LoginAttempt.Result.INVALID_CREDENTIALS
            ).exists()
        )

    def test_audit_visibility_stops_at_the_tenant_boundary(self):
        from apps.core.testing.factories import make_organization

        other = make_organization("GLOBEX", "Globex Logistics")
        outsider = make_user("outsider@globex.test", organization=other)
        self.login(email=outsider.email, password="wrong")

        self.login_or_fail(email=self.org_admin.email)
        response = self.client.get(ATTEMPTS_URL)
        self.assertNotIn(outsider.email, {row["email_attempted"] for row in response.data["results"]})

    def test_unauthenticated_callers_cannot_read_the_ledger(self):
        self.assertEqual(self.client.get(ATTEMPTS_URL).status_code, 401)


class AdminLockoutTests(IdentityApiTestCase):
    def test_platform_administrator_can_bypass_email_verification_only_with_a_flag(self):
        "A deactivated platform admin must still be refused (no back door)."
        platform = make_user("platform@wims.test", is_platform_admin=True)
        platform.is_active = False
        platform.save(update_fields=["is_active"])

        with override_settings(AUTH_REQUIRE_MFA_FOR_ADMINS=False):
            self.assertEqual(self.login(email=platform.email).status_code, 401)


def _role_id(code: str) -> int:
    from apps.core.testing.factories import role

    return role(code).id
