"""Warehouse master data (foundation).

Part 2 needs the warehouse entity so that role assignments can be scoped to a
warehouse and authorization can prove "no unauthorized warehouse access".
Deep warehouse modelling — zones, operating calendars, capacity policy,
slotting configuration — ships with the warehouse/locations part of the plan;
this model intentionally stays small and stable so later parts can extend it
without migrations that break assignments.
"""
from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.organizations.models import TimeStampedModel

CODE_VALIDATOR = RegexValidator(
    regex=r"^[A-Z0-9][A-Z0-9\-_]{1,31}$",
    message=_("Use 2-32 characters: A-Z, 0-9, dash or underscore."),
)


class Warehouse(TimeStampedModel):
    """A physical stocking location belonging to a branch."""

    class WarehouseType(models.TextChoices):
        DISTRIBUTION = "distribution", _("Distribution center")
        FULFILMENT = "fulfillment", _("Fulfilment center")
        CROSS_DOCK = "cross_dock", _("Cross-dock")
        COLD_STORAGE = "cold_storage", _("Cold storage")
        BONDED = "bonded", _("Bonded warehouse")

    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="warehouses"
    )
    code = models.CharField(max_length=32, validators=[CODE_VALIDATOR])
    name = models.CharField(max_length=150)
    warehouse_type = models.CharField(
        max_length=32, choices=WarehouseType.choices, default=WarehouseType.DISTRIBUTION
    )

    is_active = models.BooleanField(default=True)
    manager = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_warehouses",
    )

    address_line1 = models.CharField(max_length=200, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=2, blank=True, default="")

    timezone = models.CharField(max_length=64, blank=True, default="")
    #: Non-secret operating preferences (fill rate targets, cut-off times, …).
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("warehouse")
        verbose_name_plural = _("warehouses")
        ordering = ["branch__organization__name", "code"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "code"], name="unique_warehouse_code_per_branch")
        ]
        indexes = [models.Index(fields=["branch", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    @property
    def organization(self):
        """Owning organization (denormalised convenience for scoping)."""
        return self.branch.organization

    @property
    def organization_id(self) -> int:
        return self.branch.organization_id

    @property
    def effective_timezone(self) -> str:
        return self.timezone or self.branch.effective_timezone
