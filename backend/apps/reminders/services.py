from datetime import datetime, time, timedelta
from django.utils import timezone
from .models import Reminder, ReminderCategory, ReminderStatus


def _aware_on_date(date_value, hour=9):
    dt = datetime.combine(date_value, time(hour=hour))
    return timezone.make_aware(dt, timezone.get_current_timezone()) if timezone.is_naive(dt) else dt


def ensure_reminder(*, source_key, title, category, due_at, client=None, project=None, assigned_to=None, notes="", user=None):
    obj, _ = Reminder.objects.update_or_create(
        source_key=source_key,
        defaults={
            "title": title,
            "category": category,
            "due_at": due_at,
            "client": client,
            "project": project,
            "assigned_to": assigned_to,
            "notes": notes,
            "status": ReminderStatus.PENDING,
            "created_by": user,
        },
    )
    return obj


def ensure_new_client_reminders(project, *, start_date, user=None):
    client = project.client
    ensure_reminder(
        source_key=f"project:{project.pk}:six_weeks",
        title=f"Revisar 6 semanas · {client.business_name}",
        category=ReminderCategory.SIX_WEEKS,
        due_at=_aware_on_date(start_date + timedelta(days=42)),
        client=client,
        project=project,
        assigned_to=user,
        notes="Recordatorio administrativo para revisar que el proyecto no exceda el plazo de seis semanas.",
        user=user,
    )
    ensure_reminder(
        source_key=f"project:{project.pk}:social_offer",
        title=f"Ofrecer Social Media · {client.business_name}",
        category=ReminderCategory.SOCIAL_OFFER,
        due_at=_aware_on_date(start_date + timedelta(days=21)),
        client=client,
        project=project,
        assigned_to=user,
        notes="Seguimiento comercial sugerido a las 3 semanas; puede moverse al mes si corresponde.",
        user=user,
    )


def ensure_credential_renewal_reminder(purchase, *, user=None):
    if not purchase.renewal_date:
        return None
    return ensure_reminder(
        source_key=f"credential:{purchase.pk}:renewal",
        title=f"Renovar {purchase.credential_name} · {purchase.client.business_name}",
        category=ReminderCategory.CREDENTIAL_RENEWAL,
        due_at=_aware_on_date(purchase.renewal_date, 9),
        client=purchase.client,
        project=purchase.project,
        assigned_to=user,
        notes=f"Proveedor: {purchase.get_provider_display()}. Revisar compra/renovación anual.",
        user=user,
    )


def ensure_launch_followups(project, *, launch_date=None, user=None):
    launch_date = launch_date or timezone.localdate()
    client = project.client
    assignees = [user] if user else []
    assignees.extend([a.user for a in project.assignments.select_related("user").filter(area="marketing", status__in=["assigned", "active"]) if a.user])
    seen = set()
    for assignee in assignees or [None]:
        key = assignee.pk if assignee else "team"
        if key in seen:
            continue
        seen.add(key)
        ensure_reminder(
            source_key=f"project:{project.pk}:followup15:{key}",
            title=f"Seguimiento 15 días post lanzamiento · {client.business_name}",
            category=ReminderCategory.FOLLOWUP_15,
            due_at=_aware_on_date(launch_date + timedelta(days=15)),
            client=client, project=project, assigned_to=assignee,
            notes="Revisar web, Marketing, reviews y puntos pendientes con el cliente.", user=user,
        )
        ensure_reminder(
            source_key=f"project:{project.pk}:reviews_guarantee:{key}",
            title=f"Revisar reviews / Google Guarantee · {client.business_name}",
            category=ReminderCategory.GOOGLE_REVIEWS,
            due_at=_aware_on_date(launch_date + timedelta(days=15)),
            client=client, project=project, assigned_to=assignee,
            notes="Si reviews/Google Guarantee no se ha realizado, hacer seguimiento conjunto con Marketing.", user=user,
        )


def ensure_meeting_reminder(meeting, *, user=None):
    due_at = meeting.scheduled_at - timedelta(minutes=meeting.reminder_minutes or 60)
    return ensure_reminder(
        source_key=f"meeting:{meeting.pk}",
        title=f"Reunión · {meeting.client.business_name}",
        category=ReminderCategory.MEETING,
        due_at=due_at,
        client=meeting.client,
        project=meeting.project,
        assigned_to=user,
        notes=meeting.meet_url or meeting.agenda,
        user=user,
    )


def ensure_campaign_weekly_reminders(campaign, *, user=None):
    if not campaign.start_date or not campaign.end_date:
        return
    current = campaign.start_date + timedelta(days=7)
    index = 1
    while current <= campaign.end_date and index <= 52:
        ensure_reminder(
            source_key=f"campaign:{campaign.pk}:week:{index}",
            title=f"Seguimiento semanal {campaign.get_platform_display()} · {campaign.project.client.business_name}",
            category=ReminderCategory.CAMPAIGN_WEEKLY,
            due_at=_aware_on_date(current),
            client=campaign.project.client,
            project=campaign.project,
            assigned_to=campaign.assigned_to,
            notes="Revisar resultados, gasto, leads, ajustes y notas del periodo.",
            user=user,
        )
        current += timedelta(days=7)
        index += 1


def ensure_social_monthly_reminder(plan, *, user=None):
    if not plan.next_report_date:
        return
    ensure_reminder(
        source_key=f"social-plan:{plan.pk}:monthly:{plan.next_report_date.isoformat()}",
        title=f"Pedir informe mensual Social Media · {plan.client.business_name}",
        category=ReminderCategory.SOCIAL_MONTHLY,
        due_at=_aware_on_date(plan.next_report_date),
        client=plan.client,
        project=plan.project,
        assigned_to=plan.assigned_to,
        notes="Revisar publicaciones, seguimiento diario, resultados y pedir informe a Marketing.",
        user=user,
    )
