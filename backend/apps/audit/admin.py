from django.contrib import admin
from .models import ActivityLog
@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "module", "action", "entity_type", "entity_id")
    list_filter = ("module", "action")
    search_fields = ("description", "user__email")
    readonly_fields = ("user", "module", "action", "entity_type", "entity_id", "description", "metadata", "created_at")
