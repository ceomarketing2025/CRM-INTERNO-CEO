from django.urls import path
from . import views

app_name = "finance"
urlpatterns = [
    path("", views.finance_dashboard, name="dashboard"),
    path("new/", views.transaction_create, name="create"),
    path("<int:pk>/edit/", views.transaction_edit, name="edit"),
    path("personnel/new/", views.personnel_create, name="personnel_create"),
    path("personnel/<int:pk>/edit/", views.personnel_edit, name="personnel_edit"),
    path("personnel/<int:pk>/delete/", views.personnel_delete, name="personnel_delete"),
]
