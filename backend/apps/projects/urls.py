from django.urls import path
from . import views
app_name = "projects"
urlpatterns = [
    path("", views.project_list, name="list"), path("new/", views.project_create, name="create"),
    path("<int:pk>/", views.project_detail, name="detail"), path("<int:pk>/edit/", views.project_edit, name="edit"),
    path("<int:pk>/assign/", views.assignment_create, name="assign"), path("<int:pk>/notes/new/", views.note_create, name="note_create"),
]
