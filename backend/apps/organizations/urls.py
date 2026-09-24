"""Organization & branch routes — mounted at ``/api/v1/organizations/``.

``/api/v1/organizations/``              organizations (scoped to the caller)
``/api/v1/organizations/branches/``     branches across accessible organizations
``/api/v1/organizations/<id>/branches/``
``/api/v1/organizations/<id>/warehouses/``
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.organizations.views import BranchViewSet, OrganizationViewSet

app_name = "organizations"

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")
router.register("", OrganizationViewSet, basename="organization")

urlpatterns = [
    # Explicit, discoverable aliases for the nested collections.
    path(
        "<int:pk>/branches/",
        OrganizationViewSet.as_view({"get": "branches"}),
        name="organization-branches",
    ),
    path(
        "<int:pk>/warehouses/",
        OrganizationViewSet.as_view({"get": "warehouses"}),
        name="organization-warehouses",
    ),
    *router.urls,
]
