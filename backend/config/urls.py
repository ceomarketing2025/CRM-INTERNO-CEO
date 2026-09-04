from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from apps.core.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("", include("apps.dashboard.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("administration/", include("apps.administration.urls")),
    path("clients/", include("apps.clients.urls")),
    path("plans/", include("apps.plans.urls")),
    path("projects/", include("apps.projects.urls")),
    path("domains/", include("apps.domains.urls")),
    path("questionnaires/", include("apps.questionnaires.urls")),
    path("design/", include("apps.design.urls")),
    path("resources/", include("apps.resources.urls")),
    path("handoff/", include("apps.handoff.urls")),
    path("marketing/", include("apps.marketing.urls")),
    path("operations/", include("apps.operations.urls")),
    path("reminders/", include("apps.reminders.urls")),
    path("finance/", include("apps.finance.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
