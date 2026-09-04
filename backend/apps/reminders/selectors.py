from django.utils import timezone
from .models import Reminder
def due_reminders(): return Reminder.objects.filter(status="pending", due_at__lte=timezone.now()).order_by("due_at")
