"""Core platform endpoints: health & readiness probes."""

from __future__ import annotations

import logging
import time

from django import __version__ as django_version
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("apps.core.health")


class BaseHealthView(APIView):
    """Health probes: no auth, no CSRF, no throttling — safe to hit from
    orchestrators (Kubernetes, load balancers, uptime monitors)."""

    authentication_classes: list = []
    permission_classes = [AllowAny]


def _check_database() -> tuple[bool, str]:
    try:
        start = time.perf_counter()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        latency_ms = (time.perf_counter() - start) * 1000.0
        return True, f"{latency_ms:.1f}ms"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False, "unavailable"


def _check_redis() -> tuple[bool, str]:
    try:
        from django_redis import get_redis_connection

        start = time.perf_counter()
        redis = get_redis_connection("default")
        if not redis.ping():
            return False, "unavailable"
        latency_ms = (time.perf_counter() - start) * 1000.0
        return True, f"{latency_ms:.1f}ms"
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        return False, "unavailable"


class ApiIndexView(BaseHealthView):
    """Self-describing root of the versioned API.

    Lists the API version and every mounted domain module with its base
    path, so integrators can discover the surface without reading the docs.
    """

    @extend_schema(
        summary="API index",
        description="Version information and the list of mounted domain modules.",
        responses={
            200: inline_serializer(
                name="ApiIndex",
                fields={
                    "version": serializers.CharField(),
                    "environment": serializers.CharField(),
                    "modules": serializers.ListField(
                        child=serializers.DictField(child=serializers.CharField())
                    ),
                },
            )
        },
        tags=["platform"],
    )
    def get(self, request):
        return Response(
            {
                "version": settings.SPECTACULAR_SETTINGS["VERSION"],
                "environment": settings.ENVIRONMENT,
                "endpoints": {
                    "health": request.build_absolute_uri("health/"),
                    "schema": request.build_absolute_uri("schema/"),
                    "docs": request.build_absolute_uri("docs/"),
                },
                "modules": [
                    {"name": module, "path": request.build_absolute_uri(f"{module}/")}
                    for module in settings.DOMAIN_MODULES
                ],
            }
        )


class LivenessView(BaseHealthView):
    @extend_schema(
        summary="Liveness probe",
        description="Returns immediately if the process is alive (no dependency checks).",
        responses={
            200: inline_serializer(name="Liveness", fields={"status": serializers.CharField()})
        },
        tags=["health"],
    )
    def get(self, request):
        return Response({"status": "alive"})


class ReadinessView(BaseHealthView):
    @extend_schema(
        summary="Readiness probe",
        description="Checks that the API can serve traffic (database reachable).",
        responses={
            200: inline_serializer(
                name="Readiness",
                fields={
                    "status": serializers.CharField(),
                    "checks": serializers.DictField(child=serializers.JSONField()),
                },
            ),
            503: None,
        },
        tags=["health"],
    )
    def get(self, request):
        db_ok, db_detail = _check_database()
        healthy = db_ok
        return Response(
            {
                "status": "ready" if healthy else "degraded",
                "checks": {"database": {"status": "ok" if db_ok else "error", "detail": db_detail}},
            },
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class HealthView(BaseHealthView):
    @extend_schema(
        summary="Full health check",
        description="Verifies connectivity to all synchronous dependencies (PostgreSQL, Redis).",
        responses={
            200: inline_serializer(
                name="Health",
                fields={
                    "status": serializers.CharField(),
                    "environment": serializers.CharField(),
                    "version": serializers.CharField(),
                    "checks": serializers.DictField(child=serializers.JSONField()),
                },
            ),
            503: None,
        },
        tags=["health"],
    )
    def get(self, request):
        db_ok, db_detail = _check_database()
        redis_ok, redis_detail = _check_redis()

        checks = {
            "database": {"status": "ok" if db_ok else "error", "detail": db_detail},
            "redis": {"status": "ok" if redis_ok else "error", "detail": redis_detail},
        }
        healthy = db_ok and redis_ok

        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "environment": settings.ENVIRONMENT,
                "version": settings.SPECTACULAR_SETTINGS["VERSION"],
                "django_version": django_version,
                "checks": checks,
            },
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )
