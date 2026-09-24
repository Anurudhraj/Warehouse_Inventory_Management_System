"""Warehouse & Inventory Management System — Django project package.

Importing this package makes the Celery app available so that
``@shared_task`` decorators bind to it as soon as Django starts.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
