from django.urls import path
from . import views

app_name = "design"
urlpatterns = [
    path("", views.design_list, name="list"),
    path("tasks/", views.social_media_dashboard, name="tasks"),
    path("social-media/", views.social_media_dashboard, name="social_media"),  # compatibilidad histórica
    path("tasks/new/", views.design_task_create, name="task_create"),
    path("tasks/project/<int:project_pk>/", views.design_project_tasks, name="project_tasks"),
    path("tasks/project/<int:project_pk>/services/", views.design_service_manage, name="service_manage"),
    path("tasks/<int:pk>/edit/", views.design_task_edit, name="task_edit"),
    path("tasks/<int:pk>/toggle/", views.design_task_toggle, name="task_toggle"),
    path("task-cycles/<int:pk>/update/", views.design_task_cycle_update, name="task_cycle_update"),
    path("task-cycle-items/<int:pk>/update/", views.design_task_cycle_item_update, name="task_cycle_item_update"),
    path("social-media/assign/", views.social_media_assign, name="social_media_assign"),
    path("social-media/<int:pk>/", views.social_media_detail, name="social_media_detail"),
    path("social-media/<int:pk>/edit/", views.social_media_assignment_edit, name="social_media_assignment_edit"),
    path("project/<int:project_pk>/brief/", views.brief_edit, name="brief_edit"),
    path("project/<int:project_pk>/palette/new/", views.palette_create, name="palette_create"),
    path("palette/<int:pk>/", views.palette_detail, name="palette_detail"),
    path("palette/<int:pk>/pdf/", views.palette_pdf, name="palette_pdf"),
]
