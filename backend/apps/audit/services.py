def log_activity(user, module, action, obj=None, description="", metadata=None):
    from .models import ActivityLog
    return ActivityLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        module=module,
        action=action,
        entity_type=obj.__class__.__name__ if obj else "",
        entity_id=str(getattr(obj, "pk", "")) if obj else "",
        description=description,
        metadata=metadata or {},
    )
