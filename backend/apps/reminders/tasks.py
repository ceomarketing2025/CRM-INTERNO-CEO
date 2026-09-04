from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import Reminder


@shared_task
def due_reminder_digest():
    now = timezone.now()
    horizon = now + timedelta(days=1)
    return list(Reminder.objects.filter(status="pending", due_at__lte=horizon).values_list("id", flat=True))
