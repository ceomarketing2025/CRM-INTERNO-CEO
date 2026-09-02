from django.urls import path
from . import views
app_name = "resources"
urlpatterns = [path("project/<int:project_pk>/", views.project_resources, name="project")]
