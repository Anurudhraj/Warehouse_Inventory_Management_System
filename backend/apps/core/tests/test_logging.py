"""Logging safety tests — sensitive data must never reach log storage."""

import logging

from django.test import SimpleTestCase

from apps.core.logging import RequestContextFilter, SensitiveDataFilter


class SensitiveDataFilterTests(SimpleTestCase):
    def setUp(self):
        self.filter = SensitiveDataFilter()

    def _render(self, msg, args=()):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=args,
            exc_info=None,
        )
        self.filter.filter(record)
        return record.getMessage()

    def test_redacts_key_value_secrets(self):
        rendered = self._render("connecting with password=hunter2 and token=abc123def456")
        self.assertNotIn("hunter2", rendered)
        self.assertNotIn("abc123def456", rendered)
        self.assertIn("password=***", rendered)

    def test_redacts_authorization_headers(self):
        rendered = self._render(
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        )
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", rendered)

    def test_redacts_sensitive_mapping_arguments(self):
        rendered = self._render(
            "payload %(password)s / %(sku)s", {"password": "s3cret", "sku": "SKU-1"}
        )
        self.assertNotIn("s3cret", rendered)
        self.assertIn("SKU-1", rendered)

    def test_keeps_ordinary_messages_intact(self):
        message = "replenishment task finished for warehouse WH-01"
        self.assertEqual(self._render(message), message)


class RequestContextFilterTests(SimpleTestCase):
    def test_sets_placeholder_when_no_request_context(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        RequestContextFilter().filter(record)
        self.assertEqual(record.request_id, "-")
