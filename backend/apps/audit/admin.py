from django.contrib import admin
from .models import ActivityLog, GeneralAuditCheck
@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "module", "action", "entity_type", "entity_id")
    list_filter = ("module", "action")
    search_fields = ("description", "user__email")
    readonly_fields = ("user", "module", "action", "entity_type", "entity_id", "description", "metadata", "created_at")


@admin.register(GeneralAuditCheck)
class GeneralAuditCheckAdmin(admin.ModelAdmin):
    list_display = ("project", "area", "category", "label", "is_ready", "reviewed_at", "reviewed_by")
    list_filter = ("area", "is_ready")
    search_fields = ("project__project_code", "project__client__business_name", "category", "label", "source_key")
    readonly_fields = ("source_key", "created_at", "updated_at")
