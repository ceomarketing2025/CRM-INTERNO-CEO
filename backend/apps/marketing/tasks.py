from datetime import datetime, time, timedelta
from celery import shared_task
from django.utils import timezone
from apps.reminders.models import ReminderCategory
from apps.reminders.services import ensure_reminder
from .models import SocialMediaPlan
from .services import refresh_lsa_followups


def _due_at_today(hour=9):
    now = timezone.localtime()
    target = timezone.make_aware(datetime.combine(now.date(), time(hour=hour)), timezone.get_current_timezone())
    return now if now > target else target


@shared_task
def create_daily_social_followups():
    today = timezone.localdate()
    refresh_lsa_followups()
    count = 0
    for plan in SocialMediaPlan.objects.select_related("client", "project", "assigned_to").filter(active=True, start_date__lte=today):
        if plan.end_date and plan.end_date < today:
            continue
        ensure_reminder(
            source_key=f"social-plan:{plan.pk}:daily:{today.isoformat()}",
            title=f"Seguimiento diario Social Media · {plan.client.business_name}",
            category=ReminderCategory.SOCIAL_DAILY,
            due_at=_due_at_today(9),
            client=plan.client, project=plan.project, assigned_to=plan.assigned_to,
            notes="Revisar seguimiento del día y publicaciones programadas.", user=plan.assigned_to,
        )
        count += 1

        if plan.next_report_date and today >= plan.next_report_date:
            ensure_reminder(
                source_key=f"social-plan:{plan.pk}:monthly:{plan.next_report_date.isoformat()}",
                title=f"Pedir informe mensual Social Media · {plan.client.business_name}",
                category=ReminderCategory.SOCIAL_MONTHLY,
                due_at=_due_at_today(9),
                client=plan.client, project=plan.project, assigned_to=plan.assigned_to,
                notes="Revisar publicaciones, seguimiento diario, resultados y pedir informe a Marketing.", user=plan.assigned_to,
            )
            plan.next_report_date = plan.next_report_date + timedelta(days=30)
            plan.save(update_fields=["next_report_date", "updated_at"])
    return count
