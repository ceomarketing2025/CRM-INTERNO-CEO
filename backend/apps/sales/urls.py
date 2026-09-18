from django.urls import path
from . import views

app_name = "sales"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/new/", views.lead_create, name="lead_create"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
]
