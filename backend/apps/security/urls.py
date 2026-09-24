"""RBAC routes — mounted at ``/api/v1/security/``.

    /permissions/                     permission registry (read-only)
    /permissions/grouped/             registry grouped by module
    /roles/                           roles (system + organization custom)
    /roles/<id>/permissions/          replace a role's permission set
    /roles/grantable/                 roles the caller may grant
    /assignments/                     role assignments (user ↔ role ↔ scope)
    /assignments/for-user/?user=<id>  everything one user has been granted
    /me/permissions/                  effective access for the caller
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.security.views import (
    EffectivePermissionsView,
    PermissionViewSet,
    RoleAssignmentViewSet,
    RoleViewSet,
)

app_name = "security"

router = DefaultRouter()
router.register("permissions", PermissionViewSet, basename="permission")
router.register("roles", RoleViewSet, basename="role")
router.register("assignments", RoleAssignmentViewSet, basename="assignment")

urlpatterns = [
    path("me/permissions/", EffectivePermissionsView.as_view(), name="effective-permissions"),
    path("", include(router.urls)),
]
