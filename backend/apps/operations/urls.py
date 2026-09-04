from django.urls import path
from . import views

app_name = "operations"
urlpatterns = [
    path("ajax/projects-for-client/", views.projects_for_client, name="projects_for_client"),
    path("general/", views.general_list, name="general_list"),
    path("general/new/", views.general_create, name="general_create"),
    path("general/<int:pk>/", views.general_detail, name="general_detail"),
    path("general/<int:pk>/edit/", views.general_edit, name="general_edit"),
    path("general/<int:pk>/quick-status/", views.general_quick_status, name="general_quick_status"),
    path("general/<int:pk>/delete/", views.general_delete, name="general_delete"),
    path("credentials/", views.credential_list, name="credential_list"),
    path("credentials/new/", views.credential_create, name="credential_create"),
    path("credentials/snapshot/", views.credential_snapshot, name="credential_snapshot"),
    path("credentials/<int:pk>/", views.credential_detail, name="credential_detail"),
    path("credentials/<int:pk>/edit/", views.credential_edit, name="credential_edit"),
    path("credentials/<int:pk>/delete/", views.credential_delete, name="credential_delete"),
    path("production/", views.production_list, name="production_list"),
    path("production/new/", views.production_create, name="production_create"),
    path("production/<int:pk>/edit/", views.production_edit, name="production_edit"),
    path("development/project/<int:project_pk>/production/", views.web_production_sheet, name="web_production_sheet"),
    path("development/project/<int:project_pk>/production/quick-toggle/", views.web_production_quick_toggle, name="web_production_quick_toggle"),
]
