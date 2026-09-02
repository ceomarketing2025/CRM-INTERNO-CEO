from django.urls import path
from . import views

app_name = "design"
urlpatterns = [
    path("", views.design_list, name="list"),
    path("project/<int:project_pk>/brief/", views.brief_edit, name="brief_edit"),
    path("project/<int:project_pk>/palette/new/", views.palette_create, name="palette_create"),
    path("palette/<int:pk>/", views.palette_detail, name="palette_detail"),
    path("palette/<int:pk>/pdf/", views.palette_pdf, name="palette_pdf"),
]
