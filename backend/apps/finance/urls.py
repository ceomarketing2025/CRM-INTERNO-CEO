from django.urls import path
from . import views
app_name = "finance"
urlpatterns = [path("", views.finance_dashboard, name="dashboard"), path("new/", views.transaction_create, name="create"), path("<int:pk>/edit/", views.transaction_edit, name="edit")]
