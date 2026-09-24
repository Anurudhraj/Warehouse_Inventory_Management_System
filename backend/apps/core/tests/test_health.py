"""Health endpoint tests (external dependencies are mocked)."""

from unittest import mock

from django.test import override_settings
from rest_framework.test import APITestCase


class LivenessTests(APITestCase):
    def test_liveness_returns_ok(self):
        response = self.client.get("/api/v1/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")
        self.assertIn("X-Request-ID", response.headers)


class HealthTests(APITestCase):
    def _mock_redis_ok(self):
        redis = mock.Mock()
        redis.ping.return_value = True
        return mock.patch("django_redis.get_redis_connection", return_value=redis)

    def test_health_ok_when_dependencies_healthy(self):
        with self._mock_redis_ok():
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["checks"]["database"]["status"], "ok")
        self.assertEqual(body["checks"]["redis"]["status"], "ok")
        self.assertEqual(body["version"], "v1")

    def test_health_degraded_when_redis_down(self):
        with mock.patch("django_redis.get_redis_connection", side_effect=ConnectionError("boom")):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["checks"]["redis"]["status"], "error")

    def test_readiness_checks_database(self):
        response = self.client.get("/api/v1/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"]["database"]["status"], "ok")


class ErrorHandlingTests(APITestCase):
    def test_unknown_api_route_returns_json_404(self):
        response = self.client.get("/api/v1/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json()["error"]["code"], "not_found")

    @override_settings(ROOT_URLCONF="config.urls")
    def test_request_id_header_echoed(self):
        response = self.client.get("/api/v1/health/live/", HTTP_X_REQUEST_ID="abc123")
        self.assertEqual(response.headers["X-Request-ID"], "abc123")


class ApiVersioningTests(APITestCase):
    def test_openapi_schema_is_served(self):
        response = self.client.get("/api/v1/schema/")
        self.assertEqual(response.status_code, 200)
