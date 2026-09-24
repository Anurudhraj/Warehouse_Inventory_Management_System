"""Authentication flow tests: sign-in, sessions, lockout, rate limiting,
password change/reset, email verification and MFA — all through the API.
"""
from __future__ import annotations

from django.conf import settings
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.testing.factories import DEFAULT_PASSWORD, make_user
from apps.identity.models import LoginAttempt, OneTimeToken, TokenPurpose, User, UserSession
from apps.identity.services import OneTimeTokenService
from apps.identity.tests.base import (
    SESSION_URL,
    IdentityApiTestCase,
    throttle_rate,
    totp_code,
)
from apps.security.totp import generate_code

STRONG_PASSWORD = "N3w-Str0ng-Passphrase!"
WEAK_PASSWORD = "password"


class SignInTests(IdentityApiTestCase):
    def test_successful_login_returns_identity_and_permissions(self):
        response = self.login_or_fail()

        self.assertFalse(response.data["mfa_required"])
        self.assertEqual(response.data["user"]["email"], self.operator.email)
        self.assertIn("warehouse.view", response.data["permissions"])
        self.assertIn("inventory.view", response.data["permissions"])

        self.operator.refresh_from_db()
        self.assertIsNotNone(self.operator.last_login_at)
        self.assertEqual(self.operator.last_login_ip, "127.0.0.1")

        tracked = self.session_of(self.operator)
        self.assertIsNotNone(tracked, "sign-in must create a tracked session")
        self.assertEqual(tracked.session_key, self.client.session.session_key)

        attempt = self.latest_attempt(self.operator)
        self.assertEqual(attempt.result, LoginAttempt.Result.SUCCESS)

    def test_email_is_case_insensitive(self):
        response = self.login(email=self.operator.email.upper())
        self.assertEqual(response.status_code, 200)

    def test_session_key_rotates_on_login(self):
        self.client.session["pre_login_marker"] = "set"
        self.client.session.save()
        before = self.client.session.session_key

        self.login_or_fail()

        self.assertNotEqual(self.client.session.session_key, before)
        self.assertNotIn("pre_login_marker", self.client.session)

    def test_wrong_password_is_generic_and_counted(self):
        response = self.login(password="not-the-password")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "authentication_failed")
        self.assertEqual(response.data["error"]["message"], "Invalid email or password.")

        self.operator.refresh_from_db()
        self.assertEqual(self.operator.failed_login_count, 1)
        self.assertEqual(
            self.latest_attempt(self.operator).result, LoginAttempt.Result.INVALID_CREDENTIALS
        )
        self.assertEqual(self.client.get(SESSION_URL).status_code, 401)

    def test_unknown_email_is_indistinguishable_from_wrong_password(self):
        unknown = self.login(email="nobody@acme.test", password="whatever")
        wrong = self.login(password="whatever")

        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(unknown.data, wrong.data)

    def test_deactivated_account_cannot_sign_in(self):
        victim = make_user("leaver@acme.test", organization=self.acme)
        self.client.force_login(self.org_admin)
        self.client.post(f"/api/v1/identity/users/{victim.id}/deactivate/", {}, format="json")
        self.logout()

        response = self.login(email=victim.email)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["message"], "Invalid email or password.")

    def test_account_is_locked_after_repeated_failures(self):
        for _ in range(settings.AUTH_MAX_FAILED_ATTEMPTS):
            self.login(password="wrong-password")
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.is_locked)

        # Even the *correct* password is refused while the lock is active.
        response = self.login(password=DEFAULT_PASSWORD)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], str(settings.AUTH_LOCKOUT_SECONDS))
        self.assertEqual(self.latest_attempt(self.operator).result, LoginAttempt.Result.LOCKED)

    def test_a_successful_login_resets_the_failure_counter(self):
        self.login(password="wrong-password")
        self.login_or_fail()
        self.operator.refresh_from_db()
        self.assertEqual(self.operator.failed_login_count, 0)
        self.assertIsNone(self.operator.locked_until)

    def test_login_attempts_are_rate_limited(self):
        with throttle_rate("login", "3/min"):
            statuses = [self.login(password="wrong").status_code for _ in range(4)]

        self.assertEqual(statuses[-1], 429)
        self.assertIn(401, statuses)

    def test_unverified_email_blocks_sign_in_when_required(self):
        self.operator.is_email_verified = False
        self.operator.save(update_fields=["is_email_verified"])

        # Default policy: verification is architectural, not enforced.
        self.assertEqual(self.login().status_code, 200)
        self.logout()

        with override_settings(AUTH_REQUIRE_EMAIL_VERIFICATION=True):
            blocked = self.login()
        self.assertEqual(blocked.status_code, 401)
        self.assertIn("verify your email", blocked.data["error"]["message"])
        self.assertEqual(
            self.latest_attempt(self.operator).result, LoginAttempt.Result.UNVERIFIED_EMAIL
        )


class SignOutTests(IdentityApiTestCase):
    def test_logout_revokes_the_tracked_session(self):
        self.login_or_fail()
        response = self.logout()

        self.assertEqual(response.status_code, 204)
        self.assertIsNotNone(self.session_of(self.operator, active=False).revoked_at)
        self.assertEqual(self.client.get(SESSION_URL).status_code, 401)

    def test_logout_without_a_session_is_idempotent(self):
        self.assertEqual(self.logout().status_code, 204)


class SessionIntrospectionTests(IdentityApiTestCase):
    def test_session_endpoint_reports_identity_and_scope(self):
        self.login_or_fail()
        response = self.client.get(SESSION_URL)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["authenticated"])
        self.assertEqual(response.data["user"]["email"], self.operator.email)
        self.assertEqual(response.data["organizations"], [self.acme.id])
        self.assertEqual(response.data["warehouses"], [self.warehouse.id])
        self.assertFalse(response.data["is_platform_admin"])

    def test_sessions_can_be_listed_and_revoked_remotely(self):
        self.login_or_fail()  # session A (self.client)
        other = self.second_client()
        self.login_or_fail(client=other)  # session B (same user, second device)

        listed = self.client.get("/api/v1/identity/sessions/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data["results"]), 2)
        self.assertTrue(any(row["is_current"] for row in listed.data["results"]))

        target = UserSession.objects.filter(user=self.operator, revoked_at__isnull=True).exclude(
            session_key=self.client.session.session_key
        ).first()
        revoked = self.client.post(f"/api/v1/identity/sessions/{target.id}/revoke/")
        self.assertEqual(revoked.status_code, 200)

        # The revoked device is signed out; the caller keeps working.
        self.assertEqual(other.get(SESSION_URL).status_code, 401)
        self.assertEqual(self.client.get(SESSION_URL).status_code, 200)

    def test_current_session_cannot_be_revoked_through_the_sessions_api(self):
        self.login_or_fail()
        current = self.session_of(self.operator)
        response = self.client.post(f"/api/v1/identity/sessions/{current.id}/revoke/")
        self.assertEqual(response.status_code, 400)

    def test_revoke_all_keeps_the_calling_session(self):
        self.login_or_fail()
        other = self.second_client()
        self.login_or_fail(client=other)

        response = self.client.post("/api/v1/identity/sessions/revoke-all/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["revoked"], 1)
        self.assertEqual(other.get(SESSION_URL).status_code, 401)
        self.assertEqual(self.client.get(SESSION_URL).status_code, 200)

    def test_an_expired_session_is_rejected_by_the_middleware(self):
        self.login_or_fail()
        tracked = self.session_of(self.operator)
        tracked.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        tracked.save(update_fields=["expires_at"])

        self.assertEqual(self.client.get(SESSION_URL).status_code, 401)

    def test_sessions_of_another_user_are_not_listed(self):
        self.login_or_fail()
        intruder = self.second_client()
        self.login_or_fail(email=self.org_admin.email, client=intruder)
        admin_session = UserSession.objects.filter(user=self.org_admin).first()

        response = self.client.post(f"/api/v1/identity/sessions/{admin_session.id}/revoke/")
        self.assertEqual(response.status_code, 404)


class PasswordChangeTests(IdentityApiTestCase):
    def test_password_change_rotates_credentials_and_signs_out_other_devices(self):
        self.login_or_fail()
        other = self.second_client()
        self.login_or_fail(client=other)

        response = self.client.post(
            "/api/v1/identity/auth/password/change/",
            {"current_password": DEFAULT_PASSWORD, "new_password": STRONG_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(STRONG_PASSWORD))
        self.assertFalse(self.operator.must_change_password)

        self.assertEqual(other.get(SESSION_URL).status_code, 401)
        self.assertEqual(self.client.get(SESSION_URL).status_code, 200)

        self.logout()
        self.assertEqual(self.login(password=DEFAULT_PASSWORD).status_code, 401)
        self.assertEqual(self.login(password=STRONG_PASSWORD).status_code, 200)

    def test_wrong_current_password_is_rejected(self):
        self.login_or_fail()
        response = self.client.post(
            "/api/v1/identity/auth/password/change/",
            {"current_password": "not-my-password", "new_password": STRONG_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(DEFAULT_PASSWORD))

    def test_weak_new_password_is_rejected_by_the_validators(self):
        self.login_or_fail()
        response = self.client.post(
            "/api/v1/identity/auth/password/change/",
            {"current_password": DEFAULT_PASSWORD, "new_password": WEAK_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", str(response.data))

    def test_password_change_requires_authentication(self):
        response = self.client.post(
            "/api/v1/identity/auth/password/change/",
            {"current_password": DEFAULT_PASSWORD, "new_password": STRONG_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 401)


class PasswordResetTests(IdentityApiTestCase):
    RESET_URL = "/api/v1/identity/auth/password/reset/"
    CONFIRM_URL = "/api/v1/identity/auth/password/reset/confirm/"
    VALIDATE_URL = "/api/v1/identity/auth/password/reset/validate/"

    def request_reset(self, email: str):
        return self.client.post(self.RESET_URL, {"email": email}, format="json")

    def test_request_for_an_unknown_email_looks_identical(self):
        unknown = self.request_reset("nobody@acme.test")
        known = self.request_reset(self.operator.email)

        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(known.status_code, 202)
        self.assertEqual(unknown.data, known.data)
        self.assertEqual(len(mail.outbox), 1, "only the existing account is emailed")

    def test_reset_link_is_single_use_and_revokes_sessions(self):
        self.login_or_fail()
        self.assertEqual(self.client.get(SESSION_URL).status_code, 200)
        self.logout()

        self.request_reset(self.operator.email)
        token = self.token_from_email(mail.outbox[0])

        validated = self.client.post(self.VALIDATE_URL, {"token": token}, format="json")
        self.assertEqual(validated.status_code, 200)
        self.assertTrue(validated.data["valid"])

        confirmed = self.client.post(
            self.CONFIRM_URL, {"token": token, "new_password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)

        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(STRONG_PASSWORD))
        self.assertIsNone(self.operator.locked_until)

        # Single use: a replay is refused.
        replay = self.client.post(
            self.CONFIRM_URL, {"token": token, "new_password": "Yet-An0ther-Password!"}, format="json"
        )
        self.assertEqual(replay.status_code, 400)

        # The old password no longer works, the new one does.
        self.assertEqual(self.login(password=DEFAULT_PASSWORD).status_code, 401)
        self.assertEqual(self.login(password=STRONG_PASSWORD).status_code, 200)

    def test_reset_revokes_active_sessions(self):
        self.login_or_fail()
        self.assertEqual(UserSession.objects.filter(user=self.operator, revoked_at__isnull=True).count(), 1)

        token = OneTimeTokenService.issue(
            self.operator, purpose=TokenPurpose.PASSWORD_RESET, ttl=600
        )
        response = self.client.post(
            self.CONFIRM_URL, {"token": token, "new_password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(SESSION_URL).status_code, 401)

    def test_a_rejected_password_does_not_burn_the_link(self):
        self.request_reset(self.operator.email)
        token = self.token_from_email(mail.outbox[0])

        rejected = self.client.post(
            self.CONFIRM_URL, {"token": token, "new_password": WEAK_PASSWORD}, format="json"
        )
        self.assertEqual(rejected.status_code, 400)

        accepted = self.client.post(
            self.CONFIRM_URL, {"token": token, "new_password": STRONG_PASSWORD}, format="json"
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)

    def test_expired_token_is_refused(self):
        token = OneTimeTokenService.issue(
            self.operator, purpose=TokenPurpose.PASSWORD_RESET, ttl=-1
        )
        self.assertEqual(
            self.client.post(self.VALIDATE_URL, {"token": token}, format="json").status_code, 400
        )
        self.assertEqual(
            self.client.post(
                self.CONFIRM_URL, {"token": token, "new_password": STRONG_PASSWORD}, format="json"
            ).status_code,
            400,
        )

    def test_password_reset_request_is_rate_limited(self):
        with throttle_rate("password_reset", "2/hour"):
            statuses = [self.request_reset(self.operator.email).status_code for _ in range(3)]

        self.assertEqual(statuses[-1], 429)
        self.assertEqual(statuses[0], 202)


class EmailVerificationTests(IdentityApiTestCase):
    VERIFY_URL = "/api/v1/identity/auth/email/verify/"
    RESEND_URL = "/api/v1/identity/auth/email/resend/"

    def test_resend_requires_authentication(self):
        self.assertEqual(self.client.post(self.RESEND_URL, {}, format="json").status_code, 401)

    def test_resend_sends_a_single_use_verification_link(self):
        self.login_or_fail()
        response = self.client.post(self.RESEND_URL, {}, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)

        token = self.token_from_email(mail.outbox[0])
        self.client.logout()

        verified = self.client.post(self.VERIFY_URL, {"token": token}, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.data["email"], self.operator.email)

        self.operator.refresh_from_db()
        self.assertTrue(self.operator.is_email_verified)
        self.assertIsNotNone(self.operator.email_verified_at)

        repeated = self.client.post(self.VERIFY_URL, {"token": token}, format="json")
        self.assertEqual(repeated.status_code, 400)

    def test_resend_is_a_no_op_when_already_verified(self):
        self.operator.mark_email_verified()
        self.operator.save(update_fields=["is_email_verified", "email_verified_at"])
        self.login_or_fail()

        response = self.client.post(self.RESEND_URL, {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_password_reset_token_cannot_verify_an_email(self):
        token = OneTimeTokenService.issue(
            self.operator, purpose=TokenPurpose.PASSWORD_RESET, ttl=600
        )
        self.assertEqual(
            self.client.post(self.VERIFY_URL, {"token": token}, format="json").status_code, 400
        )
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.is_email_verified)


class MFATests(IdentityApiTestCase):
    ENROL_URL = "/api/v1/identity/mfa/enrol/"
    CONFIRM_URL = "/api/v1/identity/mfa/confirm/"
    STATUS_URL = "/api/v1/identity/mfa/"
    DISABLE_URL = "/api/v1/identity/mfa/disable/"
    RECOVERY_URL = "/api/v1/identity/mfa/recovery-codes/"
    MFA_VERIFY_URL = "/api/v1/identity/auth/mfa/verify/"

    def enrol(self) -> tuple[str, list[str]]:
        """Enrol TOTP for the operator and return (secret, recovery codes)."""
        start = self.client.post(self.ENROL_URL, {"name": "Test phone"}, format="json")
        assert start.status_code == 201, start.data
        secret = start.data["secret"]
        self.assertIn("otpauth://totp/", start.data["otpauth_uri"])

        confirm = self.client.post(
            self.CONFIRM_URL, {"code": generate_code(secret)}, format="json"
        )
        assert confirm.status_code == 200, confirm.data
        return secret, confirm.data["recovery_codes"]

    def test_mfa_endpoints_require_authentication(self):
        for url in (self.ENROL_URL, self.CONFIRM_URL, self.STATUS_URL, self.DISABLE_URL):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    def test_enrolment_returns_secret_once_and_ten_recovery_codes(self):
        self.login_or_fail()
        secret, codes = self.enrol()

        self.assertEqual(len(codes), settings.AUTH_MFA_RECOVERY_CODE_COUNT)
        self.assertEqual(len(set(codes)), len(codes))

        status_response = self.client.get(self.STATUS_URL)
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.data["enabled"])
        self.assertTrue(status_response.data["device_name"])
        self.assertEqual(
            status_response.data["recovery_codes_remaining"], settings.AUTH_MFA_RECOVERY_CODE_COUNT
        )
        self.assertEqual(len(status_response.data["devices"]), 1)
        self.assertNotIn(secret, str(status_response.data), "the secret is never echoed back")

        self.operator.refresh_from_db()
        self.assertTrue(self.operator.has_mfa_enabled)

    def test_enrolment_requires_a_valid_totp_code(self):
        self.login_or_fail()
        self.client.post(self.ENROL_URL, {}, format="json")
        response = self.client.post(self.CONFIRM_URL, {"code": "000000"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.has_mfa_enabled)

    def test_login_requires_the_second_factor(self):
        self.login_or_fail()
        secret, _codes = self.enrol()
        self.logout()

        first = self.login()
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["mfa_required"])
        # The challenge only echoes enough to render "code sent to …".
        self.assertEqual(set(first.data["user"]), {"email", "first_name"})
        self.assertNotIn("permissions", first.data)
        challenge = first.data["challenge_token"]

        # No session exists yet: the password step alone authenticates nothing.
        self.assertEqual(self.client.get(SESSION_URL).status_code, 401)

        second = self.client.post(
            self.MFA_VERIFY_URL, {"challenge_token": challenge, "code": totp_code(secret)}, format="json"
        )
        self.assertEqual(second.status_code, 200, second.data)
        self.assertFalse(second.data["mfa_required"])
        self.assertEqual(self.client.get(SESSION_URL).status_code, 200)
        self.assertTrue(
            LoginAttempt.objects.filter(
                user=self.operator, result=LoginAttempt.Result.MFA_PASSED
            ).exists(),
            "the second factor must be recorded in the audit ledger",
        )
        self.assertEqual(self.latest_attempt(self.operator).result, LoginAttempt.Result.SUCCESS)

    def test_challenge_is_single_use_and_rejects_wrong_codes(self):
        self.login_or_fail()
        secret, _codes = self.enrol()
        self.logout()

        challenge = self.login().data["challenge_token"]
        wrong = self.client.post(
            self.MFA_VERIFY_URL, {"challenge_token": challenge, "code": "123456"}, format="json"
        )
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(self.client.get(SESSION_URL).status_code, 401)

        valid = self.client.post(
            self.MFA_VERIFY_URL, {"challenge_token": challenge, "code": totp_code(secret)}, format="json"
        )
        self.assertEqual(valid.status_code, 200)

        # Replaying the same challenge after a successful use is refused.
        replay = self.client.post(
            self.MFA_VERIFY_URL, {"challenge_token": challenge, "code": totp_code(secret)}, format="json"
        )
        self.assertEqual(replay.status_code, 401)

    def test_recovery_code_signs_in_once(self):
        self.login_or_fail()
        _secret, codes = self.enrol()
        self.logout()

        challenge = self.login().data["challenge_token"]
        response = self.client.post(
            self.MFA_VERIFY_URL,
            {"challenge_token": challenge, "code": codes[0]},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get(SESSION_URL).status_code, 200)
        self.logout()

        challenge = self.login().data["challenge_token"]
        reused = self.client.post(
            self.MFA_VERIFY_URL, {"challenge_token": challenge, "code": codes[0]}, format="json"
        )
        self.assertEqual(reused.status_code, 401)

    def test_regenerating_recovery_codes_invalidates_the_old_ones(self):
        self.login_or_fail()
        _secret, codes = self.enrol()

        regenerated = self.client.post(self.RECOVERY_URL, {}, format="json")
        self.assertEqual(regenerated.status_code, 200)
        new_codes = regenerated.data["recovery_codes"]
        self.assertNotEqual(set(codes), set(new_codes))

        self.logout()
        challenge = self.login().data["challenge_token"]
        stale = self.client.post(
            self.MFA_VERIFY_URL, {"challenge_token": challenge, "code": codes[0]}, format="json"
        )
        self.assertEqual(stale.status_code, 401)

        challenge = self.login().data["challenge_token"]
        fresh = self.client.post(
            self.MFA_VERIFY_URL, {"challenge_token": challenge, "code": new_codes[0]}, format="json"
        )
        self.assertEqual(fresh.status_code, 200)

    def test_recovery_codes_require_enabled_mfa(self):
        self.login_or_fail()
        self.assertEqual(self.client.post(self.RECOVERY_URL, {}, format="json").status_code, 400)

    def test_disable_requires_the_account_password(self):
        self.login_or_fail()
        self.enrol()

        wrong = self.client.post(self.DISABLE_URL, {"password": "not-my-password"}, format="json")
        self.assertEqual(wrong.status_code, 400)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.has_mfa_enabled)

        self.operator.refresh_from_db()
        # Use a fresh session: the failed attempt may have been counted.
        response = self.client.post(self.DISABLE_URL, {"password": DEFAULT_PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.has_mfa_enabled)

        # A disabled device no longer demands a second factor.
        self.logout()
        self.assertFalse(self.login().data["mfa_required"])

    def test_platform_admin_login_with_confirmed_device_requires_mfa(self):
        platform = make_user("platform-admin@wims.test", is_platform_admin=True)
        device_client = APIClient()
        self.login_or_fail(email=platform.email, client=device_client)
        start = device_client.post(self.ENROL_URL, {}, format="json")
        device_client.post(self.CONFIRM_URL, {"code": generate_code(start.data["secret"])}, format="json")
        device_client.post("/api/v1/identity/auth/logout/", format="json")

        response = self.login(email=platform.email, client=APIClient())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["mfa_required"])


class ProfileTests(IdentityApiTestCase):
    PROFILE_URL = "/api/v1/identity/profile/"

    def test_profile_requires_authentication(self):
        self.assertEqual(self.client.get(self.PROFILE_URL).status_code, 401)

    def test_profile_exposes_identity_scope_and_permissions(self):
        self.login_or_fail()
        response = self.client.get(self.PROFILE_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["organization"]["id"], self.acme.id)
        self.assertIn("warehouse.view", response.data["effective_permissions"])
        self.assertFalse(response.data["has_mfa_enabled"])

    def test_users_may_edit_presentation_fields_only(self):
        self.login_or_fail()
        response = self.client.patch(
            self.PROFILE_URL,
            {
                "first_name": "Renamed",
                "job_title": "Lead Operator",
                "phone": "+919999999999",
                "timezone": "Asia/Kolkata",
                # Everything below is read-only or security sensitive.
                "email": "attacker@evil.test",
                "status": User.Status.DEACTIVATED,
                "must_change_password": False,
                "is_email_verified": True,
                "mfa_required": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.operator.refresh_from_db()
        self.assertEqual(self.operator.first_name, "Renamed")
        self.assertEqual(self.operator.job_title, "Lead Operator")
        self.assertEqual(self.operator.timezone, "Asia/Kolkata")
        self.assertEqual(self.operator.email, "operator@acme.test")
        self.assertEqual(self.operator.status, User.Status.ACTIVE)
        self.assertTrue(self.operator.is_active)
        self.assertFalse(self.operator.is_email_verified)
        self.assertFalse(self.operator.mfa_required)

    def test_email_verification_cannot_be_forged_without_a_token(self):
        self.login_or_fail()
        self.client.patch(self.PROFILE_URL, {"is_email_verified": True}, format="json")
        self.operator.refresh_from_db()
        self.assertFalse(self.operator.is_email_verified)
        self.assertEqual(OneTimeToken.objects.filter(user=self.operator).count(), 0)
