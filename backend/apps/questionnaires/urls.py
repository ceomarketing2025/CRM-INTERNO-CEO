from django.urls import path
from . import views
app_name = "questionnaires"
urlpatterns = [path("project/<int:project_pk>/new/", views.create_for_project, name="create_for_project"), path("<int:pk>/", views.fill, name="fill")]
