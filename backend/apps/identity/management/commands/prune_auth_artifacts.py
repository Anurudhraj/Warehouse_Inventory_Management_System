"""``manage.py prune_auth_artifacts`` — retention for authentication metadata.

Removes expired one-time tokens, revoked/expired session rows and old login
attempts. Run from Celery beat (or cron) in production.

    python manage.py prune_auth_artifacts
    python manage.py prune_auth_artifacts --login-attempt-days 180
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.identity.models import LoginAttempt, OneTimeToken, UserSession


class Command(BaseCommand):
    help = "Delete expired authentication artefacts (tokens, sessions, attempts)."

    def add_arguments(self, parser):
        parser.add_argument("--login-attempt-days", type=int, default=90)

    def handle(self, *args, **options):
        now = timezone.now()
        tokens = OneTimeToken.objects.filter(expires_at__lt=now).delete()[0]
        sessions = UserSession.objects.filter(
            expires_at__lt=now - timezone.timedelta(days=7)
        ).delete()[0]
        attempts = LoginAttempt.objects.filter(
            created_at__lt=now - timezone.timedelta(days=options["login_attempt_days"])
        ).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {tokens} token(s), {sessions} session(s), {attempts} login attempt(s)."
            )
        )
