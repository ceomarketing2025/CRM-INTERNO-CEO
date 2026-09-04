from django.contrib import admin
from .models import GoogleCalendarConnection, Meeting, Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "due_at", "assigned_to", "status", "google_sync_status")
    list_filter = ("status", "category", "google_sync_status", "sync_to_google")
    search_fields = ("title", "notes", "source_key")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "scheduled_at", "status", "create_google_meet", "google_sync_status")
    list_filter = ("status", "create_google_event", "create_google_meet", "google_sync_status")
    search_fields = ("title", "client__business_name", "external_attendees")


@admin.register(GoogleCalendarConnection)
class GoogleCalendarConnectionAdmin(admin.ModelAdmin):
    list_display = ("account_email", "calendar_id", "status", "last_synced_at", "connected_by")
    readonly_fields = ("encrypted_credentials", "last_synced_at", "created_at", "updated_at")
