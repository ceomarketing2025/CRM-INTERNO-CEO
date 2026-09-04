from django.urls import path
from . import views

app_name = "finance"
urlpatterns = [
    path("", views.finance_dashboard, name="dashboard"),

    path("operating/", views.operating_list, name="operating_list"),
    path("operating/new/", views.operating_create, name="operating_create"),
    path("operating/<int:pk>/edit/", views.operating_edit, name="operating_edit"),
    path("operating/<int:pk>/delete/", views.operating_delete, name="operating_delete"),

    path("projects/<int:project_pk>/payment/new/", views.project_payment_create, name="project_payment_create"),
    path("project-payments/<int:pk>/delete/", views.project_payment_delete, name="project_payment_delete"),
    path("subscriptions/<int:client_plan_pk>/payment/new/", views.subscription_payment_create, name="subscription_payment_create"),
    path("subscription-payments/<int:pk>/delete/", views.subscription_payment_delete, name="subscription_payment_delete"),

    path("personnel/new/", views.personnel_create, name="personnel_create"),
    path("personnel/<int:pk>/edit/", views.personnel_edit, name="personnel_edit"),
    path("personnel/<int:pk>/delete/", views.personnel_delete, name="personnel_delete"),

    # Compatibilidad V11 y anteriores.
    path("new/", views.transaction_create, name="create"),
    path("<int:pk>/edit/", views.transaction_edit, name="edit"),
]
