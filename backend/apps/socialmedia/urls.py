from django.urls import path

from . import views

app_name = "socialmedia"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("new/", views.subscription_create, name="create"),
    path("<int:pk>/", views.subscription_detail, name="detail"),
    path("<int:pk>/edit/", views.subscription_edit, name="edit"),
]
