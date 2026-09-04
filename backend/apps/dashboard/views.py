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
from apps.projects.models import Project
from apps.projects.selectors import visible_projects_for_user
from apps.reminders.models import Reminder


def _avg(values):
    values = list(values)
    return round(sum(values) / len(values)) if values else 0


@login_required
def home(request):
    today = timezone.localdate()
    projects_qs = visible_projects_for_user(request.user).distinct()
    reminders = Reminder.objects.select_related("client", "project", "assigned_to").filter(status="pending")
    if not request.user.is_manager:
        reminders = reminders.filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))

    # Reuse the same control calculation used by the Projects module so dashboard
    # percentages and project cards never contradict each other.
    from apps.projects.views import _control_data
    project_rows = []
    for project in projects_qs:
        project_rows.append({"project": project, "control": _control_data(project)})

    active_rows = [r for r in project_rows if r["project"].status not in {"completed", "cancelled", "delivered"}]
    delivered_rows = [r for r in project_rows if r["project"].status in {"completed", "delivered"}]
    queue_rows = [r for r in active_rows if r["control"]["overall_percent"] < 25]
    incomplete_rows = [r for r in active_rows if 25 <= r["control"]["overall_percent"] < 90]
    ready_rows = [r for r in active_rows if r["control"]["overall_percent"] >= 90]
    delayed_rows = [r for r in active_rows if r["project"].due_date and r["project"].due_date < today]

    area_stats = {
        "administration": _avg(r["control"]["admin_percent"] for r in project_rows),
        "design": _avg(r["control"]["design_percent"] for r in project_rows),
        "marketing": _avg(r["control"]["marketing_percent"] for r in project_rows),
        "development": _avg(r["control"]["development_percent"] for r in project_rows),
        "overall": _avg(r["control"]["overall_percent"] for r in project_rows),
    }

    context = {
        "client_count": Client.objects.filter(status="active").count(),
        "project_count": len(active_rows),
        "project_total": len(project_rows),
        "reminder_count": reminders.filter(due_at__lte=timezone.now() + timedelta(days=7)).count(),
        "recent_project_rows": project_rows[:10],
        "upcoming_reminders": reminders.order_by("due_at")[:8],
        "credential_due_count": CredentialPurchase.objects.filter(active=True, renewal_date__range=(today, today + timedelta(days=45))).count(),
        "queue_count": len(queue_rows),
        "incomplete_count": len(incomplete_rows),
        "ready_count": len(ready_rows),
        "delivered_count": len(delivered_rows),
        "delayed_count": len(delayed_rows),
        "area_stats": area_stats,
        "recent_activity": ActivityLog.objects.select_related("user")[:12],
    }

    if request.user.is_manager or request.user.role == "administration":
        context["production_pending"] = ProductionRecord.objects.exclude(status__in=["finished", "delivered"]).count()
        context["social_incomplete"] = SocialMediaTracking.objects.filter(
            Q(reviews="incomplete") | Q(products="incomplete") | Q(profile_percentage="incomplete") |
            Q(google_business="incomplete") | Q(networks="incomplete") | Q(website_in_gb="incomplete") |
            Q(lsa="incomplete") | Q(photos="incomplete") | Q(ads_verified="incomplete")
        ).distinct().count()

    if request.user.is_manager or request.user.role == "marketing":
        context["marketing_pending"] = MarketingChecklistItem.objects.filter(status="incomplete").count()

    if request.user.is_manager:
        month_start = today.replace(day=1)
        month = FinancialTransaction.objects.filter(transaction_date__gte=month_start, status="paid")
        context["month_expenses"] = month.filter(transaction_type="expense").aggregate(total=Sum("amount"))["total"] or 0
        context["month_income"] = month.filter(transaction_type="income").aggregate(total=Sum("amount"))["total"] or 0
        context["payroll_pending"] = PersonnelPayment.objects.filter(status__in=["planned", "pending"]).count()

    return render(request, "dashboard/home.html", context)
