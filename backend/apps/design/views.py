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
from .forms import DesignBriefForm, PaletteForm, PaletteQuickForm, DesignTaskForm
from .models import ColorPalette, DesignBrief, DesignTask, DesignTaskCycle, PaletteColor, SocialMediaContentItem, SocialMediaCycle
from .services import (
    build_palette_pdf, complete_design_brief, design_task_progress,
    ensure_current_design_task_cycle, ensure_current_social_media_cycle,
    ensure_default_design_tasks_for_project,
)


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
    """Tareas de Diseño con control simple y ciclos de publicación."""
    from django.db.models import Q
    from django.utils import timezone
    from apps.plans.models.choices import PlanDepartment

    today = timezone.localdate()
    plan_assignments = (
        ProjectPlanAssignment.objects
        .select_related("project__client", "plan")
        .prefetch_related("design_tasks__assigned_to", "design_tasks__cycles")
        .filter(is_active=True, plan__department=PlanDepartment.DESIGN)
        .order_by("project__client__business_name", "plan__name")
    )

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    if q:
        plan_assignments = plan_assignments.filter(
            Q(project__client__business_name__icontains=q)
            | Q(project__name__icontains=q)
            | Q(project__project_code__icontains=q)
            | Q(plan__name__icontains=q)
            | Q(design_tasks__title__icontains=q)
        ).distinct()

    # Repara automáticamente proyectos antiguos que ya tenían productos de Diseño
    # pero fueron creados antes de existir las tareas automáticas.
    seen_projects = set()
    for assignment in list(plan_assignments):
        if assignment.project_id not in seen_projects:
            ensure_default_design_tasks_for_project(assignment.project, user=request.user)
            seen_projects.add(assignment.project_id)

    # Recargamos para incluir las tareas recién creadas.
    plan_assignments = plan_assignments.prefetch_related("design_tasks__assigned_to", "design_tasks__cycles")

    rows = []
    task_states_all = []
    overdue_tasks = 0
    configuration_pending = 0
    for assignment in plan_assignments:
        task_rows = []
        for task in assignment.design_tasks.all().order_by("order", "id"):
            state = design_task_progress(task, today=today)
            if state["needs_configuration"]:
                configuration_pending += 1
            overdue = bool(
                task.task_type == DesignTask.TaskType.STANDARD
                and state["progress"] < 100
                and task.due_date
                and task.due_date < today
            )
            if overdue:
                overdue_tasks += 1

            recent_cycles = []
            if task.task_type == DesignTask.TaskType.CONTENT and not state["needs_configuration"]:
                current_cycle = state.get("cycle")
                recent_cycles = list(task.cycles.all().order_by("-period_start")[:6])
                for cycle in recent_cycles:
                    cycle.is_current_period = bool(current_cycle and cycle.pk == current_cycle.pk)

            include = True
            if status == "pending":
                include = state["progress"] < 100
            elif status == "done":
                include = state["progress"] == 100
            elif status == "overdue":
                include = overdue
            elif status == "configuration":
                include = state["needs_configuration"]
            elif status == "created":
                include = bool(state.get("cycle") and state["cycle"].content_created)
            elif status == "published":
                include = bool(state.get("cycle") and state["cycle"].content_published)
            if not include:
                continue

            task_rows.append({
                "task": task,
                "progress": state["progress"],
                "state": state["state"],
                "state_label": state["label"],
                "needs_configuration": state["needs_configuration"],
                "current_cycle": state.get("cycle"),
                "cycles": recent_cycles,
                "overdue": overdue,
            })
            task_states_all.append(state)

        if status != "all" and not task_rows:
            continue

        total = len(task_rows)
        progress = round(sum(item["progress"] for item in task_rows) / total) if total else 0
        rows.append({
            "assignment": assignment,
            "project": assignment.project,
            "plan": assignment.plan,
            "tasks": task_rows,
            "total": total,
            "done": sum(1 for item in task_rows if item["progress"] == 100),
            "progress": progress,
            "progress_state": "green" if progress == 100 else ("yellow" if progress > 50 else "red"),
        })

    total_tasks = len(task_states_all)
    completed_tasks = sum(1 for item in task_states_all if item["progress"] == 100)
    overall_progress = round(sum(item["progress"] for item in task_states_all) / total_tasks) if total_tasks else 0
    return render(request, "design/social_media.html", {
        "rows": rows,
        "today": today,
        "product_count": len(rows),
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": max(total_tasks - completed_tasks, 0),
        "overdue_tasks": overdue_tasks,
        "configuration_pending": configuration_pending,
        "overall_progress": overall_progress,
        "search_query": q,
        "selected_status": status,
    })


@role_required("design")
def design_task_create(request):
    initial = {}
    if request.GET.get("project_plan"):
        initial["project_plan"] = request.GET.get("project_plan")
    form = DesignTaskForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.created_by = request.user
        task.updated_by = request.user
        task.save()
        ensure_current_design_task_cycle(task)
        log_activity(request.user, "design", "design_task_create", task, task.title)
        messages.success(request, "Actividad de Diseño creada.")
        return redirect("design:tasks")
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Nueva tarea de Diseño",
        "subtitle": "Las tareas únicas se completan una vez. Para posts/contenido usa una frecuencia semanal, quincenal o mensual.",
    })


@role_required("design")
def design_task_edit(request, pk):
    task = get_object_or_404(DesignTask.objects.select_related("project_plan__project", "project_plan__plan"), pk=pk)
    if not can_access_project(request.user, task.project_plan.project):
        raise PermissionDenied("Esta tarea no pertenece a un proyecto asignado a Diseño.")
    form = DesignTaskForm(request.POST or None, instance=task, user=request.user)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.updated_by = request.user
        task.save()
        ensure_current_design_task_cycle(task)
        log_activity(request.user, "design", "design_task_update", task, task.title)
        messages.success(request, "Actividad actualizada.")
        return redirect("design:tasks")
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Editar tarea de Diseño",
        "subtitle": f"{task.project_plan.project.client.business_name} · {task.project_plan.plan.name}",
    })


@role_required("design")
def design_task_toggle(request, pk):
    if request.method != "POST":
        return redirect("design:tasks")
    task = get_object_or_404(DesignTask.objects.select_related("project_plan__project"), pk=pk)
    if not can_access_project(request.user, task.project_plan.project):
        raise PermissionDenied("Esta tarea no pertenece a un proyecto asignado a Diseño.")
    if task.task_type == DesignTask.TaskType.CONTENT:
        messages.warning(request, "Las tareas de contenido se controlan con los checks Creado y Publicado del periodo actual.")
        return redirect("design:tasks")
    task.status = DesignTask.Status.TODO if task.status == DesignTask.Status.DONE else DesignTask.Status.DONE
    task.updated_by = request.user
    task.save(update_fields=["status", "updated_by", "updated_at"])
    log_activity(request.user, "design", "design_task_toggle", task, task.get_status_display())
    return redirect("design:tasks")


@role_required("design")
def design_task_cycle_update(request, pk):
    if request.method != "POST":
        return redirect("design:tasks")
    cycle = get_object_or_404(
        DesignTaskCycle.objects.select_related("task__project_plan__project"),
        pk=pk,
    )
    if not can_access_project(request.user, cycle.task.project_plan.project):
        raise PermissionDenied("Este periodo no pertenece a un proyecto asignado a Diseño.")

    action = request.POST.get("action")
    if action == "toggle_created":
        cycle.content_created = not cycle.content_created
        if not cycle.content_created:
            cycle.content_published = False
    elif action == "toggle_published":
        cycle.content_published = not cycle.content_published
        if cycle.content_published:
            cycle.content_created = True
    cycle.updated_by = request.user
    cycle.save()
    log_activity(
        request.user,
        "design",
        "design_task_cycle_update",
        cycle.task,
        description=f"{cycle.label} · {cycle.state_label}",
        metadata={"cycle_id": cycle.pk},
    )
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    return redirect(next_url or "design:tasks")


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
