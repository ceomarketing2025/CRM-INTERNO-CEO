from django.urls import path
from . import views

app_name = "audit"

urlpatterns = [
    path("projects/", views.project_audit, name="projects"),
    path("projects/<int:pk>/check/", views.project_audit_check, name="project_check"),
    path("subscriptions/", views.subscription_audit, name="subscriptions"),
    path("subscriptions/<int:pk>/check/", views.subscription_audit_check, name="subscription_check"),
    path("management-tasks/", views.management_task_list, name="management_tasks"),
    path("management-tasks/new/", views.management_task_create, name="management_task_create"),
    path("management-tasks/<int:pk>/edit/", views.management_task_edit, name="management_task_edit"),
    path("management-tasks/<int:pk>/status/", views.management_task_status, name="management_task_status"),
    path("management-tasks/options/", views.management_task_options, name="management_task_options"),
    path("logs/", views.log_list, name="logs"),
]
