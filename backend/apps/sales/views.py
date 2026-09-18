from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import role_required
from apps.clients.models import Client
from apps.clients.models.choices import ClientType
from apps.projects.models import Project, ProjectPlanAssignment
from apps.projects.models.choices import ProjectStatus
from .forms import AgendaFollowUpForm, AgendaMeetingForm, ContactAttemptForm, FollowUpForm, LeadConversionForm, LeadForm, SalesMeetingForm
from .models import ContactAttempt, FollowUp, Lead, SalesMeeting


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


def _visible_meetings(user):
    qs = SalesMeeting.objects.select_related("lead", "seller")
    if user.is_manager or user.is_superuser:
        return qs
    return qs.filter(seller=user)


def _lead_for_user(user, pk):
    return get_object_or_404(_visible_leads(user), pk=pk)


def _sync_next_follow_up(lead):
    next_item = lead.follow_ups.filter(status=FollowUp.Status.PENDING, due_at__gte=timezone.now()).order_by("due_at").first()
    if not next_item:
        next_item = lead.follow_ups.filter(status=FollowUp.Status.PENDING).order_by("due_at").first()
    lead.next_follow_up_at = next_item.due_at if next_item else None
    lead.save(update_fields=["next_follow_up_at", "updated_at"])


@role_required("sales")
def dashboard(request):
    now = timezone.now()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    leads = _visible_leads(request.user)
    followups = _visible_followups(request.user).filter(status=FollowUp.Status.PENDING)
    meetings = _visible_meetings(request.user)
    context = {
        "now": now, "today": today,
        "new_count": leads.filter(status=Lead.Status.NEW).count(),
        "pending_contact_count": leads.filter(status=Lead.Status.PENDING).count(),
        "overdue_count": followups.filter(due_at__lt=now).count(),
        "today_followups_count": followups.filter(due_at__date=today).count(),
        "today_meetings_count": meetings.filter(scheduled_at__date=today, status=SalesMeeting.Status.SCHEDULED).count(),
        "potential_count": leads.filter(status=Lead.Status.POTENTIAL).count(),
        "won_month_count": leads.filter(status=Lead.Status.WON, updated_at__year=today.year, updated_at__month=today.month).count(),
        "day_items": followups.filter(due_at__date__lte=today).order_by("due_at")[:12],
        "upcoming_items": followups.filter(due_at__date__gte=tomorrow).order_by("due_at")[:6],
        "pipeline": [("Nuevos", leads.filter(status=Lead.Status.NEW).count()), ("Contactados", leads.filter(status=Lead.Status.CONTACTED).count()), ("Meets", leads.filter(status__in=[Lead.Status.MEETING_PROPOSED, Lead.Status.MEETING_DONE]).count()), ("Potenciales", leads.filter(status=Lead.Status.POTENTIAL).count()), ("Ventas", leads.filter(status=Lead.Status.WON).count())],
    }
    return render(request, "sales/dashboard.html", context)


@role_required("sales")
def lead_list(request):
    q = request.GET.get("q", "").strip(); status = request.GET.get("status", "").strip()
    leads = _visible_leads(request.user)
    if q: leads = leads.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q))
    if status: leads = leads.filter(status=status)
    return render(request, "sales/lead_list.html", {"leads": leads, "q": q, "status": status, "status_choices": Lead.Status.choices})


@role_required("sales")
def lead_create(request):
    form = LeadForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False); lead.created_by = request.user
        if request.user.role == "sales": lead.assigned_to = request.user
        lead.save(); messages.success(request, "Lead creado y listo para seguimiento.")
        return redirect("sales:lead_detail", pk=lead.pk)
    return render(request, "sales/lead_form.html", {"form": form})


@role_required("sales")
def lead_detail(request, pk):
    lead = get_object_or_404(_visible_leads(request.user).prefetch_related("contact_attempts", "follow_ups", "sales_meetings"), pk=pk)
    timeline = []
    for item in lead.contact_attempts.all(): timeline.append((item.contacted_at, "contact", item))
    for item in lead.follow_ups.all(): timeline.append((item.created_at, "followup", item))
    for item in lead.sales_meetings.all(): timeline.append((item.created_at, "meeting", item))
    timeline.sort(key=lambda row: row[0], reverse=True)
    return render(request, "sales/lead_detail.html", {
        "lead": lead, "timeline": timeline, "contact_form": ContactAttemptForm(),
        "followup_form": FollowUpForm(), "meeting_form": SalesMeetingForm(), "status_choices": Lead.Status.choices,
        "loss_reasons": Lead.LossReason.choices, "conversion_form": LeadConversionForm(lead=lead),
    })


@require_POST
@role_required("sales")
@transaction.atomic
def add_contact(request, pk):
    lead = _lead_for_user(request.user, pk); form = ContactAttemptForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revisa los datos del contacto antes de guardar."); return redirect("sales:lead_detail", pk=pk)
    contact = form.save(commit=False); contact.lead = lead; contact.seller = request.user; contact.save()
    lead.last_contact_at = contact.contacted_at
    if contact.result == ContactAttempt.Result.ACCEPTS_MEETING: lead.status = Lead.Status.MEETING_PROPOSED
    elif contact.result in {ContactAttempt.Result.NO_ANSWER, ContactAttempt.Result.CONTACT_LATER}: lead.status = Lead.Status.FOLLOW_UP
    elif contact.result in {ContactAttempt.Result.NOT_INTERESTED, ContactAttempt.Result.OUT_OF_BUDGET, ContactAttempt.Result.WRONG_NUMBER}: lead.status = Lead.Status.CONTACTED
    else: lead.status = Lead.Status.CONTACTED
    lead.save(update_fields=["last_contact_at", "status", "updated_at"])
    if form.cleaned_data.get("create_follow_up"):
        FollowUp.objects.create(lead=lead, assigned_to=lead.assigned_to or request.user, created_by=request.user, due_at=form.cleaned_data["follow_up_at"], contact_type=form.cleaned_data.get("follow_up_type") or FollowUp.ContactType.PHONE, notes="Creado desde el registro de contacto.")
        _sync_next_follow_up(lead)
    messages.success(request, "Contacto registrado en el historial.")
    return redirect("sales:lead_detail", pk=pk)


@require_POST
@role_required("sales")
def add_followup(request, pk):
    lead = _lead_for_user(request.user, pk); form = FollowUpForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False); item.lead = lead; item.assigned_to = lead.assigned_to or request.user; item.created_by = request.user; item.save()
        if lead.status not in {Lead.Status.WON, Lead.Status.LOST, Lead.Status.UNQUALIFIED}: lead.status = Lead.Status.FOLLOW_UP; lead.save(update_fields=["status", "updated_at"])
        _sync_next_follow_up(lead); messages.success(request, "Seguimiento programado.")
    else: messages.error(request, "No pudimos programar el seguimiento. Revisa fecha y hora.")
    return redirect("sales:lead_detail", pk=pk)


@require_POST
@role_required("sales")
def add_meeting(request, pk):
    lead = _lead_for_user(request.user, pk); form = SalesMeetingForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False); item.lead = lead; item.seller = lead.assigned_to or request.user; item.created_by = request.user; item.status = SalesMeeting.Status.SCHEDULED; item.save()
        lead.status = Lead.Status.MEETING_PROPOSED; lead.save(update_fields=["status", "updated_at"]); messages.success(request, "Meet agregado a la agenda.")
    else: messages.error(request, "Revisa los datos del meet.")
    return redirect("sales:lead_detail", pk=pk)


@require_POST
@role_required("sales")
def update_status(request, pk):
    lead = _lead_for_user(request.user, pk); new_status = request.POST.get("status", ""); valid = {v for v, _ in Lead.Status.choices}
    if new_status not in valid: messages.error(request, "Estado no válido."); return redirect("sales:lead_detail", pk=pk)
    if new_status in {Lead.Status.LOST, Lead.Status.UNQUALIFIED}:
        reason = request.POST.get("loss_reason", "")
        if reason not in {v for v, _ in Lead.LossReason.choices}: messages.error(request, "Selecciona un motivo de pérdida o descalificación."); return redirect("sales:lead_detail", pk=pk)
        lead.loss_reason = reason
    elif new_status not in {Lead.Status.NO_RESPONSE}: lead.loss_reason = ""
    lead.status = new_status; lead.save(update_fields=["status", "loss_reason", "updated_at"]); messages.success(request, f"Estado actualizado a {lead.get_status_display()}.")
    return redirect("sales:lead_detail", pk=pk)


@require_POST
@role_required("sales")
def complete_followup(request, pk):
    item = get_object_or_404(_visible_followups(request.user), pk=pk); item.status = FollowUp.Status.COMPLETED; item.save(update_fields=["status", "updated_at"]); _sync_next_follow_up(item.lead); messages.success(request, "Seguimiento completado.")
    return redirect(request.POST.get("next") or "sales:followup_list")


@role_required("sales")
def followup_list(request):
    now = timezone.now(); items = _visible_followups(request.user).filter(status=FollowUp.Status.PENDING).order_by("due_at")
    return render(request, "sales/followup_list.html", {"items": items, "now": now, "agenda_form": AgendaFollowUpForm(user=request.user)})


@role_required("sales")
def meeting_list(request):
    items = _visible_meetings(request.user).order_by("scheduled_at")
    return render(request, "sales/meeting_list.html", {"items": items, "now": timezone.now(), "meeting_status_choices": SalesMeeting.Status.choices, "agenda_form": AgendaMeetingForm(user=request.user)})


@require_POST
@role_required("sales")
def update_meeting(request, pk):
    item = get_object_or_404(_visible_meetings(request.user), pk=pk); status = request.POST.get("status", "")
    if status not in {v for v, _ in SalesMeeting.Status.choices}: messages.error(request, "Estado de meet no válido."); return redirect("sales:meeting_list")
    item.status = status; item.result = request.POST.get("result", item.result); item.save(update_fields=["status", "result", "updated_at"])
    if status == SalesMeeting.Status.COMPLETED: item.lead.status = Lead.Status.MEETING_DONE; item.lead.save(update_fields=["status", "updated_at"])
    messages.success(request, "Meet actualizado."); return redirect(request.POST.get("next") or "sales:meeting_list")


@require_POST
@role_required("sales")
@transaction.atomic
def create_followup_from_agenda(request):
    form = AgendaFollowUpForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, "Revisa los datos antes de programar el seguimiento.")
        return redirect("sales:followup_list")
    lead = form.cleaned_data["lead"]
    if not _visible_leads(request.user).filter(pk=lead.pk).exists():
        messages.error(request, "No tienes acceso a ese lead.")
        return redirect("sales:followup_list")
    item = form.save(commit=False)
    item.lead = lead
    item.assigned_to = form.cleaned_data["assigned_to"]
    item.created_by = request.user
    item.save()
    if lead.status not in {Lead.Status.WON, Lead.Status.LOST, Lead.Status.UNQUALIFIED}:
        lead.status = Lead.Status.FOLLOW_UP
        lead.save(update_fields=["status", "updated_at"])
    _sync_next_follow_up(lead)
    messages.success(request, "Seguimiento agregado a la agenda.")
    return redirect("sales:followup_list")


@require_POST
@role_required("sales")
@transaction.atomic
def create_meeting_from_agenda(request):
    form = AgendaMeetingForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, "Revisa los datos antes de agendar el meet.")
        return redirect("sales:meeting_list")
    lead = form.cleaned_data["lead"]
    if not _visible_leads(request.user).filter(pk=lead.pk).exists():
        messages.error(request, "No tienes acceso a ese lead.")
        return redirect("sales:meeting_list")
    item = form.save(commit=False)
    item.lead = lead
    item.seller = form.cleaned_data["seller"]
    item.created_by = request.user
    item.status = SalesMeeting.Status.SCHEDULED
    item.save()
    lead.status = Lead.Status.MEETING_PROPOSED
    lead.save(update_fields=["status", "updated_at"])
    messages.success(request, "Meet agregado a la agenda.")
    return redirect("sales:meeting_list")


@require_POST
@role_required("sales")
@transaction.atomic
def convert_lead_to_client(request, pk):
    lead = _lead_for_user(request.user, pk)
    if lead.status != Lead.Status.WON:
        messages.error(request, "Primero marca el lead como Venta cerrada antes de convertirlo en cliente.")
        return redirect("sales:lead_detail", pk=pk)
    if lead.client_id:
        messages.info(request, "Este lead ya está vinculado a un cliente.")
        return redirect("sales:lead_detail", pk=pk)

    form = LeadConversionForm(request.POST, lead=lead)
    if not form.is_valid():
        messages.error(request, "Revisa los datos de conversión, el cliente y los servicios vendidos.")
        return redirect("sales:lead_detail", pk=pk)

    client = form.cleaned_data.get("existing_client")
    if not client:
        client = Client.objects.create(
            client_type=ClientType.COMPANY if lead.company else ClientType.PERSON,
            first_name=lead.first_name,
            last_name=lead.last_name,
            business_name=form.cleaned_data["business_name"],
            contact_name=lead.full_name,
            email=lead.email,
            phone=lead.phone,
            country=lead.country,
            state_region=lead.state_region,
            city=lead.city,
            source=lead.source,
            notes=lead.comments,
            created_by=request.user,
        )

    project = Project.objects.create(
        client=client,
        name=form.cleaned_data["project_name"],
        status=ProjectStatus.IN_DEVELOPMENT,
        start_date=timezone.localdate(),
        summary=f"Creado desde Ventas al convertir el lead #{lead.pk}.",
        internal_notes=lead.comments,
        created_by=request.user,
    )

    plans = list(form.cleaned_data["service_plans"])
    sale_value = form.cleaned_data.get("sale_value")
    for index, plan in enumerate(plans):
        agreed_price = plan.base_price
        if sale_value is not None and len(plans) == 1:
            agreed_price = sale_value
        ProjectPlanAssignment.objects.create(
            project=project,
            plan=plan,
            agreed_price=agreed_price,
            is_active=True,
            created_by=request.user,
        )

    lead.client = client
    lead.converted_project = project
    lead.sale_value = sale_value
    lead.converted_at = timezone.now()
    lead.converted_by = request.user
    lead.save(update_fields=["client", "converted_project", "sale_value", "converted_at", "converted_by", "updated_at"])

    messages.success(request, f"{lead.full_name} ya es cliente y su proyecto fue creado con los servicios vendidos.")
    return redirect("sales:lead_detail", pk=pk)
