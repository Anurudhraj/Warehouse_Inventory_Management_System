"""Organization (tenant) and Branch master data.

Organizations are the tenancy root: every scoped record in the system hangs off
an organization, directly or through a branch/warehouse. Branches group
warehouses into business locations (regions, cities, operating units).
"""
from __future__ import annotations

import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

CODE_VALIDATOR = RegexValidator(
    regex=r"^[A-Z0-9][A-Z0-9\-_]{1,31}$",
    message=_("Use 2-32 characters: A-Z, 0-9, dash or underscore."),
)


def default_organization_code() -> str:
    return f"ORG-{uuid.uuid4().hex[:8].upper()}"


class TimeStampedModel(models.Model):
    """Abstract base with created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    """A tenant: the top-level isolation boundary of the platform."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        ARCHIVED = "archived", _("Archived")

    code = models.CharField(
        max_length=32, unique=True, default=default_organization_code, validators=[CODE_VALIDATOR]
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    legal_name = models.CharField(max_length=200, blank=True, default="")
    tax_id = models.CharField(max_length=64, blank=True, default="")

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_active = models.BooleanField(default=True)

    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=32, blank=True, default="")

    address_line1 = models.CharField(max_length=200, blank=True, default="")
    address_line2 = models.CharField(max_length=200, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=2, blank=True, default="")

    default_currency = models.CharField(max_length=3, default="USD")
    timezone = models.CharField(max_length=64, default="UTC")
    locale = models.CharField(max_length=16, default="en")

    #: Free-form, non-secret organization preferences (feature toggles, defaults).
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or slugify(self.code) or "organization"
            slug, counter = base, 1
            while Organization.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.slug = slug
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    @property
    def is_operational(self) -> bool:
        return self.is_active and self.status == self.Status.ACTIVE


class Branch(TimeStampedModel):
    """A business location inside an organization (region, city, operating unit)."""

    class BranchType(models.TextChoices):
        HEADQUARTERS = "headquarters", _("Headquarters")
        BRANCH = "branch", _("Branch")
        DISTRIBUTION_CENTER = "distribution_center", _("Distribution center")
        CROSS_DOCK = "cross_dock", _("Cross-dock")
        DARK_STORE = "dark_store", _("Dark store")

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="branches"
    )
    code = models.CharField(max_length=32, validators=[CODE_VALIDATOR])
    name = models.CharField(max_length=150)
    branch_type = models.CharField(
        max_length=32, choices=BranchType.choices, default=BranchType.BRANCH
    )

    is_active = models.BooleanField(default=True)
    manager = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_branches",
    )

    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=32, blank=True, default="")

    address_line1 = models.CharField(max_length=200, blank=True, default="")
    address_line2 = models.CharField(max_length=200, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=2, blank=True, default="")

    timezone = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = _("branch")
        verbose_name_plural = _("branches")
        ordering = ["organization__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="unique_branch_code_per_organization"
            )
        ]
        indexes = [models.Index(fields=["organization", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.organization.code}/{self.code})"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    @property
    def effective_timezone(self) -> str:
        return self.timezone or self.organization.timezone

    def warehouse_total(self) -> int:
        """Warehouse count. Querysets may annotate ``warehouse_total`` to avoid
        an N+1 query; the serializer falls back to this method."""
        return self.warehouses.count()
