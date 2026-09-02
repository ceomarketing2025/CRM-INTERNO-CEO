from django.urls import path
from . import views
app_name = "marketing"
urlpatterns = [path("", views.marketing_list, name="list"), path("task/new/", views.task_create, name="task_create"), path("project/<int:project_pk>/brief/", views.brief_edit, name="brief_edit")]
