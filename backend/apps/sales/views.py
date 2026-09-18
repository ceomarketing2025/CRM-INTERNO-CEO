from datetime import timedelta

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.decorators import role_required
from .forms import LeadForm
from .models import FollowUp, Lead, SalesMeeting


def _visible_leads(user):
    qs = Lead.objects.select_related("assigned_to")
    if user.is_manager or user.is_superuser:
        return qs
    return qs.filter(assigned_to=user)


def _visible_followups(user):
    qs = FollowUp.objects.select_related("lead", "assigned_to")
    if user.is_manager or user.is_superuser:
        return qs
    return qs.filter(assigned_to=user)


@role_required("sales")
def dashboard(request):
    now = timezone.now()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    leads = _visible_leads(request.user)
    followups = _visible_followups(request.user).filter(status=FollowUp.Status.PENDING)
    meetings = SalesMeeting.objects.select_related("lead", "seller")
    if not (request.user.is_manager or request.user.is_superuser):
        meetings = meetings.filter(seller=request.user)

    context = {
        "now": now,
        "today": today,
        "new_count": leads.filter(status=Lead.Status.NEW).count(),
        "pending_contact_count": leads.filter(status=Lead.Status.PENDING).count(),
        "overdue_count": followups.filter(due_at__lt=now).count(),
        "today_followups_count": followups.filter(due_at__date=today).count(),
        "today_meetings_count": meetings.filter(scheduled_at__date=today, status=SalesMeeting.Status.SCHEDULED).count(),
        "potential_count": leads.filter(status=Lead.Status.POTENTIAL).count(),
        "won_month_count": leads.filter(status=Lead.Status.WON, updated_at__year=today.year, updated_at__month=today.month).count(),
        "day_items": followups.filter(due_at__date__lte=today).order_by("due_at")[:12],
        "upcoming_items": followups.filter(due_at__date__gte=tomorrow).order_by("due_at")[:6],
        "pipeline": [
            ("Nuevos", leads.filter(status=Lead.Status.NEW).count()),
            ("Contactados", leads.filter(status=Lead.Status.CONTACTED).count()),
            ("Meets", leads.filter(status__in=[Lead.Status.MEETING_PROPOSED, Lead.Status.MEETING_DONE]).count()),
            ("Potenciales", leads.filter(status=Lead.Status.POTENTIAL).count()),
            ("Ventas", leads.filter(status=Lead.Status.WON).count()),
        ],
    }
    return render(request, "sales/dashboard.html", context)


@role_required("sales")
def lead_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    leads = _visible_leads(request.user)
    if q:
        leads = leads.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q))
    if status:
        leads = leads.filter(status=status)
    return render(request, "sales/lead_list.html", {"leads": leads, "q": q, "status": status, "status_choices": Lead.Status.choices})


@role_required("sales")
def lead_create(request):
    form = LeadForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        lead.created_by = request.user
        if request.user.role == "sales":
            lead.assigned_to = request.user
        lead.save()
        messages.success(request, "Lead creado y listo para seguimiento.")
        return redirect("sales:lead_detail", pk=lead.pk)
    return render(request, "sales/lead_form.html", {"form": form})


@role_required("sales")
def lead_detail(request, pk):
    lead = get_object_or_404(_visible_leads(request.user).prefetch_related("contact_attempts", "follow_ups", "sales_meetings"), pk=pk)
    timeline = []
    for item in lead.contact_attempts.all():
        timeline.append((item.contacted_at, "contact", item))
    for item in lead.follow_ups.all():
        timeline.append((item.created_at, "followup", item))
    for item in lead.sales_meetings.all():
        timeline.append((item.created_at, "meeting", item))
    timeline.sort(key=lambda row: row[0], reverse=True)
    return render(request, "sales/lead_detail.html", {"lead": lead, "timeline": timeline})
