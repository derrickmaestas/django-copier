"""Aggregator for the v1 REST API.

Mounted at `/api/v1/` from `config/urls.py`. Each app exposes its own
`api/urls.py` (typically with a per-app DefaultRouter for its
ViewSets); we splice them in flat so resources sit directly under
`/api/v1/` rather than under per-app prefixes — `/api/v1/plans/`,
not `/api/v1/plans/plans/`.

URL-path versioning is configured globally in
`REST_FRAMEWORK["DEFAULT_VERSIONING_CLASS"]`; the `v1` segment in
`config/urls.py` is what URLPathVersioning reads to set
`request.version`.
"""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    # Per-app URL contributions. Each app's api/urls.py owns its
    # router registrations + any singleton endpoints.
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.plans.api.urls")),
    path("", include("apps.tasks.api.urls")),
    path("", include("apps.notifications.api.urls")),
    # JWT — obtain (login), refresh, verify. Session auth still works
    # for the browsable API; JWT is for clients that don't share a cookie.
    path("auth/token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    # OpenAPI schema + Swagger UI.
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]
