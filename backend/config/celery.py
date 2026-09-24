"""Celery application.

The app is exposed as ``config.celery_app`` from ``config/__init__.py``
and configured entirely from Django settings with the ``CELERY_``
prefix. Tasks live in ``apps/<module>/tasks.py`` and are discovered
automatically.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("wims")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - operational helper
    print(f"Request: {self.request!r}")
