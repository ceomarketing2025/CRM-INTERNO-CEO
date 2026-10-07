from datetime import timedelta
from celery import shared_task
from django.utils import timezone

from .google_calendar import calendar_is_connected, sync_all_pending
from .models import Reminder


@shared_task
def due_reminder_digest():
    now = timezone.now()
    horizon = now + timedelta(days=1)
    return list(Reminder.objects.filter(status="pending", due_at__lte=horizon).values_list("id", flat=True))


@shared_task
def sync_google_calendar():
    """Retry de sincronización para eventos creados por cualquier módulo."""
    if not calendar_is_connected():
        return {"connected": False}
    result = sync_all_pending(limit=500)
    result["connected"] = True
    return result
