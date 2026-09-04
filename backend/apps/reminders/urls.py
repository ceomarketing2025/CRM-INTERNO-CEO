from django.urls import path
from . import views
app_name = "reminders"
urlpatterns = [
    path("", views.reminder_list, name="list"),
    path("new/", views.reminder_create, name="create"),
    path("<int:pk>/done/", views.reminder_done, name="done"),
    path("meetings/", views.meeting_list, name="meeting_list"),
    path("meetings/new/", views.meeting_create, name="meeting_create"),
    path("meetings/<int:pk>/edit/", views.meeting_edit, name="meeting_edit"),
]
