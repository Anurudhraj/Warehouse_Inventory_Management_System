"""Shared pagination classes."""
from __future__ import annotations

from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """Default list pagination: 25 per page, client-selectable up to 200."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


class LargePagination(StandardPagination):
    """For high-volume ledgers (login attempts, audit entries, stock movements)."""

    page_size = 100
    max_page_size = 500


class EnvelopePagination(PageNumberPagination):
    """Pagination whose envelope also reports the applied page size."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("num_pages", self.page.paginator.num_pages),
                    ("page", self.page.number),
                    ("page_size", self.get_page_size(self.request)),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("results", data),
                ]
            )
        )
