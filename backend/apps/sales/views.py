from datetime import timedelta

from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from apps.core.decorators import sales_required
from apps.reminders.models import Meeting, Reminder


@sales_required
def dashboard(request):
    now = timezone.now()
    reminders = (
        Reminder.objects.select_related("client", "project", "assigned_to")
        .filter(status="pending")
        .filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))
        .order_by("due_at")
    )
    meetings = (
        Meeting.objects.select_related("client", "project")
        .prefetch_related("attendees")
        .filter(status="scheduled")
        .filter(Q(attendees=request.user) | Q(attendees__isnull=True))
        .distinct()
        .order_by("scheduled_at")
    )
    return render(request, "sales/dashboard.html", {
        "upcoming_reminders": reminders[:8],
        "upcoming_meetings": meetings[:8],
        "due_soon_count": reminders.filter(due_at__lte=now + timedelta(days=2)).count(),
        "meeting_count": meetings.filter(scheduled_at__gte=now, scheduled_at__lte=now + timedelta(days=7)).count(),
    })
