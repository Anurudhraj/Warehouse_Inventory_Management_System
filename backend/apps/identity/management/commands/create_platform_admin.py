"""``manage.py create_platform_admin`` — bootstrap the first platform administrator.

Creates (or promotes) a superuser with an optional MFA policy flag. Intended
for initial deployment and break-glass recovery:

    python manage.py create_platform_admin \\
        --email admin@example.com --first-name Ada --last-name Lovelace
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.identity.models import User


class Command(BaseCommand):
    help = "Create or promote a platform administrator (superuser)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", default="Platform")
        parser.add_argument("--last-name", default="Administrator")
        parser.add_argument(
            "--password",
            default=None,
            help="Password to set. Omit to be prompted securely (recommended).",
        )
        parser.add_argument(
            "--require-mfa",
            action="store_true",
            help="Mark the account as requiring MFA enrolment.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]
        if not password:
            from getpass import getpass

            password = getpass("Password: ")
            if password != getpass("Password (again): "):
                raise CommandError("Passwords do not match.")
        if len(password) < 12:
            raise CommandError("Use at least 12 characters.")

        with transaction.atomic():
            user = User.objects.filter(email=email).first()
            created = user is None
            if created:
                user = User.objects.create_superuser(
                    email=email,
                    password=password,
                    first_name=options["first_name"],
                    last_name=options["last_name"],
                )
            else:
                user.is_superuser = True
                user.is_staff = True
                user.is_active = True
                user.status = User.Status.ACTIVE
                user.set_password(password)

            user.mfa_required = bool(options["require_mfa"])
            user.mark_email_verified()
            user.save()

        verb = "created" if created else "promoted"
        self.stdout.write(self.style.SUCCESS(f"Platform administrator {verb}: {user.email}"))
