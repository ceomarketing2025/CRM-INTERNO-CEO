from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import PermissionDenied
from apps.audit.models import ActivityLog
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.projects.models import Project, ProjectPlanAssignment
from apps.projects.selectors import can_access_project, projects_for_area
from apps.projects.services import sync_project_area_records
from apps.resources.models import ProjectResourceLink
from apps.plans.forms import SOCIAL_NETWORK_CHOICES, SocialMediaAssignmentForm
from apps.plans.models import ClientPlan, ServicePlan
from apps.plans.models.choices import PlanDepartment, ServiceType
from apps.plans.services import renewal_urgency
from .forms import DesignBriefForm, PaletteForm, PaletteQuickForm
from .models import ColorPalette, DesignBrief, PaletteColor, SocialMediaContentItem, SocialMediaCycle
from .services import build_palette_pdf, complete_design_brief, ensure_current_social_media_cycle


PALETTE_DEFAULTS = {
    "text": "#000000",
    "background": "#FFFFFF",
    "primary": "#0C3168",
    "secondary": "#C9CBD1",
    "accent": "#2571B7",
}
PALETTE_LABELS = {
    "text": "Texto",
    "background": "Fondo",
    "primary": "Primario",
    "secondary": "Secundario",
    "accent": "Acento",
}
PALETTE_USAGE = {
    "text": "Texto principal y contraste",
    "background": "Fondos y áreas neutras",
    "primary": "60% · secciones principales y llamados a la acción",
    "secondary": "30% · tarjetas, botones secundarios y apoyo visual",
    "accent": "10% · elementos clave, links y detalles",
}


def _palette_initial(palette):
    by_role = {c.role: c.hex_code for c in palette.colors.all()}
    return {
        "text_hex": by_role.get("text", PALETTE_DEFAULTS["text"]),
        "background_hex": by_role.get("background", PALETTE_DEFAULTS["background"]),
        "primary_hex": by_role.get("primary", PALETTE_DEFAULTS["primary"]),
        "secondary_hex": by_role.get("secondary", PALETTE_DEFAULTS["secondary"]),
        "accent_hex": by_role.get("accent", PALETTE_DEFAULTS["accent"]),
        "general_rules": palette.general_rules,
    }


def _upsert_palette_color(palette, role, hex_code, order):
    obj = palette.colors.filter(role=role).order_by("id").first()
    if obj:
        obj.label = PALETTE_LABELS[role]
        obj.hex_code = hex_code
        obj.usage = PALETTE_USAGE[role]
        obj.order = order
        obj.save(update_fields=["label", "hex_code", "usage", "order", "updated_at"])
        palette.colors.filter(role=role).exclude(pk=obj.pk).delete()
        return obj
    return PaletteColor.objects.create(
        palette=palette,
        role=role,
        label=PALETTE_LABELS[role],
        hex_code=hex_code,
        usage=PALETTE_USAGE[role],
        order=order,
    )


@role_required("design")
def design_list(request):
    # Un proyecto pertenece al área de Diseño cuando tiene al menos un plan activo
    # de Diseño contratado. Conservamos también las asignaciones históricas para no
    # ocultar proyectos creados antes del esquema multi-plan.
    projects = (
        projects_for_area("design")
        .prefetch_related(
            "color_palettes__colors",
            "resource_links",
            "image_references",
        )
        .order_by("-updated_at", "-created_at")
    )

    project_rows = []
    for project in projects:
        sync_project_area_records(project, request.user)
        try:
            brief = project.design_brief
        except DesignBrief.DoesNotExist:
            brief = None
        palette = next((p for p in project.color_palettes.all() if p.is_primary), None)
        roles = {c.role for c in palette.colors.all()} if palette else set()
        resource_kinds = {r.kind for r in project.resource_links.all() if r.area == ProjectResourceLink.Area.DESIGN}
        resources_ready = ProjectResourceLink.Kind.LOGO in resource_kinds and ProjectResourceLink.Kind.PALETTE_DRIVE in resource_kinds
        last_log = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user").first()
        design_plans = [
            assignment.plan
            for assignment in project.contracted_plans.all()
            if assignment.is_active and assignment.plan.department == PlanDepartment.DESIGN
        ]
        workflow_plans = [
            assignment.plan
            for assignment in project.contracted_plans.all()
            if assignment.is_active
        ]
        brief_done = bool(brief and brief.completed)
        palette_done = all(role in roles for role in PALETTE_DEFAULTS)
        design_steps = [
            ("Ficha de Diseño", brief_done),
            ("Paleta", palette_done),
            ("Links Diseño", resources_ready),
        ]
        design_done = sum(1 for _, done in design_steps if done)
        design_percent = round(design_done * 100 / len(design_steps))
        project_rows.append({
            "project": project,
            "design_plans": design_plans,
            "workflow_plans": workflow_plans,
            "brief_done": brief_done,
            "palette_done": palette_done,
            "resources_ready": resources_ready,
            "design_steps": design_steps,
            "design_done": design_done,
            "design_percent": design_percent,
            "photo_count": project.image_references.count(),
            "last_log": last_log,
            "palette": palette,
        })
    return render(request, "design/list.html", {"project_rows": project_rows})


@role_required("design")
def brief_edit(request, project_pk):
    project = get_object_or_404(Project.objects.select_related("client", "purchased_plan__plan"), pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")
    brief, _ = DesignBrief.objects.get_or_create(project=project)
    palette, _ = ColorPalette.objects.get_or_create(
        project=project,
        is_primary=True,
        defaults={"name": "Paleta principal", "description": "Paleta definida durante la asesoría visual."},
    )
    form = DesignBriefForm(request.POST or None, request.FILES or None, instance=brief)
    if request.method == "POST" and form.is_valid():
        brief = form.save()
        action = request.POST.get("action", "save")
        if action == "complete":
            complete_design_brief(brief=brief, user=request.user)
            log_activity(request.user, "design", "brief_complete", brief)
            messages.success(request, "Ficha de Diseño marcada como completa. Las demás áreas siguen trabajando de forma independiente.")
            return redirect("design:list")
        log_activity(request.user, "design", "brief_update", brief)
        messages.success(request, "Ficha de Diseño guardada.")
        return redirect("design:brief_edit", project_pk=project.pk)
    return render(request, "design/brief.html", {"form": form, "project": project, "brief": brief, "palette": palette})


@role_required("design")
def palette_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")
    form = PaletteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        palette = form.save(commit=False)
        palette.project = project
        if palette.is_primary:
            ColorPalette.objects.filter(project=project, is_primary=True).update(is_primary=False)
        palette.save()
        log_activity(request.user, "design", "palette_create", palette)
        messages.success(request, "Paleta creada.")
        return redirect("design:palette_detail", pk=palette.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Nueva paleta", "subtitle": project.name})


@role_required("design")
def palette_detail(request, pk):
    palette = get_object_or_404(ColorPalette.objects.select_related("project__client").prefetch_related("colors", "gradients"), pk=pk)
    if not can_access_project(request.user, palette.project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")

    form = PaletteQuickForm(initial=_palette_initial(palette))
    if request.method == "POST":
        form = PaletteQuickForm(request.POST)
        if form.is_valid():
            for order, role in enumerate(PALETTE_DEFAULTS, start=1):
                _upsert_palette_color(palette, role, form.cleaned_data[f"{role}_hex"], order)
            palette.general_rules = form.cleaned_data.get("general_rules", "")
            palette.is_primary = True
            palette.save(update_fields=["general_rules", "is_primary", "updated_at"])
            ColorPalette.objects.filter(project=palette.project, is_primary=True).exclude(pk=palette.pk).update(is_primary=False)
            log_activity(request.user, "design", "palette_update", palette)
            messages.success(request, "Paleta guardada. Ya puedes verla aquí o descargar el PDF.")
            return redirect("design:palette_detail", pk=pk)
    return render(request, "design/palette_detail.html", {"palette": palette, "form": form})


@role_required("design")
def palette_pdf(request, pk):
    palette = get_object_or_404(ColorPalette.objects.select_related("project__client", "project__design_brief").prefetch_related("colors", "gradients"), pk=pk)
    if not can_access_project(request.user, palette.project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")
    pdf_bytes = build_palette_pdf(palette.project, palette)
    filename = f"asesoria-visual-{palette.project.client.business_name}".lower().replace(" ", "-") + ".pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


@role_required("design")
def social_media_dashboard(request):
    from django.utils import timezone

    today = timezone.localdate()
    assignments = ClientPlan.objects.select_related("client", "plan", "created_by").filter(
        plan__service_type=ServiceType.SOCIAL_MEDIA,
        plan__department=PlanDepartment.DESIGN,
        is_active=True,
    ).order_by("client__business_name")

    rows = []
    total_items = 0
    completed_items = 0
    ready_clients = 0
    queue_clients = 0
    due_soon = 0
    overdue = 0

    for assignment in assignments:
        cycle = ensure_current_social_media_cycle(assignment, today=today)
        urgency = renewal_urgency(assignment.renewal_date, today=today)
        progress = cycle.progress_percent if cycle else 0
        item_count = cycle.items.count() if cycle else 0
        done_count = sum(1 for item in cycle.items.all() if item.is_complete) if cycle else 0
        project_link = assignment.project_links.select_related("project").first()
        total_items += item_count
        completed_items += done_count

        if cycle and cycle.completed:
            status = "Listo"
            status_class = "done"
            ready_clients += 1
        elif assignment.start_date and assignment.start_date > today:
            status = "Programado"
            status_class = "scheduled"
            queue_clients += 1
        elif urgency["class"] == "overdue":
            status = "Vencido"
            status_class = "overdue"
            overdue += 1
        else:
            status = "En cola"
            status_class = "queued"
            queue_clients += 1

        if urgency["days"] is not None and 0 <= urgency["days"] <= 2:
            due_soon += 1

        rows.append({
            "assignment": assignment,
            "project": project_link.project if project_link else None,
            "cycle": cycle,
            "urgency": urgency,
            "progress": progress,
            "item_count": item_count,
            "done_count": done_count,
            "status": status,
            "status_class": status_class,
        })

    overall_progress = round(completed_items * 100 / total_items) if total_items else 0
    social_plan_count = ServicePlan.objects.filter(
        department=PlanDepartment.DESIGN,
        service_type=ServiceType.SOCIAL_MEDIA,
        is_active=True,
    ).count()

    return render(request, "design/social_media.html", {
        "rows": rows,
        "active_clients": len(rows),
        "ready_clients": ready_clients,
        "queue_clients": queue_clients,
        "due_soon": due_soon,
        "overdue": overdue,
        "overall_progress": overall_progress,
        "completed_items": completed_items,
        "total_items": total_items,
        "social_plan_count": social_plan_count,
        "today": today,
    })


@role_required("design")
def social_media_assign(request):
    project = None
    project_id = request.GET.get("project") or request.POST.get("project")
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
        if selected_project:
            ProjectPlanAssignment.objects.update_or_create(
                project=selected_project,
                plan=assignment.plan,
                defaults={
                    "subscription": assignment,
                    "agreed_price": assignment.agreed_price,
                    "is_active": True,
                    "created_by": request.user,
                },
            )
        ensure_current_social_media_cycle(assignment)
        log_activity(request.user, "design", "social_media_assign", assignment)
        messages.success(request, "Suscripción Social Media configurada para el cliente.")
        return redirect("design:social_media")
    return render(request, "design/social_media_assignment.html", {
        "form": form,
        "title": "Configurar suscripción de Social Media",
        "subtitle": "Selecciona proyecto, plan, renovación y redes sociales. El próximo pago se calcula automáticamente.",
        "project": project,
    })


@role_required("design")
def social_media_assignment_edit(request, pk):
    assignment = get_object_or_404(
        ClientPlan.objects.select_related("client", "plan"),
        pk=pk,
        plan__service_type=ServiceType.SOCIAL_MEDIA,
    )
    current_link = assignment.project_links.select_related("project").first()
    bound_project = current_link.project if current_link else None
    form = SocialMediaAssignmentForm(request.POST or None, instance=assignment, project=bound_project)
    if request.method == "POST" and form.is_valid():
        assignment = form.save()
        selected_project = form.cleaned_data.get("project") or bound_project
        assignment.project_links.exclude(project=selected_project).update(subscription=None)
        if selected_project:
            ProjectPlanAssignment.objects.update_or_create(
                project=selected_project,
                plan=assignment.plan,
                defaults={
                    "subscription": assignment,
                    "agreed_price": assignment.agreed_price,
                    "is_active": True,
                    "created_by": request.user,
                },
            )
        ensure_current_social_media_cycle(assignment)
        log_activity(request.user, "design", "social_media_assignment_update", assignment)
        messages.success(request, "Suscripción actualizada.")
        return redirect("design:social_media_detail", pk=assignment.pk)
    return render(request, "design/social_media_assignment.html", {
        "form": form,
        "title": "Editar suscripción Social Media",
        "subtitle": assignment.client.business_name,
        "assignment": assignment,
        "project": bound_project,
    })


@role_required("design")
def social_media_detail(request, pk):
    from django.utils import timezone

    assignment = get_object_or_404(
        ClientPlan.objects.select_related("client", "plan", "created_by"),
        pk=pk,
        plan__service_type=ServiceType.SOCIAL_MEDIA,
    )
    project_link = assignment.project_links.select_related("project").first()
    cycle = ensure_current_social_media_cycle(assignment)
    network_labels = dict(SOCIAL_NETWORK_CHOICES)
    selected_networks = [
        {"key": key, "label": network_labels.get(key, key)}
        for key in (assignment.social_networks or [])
    ]

    if request.method == "POST" and cycle:
        for item in cycle.items.all():
            ready = request.POST.get(f"ready_{item.pk}") == "1"
            published = [
                key for key in (assignment.social_networks or [])
                if request.POST.get(f"network_{item.pk}_{key}") == "1"
            ]
            notes = (request.POST.get(f"notes_{item.pk}") or "").strip()[:300]
            changed = ready != item.ready or published != (item.published_networks or []) or notes != item.notes
            if changed:
                item.ready = ready
                item.published_networks = published
                item.notes = notes
                item.updated_by = request.user
                item.save(update_fields=["ready", "published_networks", "notes", "updated_by", "updated_at"])

        cycle.updated_by = request.user
        cycle.save(update_fields=["updated_by", "updated_at"])
        log_activity(request.user, "design", "social_media_progress", assignment)
        messages.success(request, "Avance de Social Media guardado.")
        return redirect("design:social_media_detail", pk=assignment.pk)

    urgency = renewal_urgency(assignment.renewal_date)
    items = list(cycle.items.all()) if cycle else []
    return render(request, "design/social_media_detail.html", {
        "assignment": assignment,
        "project": project_link.project if project_link else None,
        "cycle": cycle,
        "items": items,
        "selected_networks": selected_networks,
        "urgency": urgency,
        "today": timezone.localdate(),
    })
