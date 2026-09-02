from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import render
from django.utils import timezone
from apps.clients.models import Client
from apps.domains.models import Domain
from apps.finance.models import FinancialTransaction
from apps.plans.models import ClientPlan
from apps.projects.models import Project


@login_required
def home(request):
    today = timezone.localdate()
    projects = Project.objects.select_related("client", "purchased_plan__plan").prefetch_related("assignments__user")
    if not request.user.is_manager:
        role_stages = {
            "administration": ["administration", "design_intake"],
            "design": ["design_intake", "development_intake", "information_ready", "review"],
            "developer": ["development_intake", "information_ready", "in_development", "review"],
            "marketing": ["information_ready", "in_development", "review", "delivered"],
        }
        projects = projects.filter(status__in=role_stages.get(request.user.role, []))

    context = {
        "client_count": Client.objects.filter(status="active").count(),
        "project_count": projects.exclude(status__in=["delivered", "cancelled"]).distinct().count(),
        "plan_count": ClientPlan.objects.filter(status__in=["purchased", "active"]).count(),
        "domain_due_count": Domain.objects.filter(Q(renewal_date__range=(today, today + timedelta(days=45))) | Q(expiry_date__range=(today, today + timedelta(days=45)))).count(),
        "recent_projects": projects.distinct()[:10],
        "upcoming_domains": Domain.objects.select_related("client").filter(renewal_date__gte=today).order_by("renewal_date")[:6],
        "design_pending": Project.objects.filter(status="design_intake").count(),
        "development_pending": Project.objects.filter(status="development_intake").count(),
        "information_ready": Project.objects.filter(status="information_ready").count(),
    }
    if request.user.is_manager:
        month_start = today.replace(day=1)
        month = FinancialTransaction.objects.filter(transaction_date__gte=month_start, status="paid")
        context["month_expenses"] = month.filter(transaction_type="expense").aggregate(total=Sum("amount"))["total"] or 0
        context["month_income"] = month.filter(transaction_type="income").aggregate(total=Sum("amount"))["total"] or 0
    return render(request, "dashboard/home.html", context)
