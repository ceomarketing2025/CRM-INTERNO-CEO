from django.urls import path
from . import views

app_name = "sales"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/new/", views.lead_create, name="lead_create"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/contact/", views.add_contact, name="add_contact"),
    path("leads/<int:pk>/follow-up/", views.add_followup, name="add_followup"),
    path("leads/<int:pk>/meeting/", views.add_meeting, name="add_meeting"),
    path("leads/<int:pk>/status/", views.update_status, name="update_status"),
    path("follow-ups/", views.followup_list, name="followup_list"),
    path("follow-ups/new/", views.create_followup_from_agenda, name="create_followup_from_agenda"),
    path("follow-ups/<int:pk>/complete/", views.complete_followup, name="complete_followup"),
    path("meetings/", views.meeting_list, name="meeting_list"),
    path("meetings/new/", views.create_meeting_from_agenda, name="create_meeting_from_agenda"),
    path("meetings/<int:pk>/update/", views.update_meeting, name="update_meeting"),
]
