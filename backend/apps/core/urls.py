"""Core platform API routes, mounted at the /api/v1/ root."""

from django.urls import path

from apps.core import views

urlpatterns = [
    path("", views.ApiIndexView.as_view(), name="api-index"),
    path("health/", views.HealthView.as_view(), name="health"),
    path("health/live/", views.LivenessView.as_view(), name="health-live"),
    path("health/ready/", views.ReadinessView.as_view(), name="health-ready"),
]
