from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.utils import timezone
from django.shortcuts import render

from apps.audit.models import ActivityLog
from apps.clients.models import Client
from apps.finance.models import FinancialTransaction, PersonnelPayment
from apps.marketing.models import MarketingChecklistItem, SocialMediaTracking
from apps.operations.models import CredentialPurchase, ProductionRecord
from apps.projects.selectors import visible_projects_for_user
from apps.reminders.models import Meeting, Reminder


OPERATIONAL_ACTIVE_STATUSES = {
    "active",
    "administration",
    "design_intake",
    "development_intake",
    "information_ready",
    "in_development",
    "review",
    "paused",
}

COMPLETED_STATUSES = {"completed", "delivered"}


def _avg(values):
    values = list(values)
    return round(sum(values) / len(values)) if values else 0


@login_required
def home(request):
    today = timezone.localdate()
    now = timezone.now()
    is_manager = request.user.is_manager or request.user.is_superuser
    is_sales = getattr(request.user, "role", "") == "sales" and not request.user.is_superuser

    projects_qs = visible_projects_for_user(request.user).distinct()
    reminders = Reminder.objects.select_related("client", "project", "assigned_to").filter(status="pending")
    if not is_manager:
        reminders = reminders.filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))

    # El resumen operativo usa el mismo cálculo del módulo Proyectos para que los
    # porcentajes nunca contradigan las fichas reales. No se exponen montos aquí.
    from apps.projects.views import _control_data

    project_rows = []
    for project in projects_qs:
        project_rows.append({"project": project, "control": _control_data(project)})

    active_rows = [r for r in project_rows if r["project"].status in OPERATIONAL_ACTIVE_STATUSES]
    delivered_rows = [r for r in project_rows if r["project"].status in COMPLETED_STATUSES]
    paused_rows = [r for r in project_rows if r["project"].status == "paused"]
    cancelled_rows = [r for r in project_rows if r["project"].status == "cancelled"]
    queue_rows = [r for r in active_rows if r["control"]["overall_percent"] < 25]
    incomplete_rows = [r for r in active_rows if 25 <= r["control"]["overall_percent"] < 90]
    ready_rows = [r for r in active_rows if r["control"]["overall_percent"] >= 90]
    delayed_rows = [r for r in active_rows if r["project"].due_date and r["project"].due_date < today]

    for row in project_rows:
        progress = row["control"]["overall_percent"]
        project = row["project"]
        if project.status in COMPLETED_STATUSES:
            stage_label = "Completado"
            stage_class = "is-complete"
        elif project.status == "paused":
            stage_label = "Pausado"
            stage_class = "is-paused"
        elif project.due_date and project.due_date < today:
            stage_label = "Retrasado"
            stage_class = "is-delayed"
        elif progress < 25:
            stage_label = "Pendiente"
            stage_class = "is-pending"
        elif progress < 90:
            stage_label = "En proceso"
            stage_class = "is-progress"
        else:
            stage_label = "Por completar"
            stage_class = "is-ready"
        row["employee_stage_label"] = stage_label
        row["employee_stage_class"] = stage_class

    area_stats = {
        "administration": _avg(r["control"]["admin_percent"] for r in project_rows),
        "design": _avg(r["control"]["design_percent"] for r in project_rows),
        "marketing": _avg(r["control"]["marketing_percent"] for r in project_rows),
        "development": _avg(r["control"]["development_percent"] for r in project_rows),
        "overall": _avg(r["control"]["overall_percent"] for r in project_rows),
    }

    employee_project_cards = [
        {
            "label": "Activos",
            "value": len(active_rows),
            "hint": "Actualmente visibles para el equipo",
            "tone": "active",
        },
        {
            "label": "Pendientes",
            "value": len(queue_rows),
            "hint": "Con avance menor al 25%",
            "tone": "pending",
        },
        {
            "label": "En proceso",
            "value": len(incomplete_rows),
            "hint": "Trabajo operativo en curso",
            "tone": "progress",
        },
        {
            "label": "Por completar",
            "value": len(ready_rows),
            "hint": "Con 90% o más de avance",
            "tone": "ready",
        },
        {
            "label": "Completados",
            "value": len(delivered_rows),
            "hint": "Terminados o entregados",
            "tone": "complete",
        },
        {
            "label": "Retrasados",
            "value": len(delayed_rows),
            "hint": "Fecha objetivo vencida",
            "tone": "delayed",
        },
    ]

    employee_status_rows = [
        {"label": "Activos", "value": len(active_rows), "class_name": "active", "helper": "operación abierta"},
        {"label": "Pausados", "value": len(paused_rows), "class_name": "paused", "helper": "esperando reactivación"},
        {"label": "Completados", "value": len(delivered_rows), "class_name": "complete", "helper": "cerrados o entregados"},
        {"label": "Cancelados", "value": len(cancelled_rows), "class_name": "cancelled", "helper": "sin operación"},
    ]

    employee_focus_rows = sorted(
        [r for r in active_rows if r["project"].due_date or r["control"]["overall_percent"] < 90],
        key=lambda row: (
            0 if row["project"].due_date and row["project"].due_date < today else 1,
            row["project"].due_date or today + timedelta(days=3650),
            row["control"]["overall_percent"],
        ),
    )[:8]

    context = {
        "is_sales": is_sales,
        "project_count": len(active_rows),
        "project_total": len(project_rows),
        "reminder_count": reminders.filter(due_at__lte=now + timedelta(days=7)).count(),
        "recent_project_rows": project_rows[:12],
        "upcoming_reminders": reminders.order_by("due_at")[:8],
        "queue_count": len(queue_rows),
        "incomplete_count": len(incomplete_rows),
        "ready_count": len(ready_rows),
        "delivered_count": len(delivered_rows),
        "delayed_count": len(delayed_rows),
        "area_stats": area_stats,
        "employee_project_cards": employee_project_cards,
        "employee_status_rows": employee_status_rows,
        "employee_focus_rows": employee_focus_rows,
    }

    if is_sales:
        meetings = (
            Meeting.objects.select_related("client", "project")
            .prefetch_related("attendees")
            .filter(status="scheduled")
            .filter(Q(attendees=request.user) | Q(attendees__isnull=True))
            .distinct()
            .order_by("scheduled_at")
        )
        context.update({
            "upcoming_meetings": meetings[:8],
            "sales_due_soon_count": reminders.filter(due_at__lte=now + timedelta(days=2)).count(),
            "sales_meeting_count": meetings.filter(scheduled_at__gte=now, scheduled_at__lte=now + timedelta(days=7)).count(),
        })

    if not is_manager:
        # Dashboard Empleados: solo operación. Sin clientes globales, credenciales,
        # finanzas, nómina, producción administrativa ni logs de auditoría.
        return render(request, "dashboard/employee.html", context)

    # Dashboard Gerencia: conserva la vista ejecutiva completa y sensible.
    context.update({
        "client_count": Client.objects.filter(status="active").count(),
        "credential_due_count": CredentialPurchase.objects.filter(
            active=True, renewal_date__range=(today, today + timedelta(days=45))
        ).count(),
        "production_pending": ProductionRecord.objects.exclude(status__in=["finished", "delivered"]).count(),
        "social_incomplete": SocialMediaTracking.objects.filter(
            Q(reviews="incomplete") | Q(products="incomplete") | Q(profile_percentage="incomplete") |
            Q(google_business="incomplete") | Q(networks="incomplete") | Q(website_in_gb="incomplete") |
            Q(lsa="incomplete") | Q(photos="incomplete") | Q(ads_verified="incomplete")
        ).distinct().count(),
        "marketing_pending": MarketingChecklistItem.objects.filter(status="incomplete").count(),
        "recent_activity": ActivityLog.objects.select_related("user")[:12],
    })
    month_start = today.replace(day=1)
    month = FinancialTransaction.objects.filter(transaction_date__gte=month_start, status="paid")
    context["month_expenses"] = month.filter(transaction_type="expense").aggregate(total=Sum("amount"))["total"] or 0
    context["month_income"] = month.filter(transaction_type="income").aggregate(total=Sum("amount"))["total"] or 0
    context["payroll_pending"] = PersonnelPayment.objects.filter(status__in=["planned", "pending"]).count()

    return render(request, "dashboard/home.html", context)
