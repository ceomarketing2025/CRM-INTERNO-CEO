from django.urls import path
from . import views

app_name = "reminders"

urlpatterns = [
    path("", views.reminder_list, name="list"),
    path("new/", views.reminder_create, name="create"),
    path("<int:pk>/edit/", views.reminder_edit, name="edit"),
    path("<int:pk>/done/", views.reminder_done, name="done"),
    path("<int:pk>/cancel/", views.reminder_cancel, name="cancel"),
    path("<int:pk>/google/retry/", views.reminder_retry_google, name="retry_google"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("meetings/", views.meeting_list, name="meeting_list"),
    path("meetings/new/", views.meeting_create, name="meeting_create"),
    path("meetings/<int:pk>/edit/", views.meeting_edit, name="meeting_edit"),
    path("meetings/<int:pk>/google/retry/", views.meeting_retry_google, name="meeting_retry_google"),
    path("google/connect/", views.google_connect, name="google_connect"),
    path("google/callback/", views.google_callback, name="google_callback"),
    path("google/disconnect/", views.google_disconnect, name="google_disconnect"),
    path("google/sync/", views.google_sync_now, name="google_sync_now"),
]
