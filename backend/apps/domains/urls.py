from django.urls import path
from . import views
app_name = "domains"
urlpatterns = [path("", views.domain_list, name="list"), path("new/", views.domain_create, name="create"), path("<int:pk>/edit/", views.domain_edit, name="edit")]
