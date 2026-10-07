from collections import OrderedDict
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.decorators import role_required
from apps.audit.services import log_activity
from apps.design.services import ensure_current_social_media_cycle
from apps.plans.forms import SOCIAL_NETWORK_CHOICES, SocialMediaAssignmentForm
from apps.plans.models import ClientPlan
from apps.plans.models.choices import RenewalFrequency, ServiceType
from apps.plans.services import renewal_urgency
from apps.projects.models import Project, ProjectPlanAssignment


social_media_required = role_required("design", "marketing")


def _project_for_assignment(assignment):
    link = assignment.project_links.select_related("project__client").first()
    return link.project if link else None


def _distribution_week_count(assignment):
    frequency = assignment.renewal_frequency
    if frequency in {RenewalFrequency.WEEKLY, RenewalFrequency.EVERY_MONDAY}:
        return 1
    if frequency == RenewalFrequency.BIWEEKLY:
        return 2
    # El flujo comercial mensual de Social Media se reparte en cuatro bloques
    # operativos aunque el mes calendario tenga días adicionales.
    return 4


def _week_groups(cycle, assignment):
    if not cycle:
        return []
    items = list(cycle.items.all().order_by("content_type", "sequence", "id"))
    week_count = _distribution_week_count(assignment)
    totals = {}
    for item in items:
        totals[item.content_type] = totals.get(item.content_type, 0) + 1

    groups = OrderedDict(
        (number, {
            "number": number,
            "label": f"Semana {number}",
            "items": [],
            "design_done": 0,
            "marketing_done": 0,
        })
        for number in range(1, week_count + 1)
    )

    for item in items:
        total = max(totals.get(item.content_type, 1), 1)
        week_number = min(week_count, ((item.sequence - 1) * week_count // total) + 1)
        groups[week_number]["items"].append(item)

    result = []
    for number, group in groups.items():
        group_items = group["items"]
        group["design_done"] = sum(1 for item in group_items if item.ready)
        group["marketing_done"] = sum(1 for item in group_items if item.is_complete)
        total = len(group_items)
        group["design_percent"] = round(group["design_done"] * 100 / total) if total else 0
        group["marketing_percent"] = round(group["marketing_done"] * 100 / total) if total else 0
        start = cycle.period_start + timedelta(days=(number - 1) * 7)
        end = start + timedelta(days=6)
        if cycle.due_date:
            end = min(end, cycle.due_date - timedelta(days=1))
        group["start"] = start
        group["end"] = end
        design_complete = bool(total) and group["design_done"] >= total
        marketing_complete = bool(total) and group["marketing_done"] >= total
        today = timezone.localdate()
        if design_complete and marketing_complete:
            group["state"] = "green"
            group["state_label"] = "Completada"
        elif today > end:
            group["state"] = "red"
            group["state_label"] = "Vencida con pendientes"
        elif start <= today <= end:
            group["state"] = "yellow"
            group["state_label"] = "Semana actual"
        else:
            group["state"] = "neutral"
            group["state_label"] = "Próxima"
        result.append(group)
    return result


def _stage_summary(cycle):
    items = list(cycle.items.all()) if cycle else []
    total = len(items)
    design_done = sum(1 for item in items if item.ready)
    marketing_done = sum(1 for item in items if item.is_complete)
    return {
        "total": total,
        "design_done": design_done,
        "marketing_done": marketing_done,
        "design_percent": round(design_done * 100 / total) if total else 0,
        "marketing_percent": round(marketing_done * 100 / total) if total else 0,
        "overall_percent": round((design_done + marketing_done) * 50 / total) if total else 0,
    }


def _sync_project_link(*, assignment, project, user):
    # Una suscripción debe quedar vinculada a un solo proyecto + plan. Si al
    # editar se cambia el plan, limpiamos el vínculo anterior del mismo proyecto
    # para evitar que la suscripción aparezca duplicada.
    links = assignment.project_links.all()
    if project:
        links.exclude(project=project, plan=assignment.plan).update(subscription=None)
        ProjectPlanAssignment.objects.update_or_create(
            project=project,
            plan=assignment.plan,
            defaults={
                "subscription": assignment,
                "agreed_price": assignment.agreed_price,
                "is_active": True,
                "created_by": user,
            },
        )
    else:
        links.update(subscription=None)


def _social_plan_catalog(form):
    """Datos de solo lectura para previsualizar entregables del catálogo."""
    return [
        {
            "id": plan.pk,
            "name": plan.name,
            "posts": int(plan.weekly_posts or 0),
            "videos": int(plan.weekly_videos or 0),
            "label": plan.content_goal_label,
        }
        for plan in form.fields["plan"].queryset
    ]


@social_media_required
def dashboard(request):
    qs = (
        ClientPlan.objects.select_related("client", "plan", "assigned_design_user")
        .filter(plan__service_type=ServiceType.SOCIAL_MEDIA)
        .prefetch_related("project_links__project", "social_media_cycles__items")
        .order_by("client__business_name", "plan__name")
    )
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    if q:
        qs = qs.filter(
            Q(client__business_name__icontains=q)
            | Q(plan__name__icontains=q)
            | Q(project_links__project__name__icontains=q)
            | Q(project_links__project__project_code__icontains=q)
        ).distinct()

    rows = []
    totals = {"subscriptions": 0, "content": 0, "design_pending": 0, "marketing_pending": 0, "complete": 0}
    for assignment in qs:
        cycle = ensure_current_social_media_cycle(assignment)
        summary = _stage_summary(cycle)
        project = _project_for_assignment(assignment)
        row_status = "complete" if summary["total"] and summary["marketing_done"] == summary["total"] else (
            "marketing" if summary["design_done"] == summary["total"] and summary["total"] else "design"
        )
        if status != "all" and row_status != status:
            continue
        urgency = renewal_urgency(assignment.renewal_date)
        rows.append({
            "assignment": assignment,
            "project": project,
            "cycle": cycle,
            "summary": summary,
            "status": row_status,
            "urgency": urgency,
        })
        totals["subscriptions"] += 1
        totals["content"] += summary["total"]
        totals["design_pending"] += max(summary["total"] - summary["design_done"], 0)
        totals["marketing_pending"] += max(summary["total"] - summary["marketing_done"], 0)
        totals["complete"] += summary["marketing_done"]

    return render(request, "socialmedia/dashboard.html", {
        "rows": rows,
        "totals": totals,
        "search_query": q,
        "selected_status": status,
        "can_manage_design": request.user.is_manager or request.user.role == "design",
        "can_manage_marketing": request.user.is_manager or request.user.role == "marketing",
    })


@social_media_required
def subscription_create(request):
    project = None
    # Solo fijamos/ocultamos proyecto cuando la pantalla se abrió desde un
    # proyecto concreto. En un POST normal el formulario conserva Cliente ->
    # Proyecto como campos dependientes y valida la relación en servidor.
    project_id = request.GET.get("project")
    if project_id:
        project = Project.objects.select_related("client").filter(pk=project_id).first()
    initial = {}
    if request.GET.get("plan"):
        initial["plan"] = request.GET.get("plan")
    form = SocialMediaAssignmentForm(request.POST or None, project=project, initial=initial)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.created_by = request.user
        assignment.save()
        selected_project = form.cleaned_data.get("project") or project
        _sync_project_link(assignment=assignment, project=selected_project, user=request.user)
        ensure_current_social_media_cycle(assignment)
        log_activity(request.user, "social_media", "subscription_create", assignment)
        messages.success(request, "Suscripción de Social Media creada y distribuida por semanas.")
        return redirect("socialmedia:detail", pk=assignment.pk)
    return render(request, "socialmedia/form.html", {
        "form": form,
        "title": "Nueva suscripción de Social Media",
        "subtitle": "Selecciona cliente, proyecto y un plan ya creado en Planes. Posts y videos se leen del catálogo y se distribuyen automáticamente.",
        "project": project,
        "social_plan_catalog": _social_plan_catalog(form),
    })


@social_media_required
def subscription_edit(request, pk):
    assignment = get_object_or_404(
        ClientPlan.objects.select_related("client", "plan"),
        pk=pk,
        plan__service_type=ServiceType.SOCIAL_MEDIA,
    )
    project = _project_for_assignment(assignment)
    form = SocialMediaAssignmentForm(request.POST or None, instance=assignment, project=project)
    if request.method == "POST" and form.is_valid():
        assignment = form.save()
        selected_project = form.cleaned_data.get("project") or project
        _sync_project_link(assignment=assignment, project=selected_project, user=request.user)
        ensure_current_social_media_cycle(assignment)
        log_activity(request.user, "social_media", "subscription_update", assignment)
        messages.success(request, "Suscripción actualizada.")
        return redirect("socialmedia:detail", pk=assignment.pk)
    return render(request, "socialmedia/form.html", {
        "form": form,
        "title": "Editar suscripción de Social Media",
        "subtitle": assignment.client.business_name,
        "assignment": assignment,
        "project": project,
        "social_plan_catalog": _social_plan_catalog(form),
    })


@social_media_required
def subscription_detail(request, pk):
    assignment = get_object_or_404(
        ClientPlan.objects.select_related("client", "plan", "created_by", "assigned_design_user"),
        pk=pk,
        plan__service_type=ServiceType.SOCIAL_MEDIA,
    )
    project = _project_for_assignment(assignment)
    cycle = ensure_current_social_media_cycle(assignment)
    network_labels = dict(SOCIAL_NETWORK_CHOICES)
    selected_networks = [
        {"key": key, "label": network_labels.get(key, key)}
        for key in (assignment.social_networks or [])
    ]
    can_design = request.user.is_manager or request.user.role == "design"
    can_marketing = request.user.is_manager or request.user.role == "marketing"

    if request.method == "POST" and cycle:
        blocked_publications = 0
        for item in cycle.items.all():
            changed_fields = []
            if can_design:
                requested_ready = request.POST.get(f"ready_{item.pk}") == "1"
                # Una pieza ya publicada no vuelve a producción para no borrar el
                # historial operativo de Marketing.
                if item.published_networks and not requested_ready:
                    requested_ready = True
                if requested_ready != item.ready:
                    item.ready = requested_ready
                    changed_fields.append("ready")

            if can_marketing:
                requested_published = [
                    key for key in (assignment.social_networks or [])
                    if request.POST.get(f"network_{item.pk}_{key}") == "1"
                ]
                if requested_published and not item.ready:
                    blocked_publications += 1
                    requested_published = item.published_networks or []
                if requested_published != (item.published_networks or []):
                    item.published_networks = requested_published
                    changed_fields.append("published_networks")

            notes = (request.POST.get(f"notes_{item.pk}") or item.notes or "").strip()[:300]
            if notes != item.notes:
                item.notes = notes
                changed_fields.append("notes")

            if changed_fields:
                item.updated_by = request.user
                item.save(update_fields=changed_fields + ["updated_by", "updated_at"])

        cycle.updated_by = request.user
        cycle.save(update_fields=["updated_by", "updated_at"])
        log_activity(request.user, "social_media", "progress_update", assignment)
        if blocked_publications:
            messages.warning(request, f"{blocked_publications} publicación(es) no se marcaron porque Diseño todavía no terminó la pieza.")
        messages.success(request, "Avance de Social Media guardado.")
        return redirect("socialmedia:detail", pk=assignment.pk)

    summary = _stage_summary(cycle)
    return render(request, "socialmedia/detail.html", {
        "assignment": assignment,
        "project": project,
        "cycle": cycle,
        "summary": summary,
        "week_groups": _week_groups(cycle, assignment),
        "selected_networks": selected_networks,
        "urgency": renewal_urgency(assignment.renewal_date),
        "today": timezone.localdate(),
        "can_design": can_design,
        "can_marketing": can_marketing,
    })
