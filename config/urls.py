from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("apps.core.urls", namespace="core")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("plans/", include("apps.plans.urls", namespace="plans")),
    path("tasks/", include("apps.tasks.urls", namespace="tasks")),
    path("attachments/", include("apps.attachments.urls", namespace="attachments")),
    path("notifications/", include("apps.notifications.urls", namespace="notifications")),
    path("api/v1/", include("config.api_router")),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

if settings.DEBUG:
    # Render error templates directly so we can iterate on them without
    # having to trigger a real 404/500 in dev.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns = [*debug_toolbar_urls(), *urlpatterns]
