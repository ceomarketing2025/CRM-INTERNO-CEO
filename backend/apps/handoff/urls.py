from django.urls import path
from . import views
app_name = "handoff"
urlpatterns = [path("project/<int:project_pk>/", views.summary, name="summary")]
