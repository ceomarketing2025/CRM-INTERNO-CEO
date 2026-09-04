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
from .models import ColorPalette, DesignBrief, DesignTask, DesignTaskCycle, DesignTaskCycleItem, PaletteColor, SocialMediaContentItem, SocialMediaCycle
from .services import (
    build_palette_pdf, complete_design_brief, design_task_progress,
    ensure_current_design_task_cycle, ensure_current_social_media_cycle,
    ensure_default_design_tasks_for_project, _refresh_design_cycle_summary,
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
    """Abre directamente el editor visual de paleta.

    Antes esta ruta mostraba un formulario intermedio para crear el nombre de la
    paleta. Para operación diaria solo necesitamos una paleta principal por
    proyecto: si no existe se crea y se abre inmediatamente.
    """
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")
    palette = ColorPalette.objects.filter(project=project, is_primary=True).order_by("id").first()
    if not palette:
        palette = ColorPalette.objects.create(
            project=project,
            name="Paleta principal",
            description="Paleta definida por el equipo de Diseño.",
            is_primary=True,
        )
        log_activity(request.user, "design", "palette_create", palette, "Paleta principal creada")
    return redirect("design:palette_detail", pk=palette.pk)


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
    """Dashboard compacto: una card por proyecto, sin desplegar tareas."""
    from django.db.models import Q
    from django.utils import timezone
    from apps.plans.models.choices import PlanDepartment

    today = timezone.localdate()
    projects = (
        projects_for_area("design")
        .prefetch_related(
            "contracted_plans__plan",
            "contracted_plans__design_tasks__assigned_to",
            "contracted_plans__design_tasks__cycles__delivery_items",
        )
        .filter(contracted_plans__is_active=True, contracted_plans__plan__department=PlanDepartment.DESIGN)
        .distinct()
        .order_by("client__business_name", "name")
    )
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "all").strip()
    if q:
        projects = projects.filter(
            Q(client__business_name__icontains=q)
            | Q(name__icontains=q)
            | Q(project_code__icontains=q)
            | Q(contracted_plans__plan__name__icontains=q)
            | Q(contracted_plans__design_tasks__title__icontains=q)
        ).distinct()

    # Repara tareas base de proyectos existentes y vuelve a consultar para que el
    # dashboard siempre refleje exactamente los servicios contratados actuales.
    project_ids = list(projects.values_list("pk", flat=True))
    for project in Project.objects.filter(pk__in=project_ids):
        ensure_default_design_tasks_for_project(project, user=request.user)

    projects = (
        Project.objects.filter(pk__in=project_ids)
        .select_related("client")
        .prefetch_related(
            "contracted_plans__plan",
            "contracted_plans__design_tasks__assigned_to",
            "contracted_plans__design_tasks__cycles__delivery_items",
        )
        .order_by("client__business_name", "name")
    )

    rows = []
    overall_parts = []
    for project in projects:
        service_rows = []
        assignments = [
            a for a in project.contracted_plans.all()
            if a.is_active and a.plan.department == PlanDepartment.DESIGN
        ]
        for assignment in assignments:
            states = []
            has_recurring = False
            for task in assignment.design_tasks.all():
                state = design_task_progress(task, today=today)
                states.append(state)
                has_recurring = has_recurring or task.task_type == DesignTask.TaskType.CONTENT
            progress = round(sum(item["progress"] for item in states) / len(states)) if states else 0
            if has_recurring:
                dot_state = "blue"
                status_label = "Renovación · al día" if progress >= 100 else "Renovación · pendiente"
            else:
                dot_state = "green" if progress >= 100 else "red"
                status_label = "Completado" if progress >= 100 else "Pendiente"
            service_rows.append({
                "assignment": assignment,
                "plan": assignment.plan,
                "progress": progress,
                "dot_state": dot_state,
                "status_label": status_label,
                "is_recurring": has_recurring,
            })

        if not service_rows:
            continue
        project_progress = round(sum(item["progress"] for item in service_rows) / len(service_rows))
        if status == "pending" and project_progress >= 100:
            continue
        if status == "done" and project_progress < 100:
            continue
        if status == "renewal" and not any(item["is_recurring"] for item in service_rows):
            continue
        state = "green" if project_progress >= 100 else ("yellow" if project_progress >= 50 else "red")
        task_updates = [
            task for assignment in assignments for task in assignment.design_tasks.all()
        ]
        last_task = max(task_updates, key=lambda task: task.updated_at, default=None)
        rows.append({
            "project": project,
            "services": service_rows,
            "service_count": len(service_rows),
            "progress": project_progress,
            "state": state,
            "last_task": last_task,
        })
        overall_parts.append(project_progress)

    overall_progress = round(sum(overall_parts) / len(overall_parts)) if overall_parts else 0
    visible_services = [service for row in rows for service in row["services"]]
    total_services = len(visible_services)
    completed_services = sum(1 for service in visible_services if service["progress"] >= 100)
    renewal_services = sum(1 for service in visible_services if service["is_recurring"])
    return render(request, "design/social_media.html", {
        "rows": rows,
        "project_count": len(rows),
        "total_services": total_services,
        "completed_services": completed_services,
        "pending_services": max(total_services - completed_services, 0),
        "renewal_services": renewal_services,
        "overall_progress": overall_progress,
        "search_query": q,
        "selected_status": status,
    })


def _design_task_audit_locked(task):
    """Una tarea única finalizada y aprobada por auditoría queda inmutable."""
    from apps.audit.models import GeneralAuditCheck
    if task.task_type != DesignTask.TaskType.STANDARD or task.status != DesignTask.Status.DONE:
        return False
    check = GeneralAuditCheck.objects.filter(
        source_key=f"design:task:{task.pk}", is_ready=True
    ).first()
    return bool(check and check.reviewed_at and check.reviewed_at >= task.updated_at)


def _cycle_week_groups(cycle):
    from collections import OrderedDict
    from datetime import timedelta
    groups = OrderedDict()
    for item in cycle.delivery_items.all().order_by("week_number", "content_type", "sequence"):
        bucket = groups.setdefault(item.week_number, {"number": item.week_number, "items": []})
        bucket["items"].append(item)
    result = []
    for number, bucket in groups.items():
        start = cycle.period_start + timedelta(days=(number - 1) * 7)
        end = min(start + timedelta(days=6), cycle.period_end)
        items = bucket["items"]
        created = sum(1 for item in items if item.content_created)
        published = sum(1 for item in items if item.content_published)
        progress = round(sum(100 if i.content_published else (50 if i.content_created else 0) for i in items) / len(items)) if items else 0
        result.append({
            "number": number,
            "label": f"Semana {number}",
            "start": start,
            "end": end,
            "items": items,
            "total": len(items),
            "created": created,
            "published": published,
            "progress": progress,
            "state": "green" if progress >= 100 else ("yellow" if progress > 0 else "red"),
        })
    return result


@role_required("design")
def design_project_tasks(request, project_pk):
    """Bitácora operativa de Diseño de un solo proyecto."""
    from django.utils import timezone
    from apps.plans.models.choices import PlanDepartment

    project = get_object_or_404(
        Project.objects.select_related("client").prefetch_related(
            "contracted_plans__plan",
            "contracted_plans__design_tasks__assigned_to",
            "contracted_plans__design_tasks__cycles__delivery_items__updated_by",
        ),
        pk=project_pk,
    )
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")
    ensure_default_design_tasks_for_project(project, user=request.user)
    # Recarga después de cualquier autocreación.
    project = Project.objects.select_related("client").prefetch_related(
        "contracted_plans__plan",
        "contracted_plans__design_tasks__assigned_to",
        "contracted_plans__design_tasks__cycles__delivery_items__updated_by",
    ).get(pk=project.pk)

    today = timezone.localdate()
    service_rows = []
    project_parts = []
    for assignment in project.contracted_plans.all():
        if not assignment.is_active or assignment.plan.department != PlanDepartment.DESIGN:
            continue
        task_rows = []
        task_parts = []
        for task in assignment.design_tasks.all().order_by("order", "id"):
            state = design_task_progress(task, today=today)
            current_cycle = state.get("cycle")
            if current_cycle:
                current_cycle = DesignTaskCycle.objects.prefetch_related("delivery_items__updated_by").get(pk=current_cycle.pk)
            week_groups = _cycle_week_groups(current_cycle) if current_cycle else []
            history = list(task.cycles.exclude(pk=getattr(current_cycle, "pk", None)).order_by("-period_start")[:6]) if task.task_type == DesignTask.TaskType.CONTENT else []
            locked = _design_task_audit_locked(task)
            task_rows.append({
                "task": task,
                "state": state,
                "cycle": current_cycle,
                "week_groups": week_groups,
                "history": history,
                "locked": locked,
            })
            task_parts.append(state["progress"])
        service_progress = round(sum(task_parts) / len(task_parts)) if task_parts else 0
        recurring = any(row["task"].task_type == DesignTask.TaskType.CONTENT for row in task_rows)
        service_rows.append({
            "assignment": assignment,
            "plan": assignment.plan,
            "tasks": task_rows,
            "progress": service_progress,
            "state": "blue" if recurring else ("green" if service_progress >= 100 else "red"),
            "recurring": recurring,
        })
        project_parts.append(service_progress)

    project_progress = round(sum(project_parts) / len(project_parts)) if project_parts else 0
    return render(request, "design/task_project_detail.html", {
        "project": project,
        "services": service_rows,
        "project_progress": project_progress,
        "project_state": "green" if project_progress >= 100 else ("yellow" if project_progress >= 50 else "red"),
        "today": today,
    })


@role_required("design")
def design_service_manage(request, project_pk):
    """Agrega/retira únicamente productos de Diseño desde la bitácora del área."""
    from apps.plans.models.choices import PlanDepartment
    project = get_object_or_404(Project.objects.select_related("client"), pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")
    plans = ServicePlan.objects.filter(is_active=True, department=PlanDepartment.DESIGN).order_by("service_type", "name")
    active_ids = set(project.contracted_plans.filter(is_active=True, plan__department=PlanDepartment.DESIGN).values_list("plan_id", flat=True))

    if request.method == "POST":
        selected_ids = {int(value) for value in request.POST.getlist("service_plans") if str(value).isdigit()}
        valid_ids = set(plans.values_list("pk", flat=True))
        selected_ids &= valid_ids
        actor = request.user if request.user.is_authenticated else None

        for plan in plans.filter(pk__in=selected_ids):
            ProjectPlanAssignment.objects.update_or_create(
                project=project,
                plan=plan,
                defaults={"is_active": True, "agreed_price": plan.base_price, "created_by": actor},
            )

        for assignment in project.contracted_plans.select_related("plan").filter(
            is_active=True, plan__department=PlanDepartment.DESIGN
        ).exclude(plan_id__in=selected_ids):
            protected = any(_design_task_audit_locked(task) for task in assignment.design_tasks.all())
            if protected:
                messages.warning(request, f"{assignment.plan.name} no se retiró porque contiene una tarea única completada y aprobada en Auditoría General.")
                continue
            assignment.is_active = False
            assignment.save(update_fields=["is_active", "updated_at"])
            log_activity(request.user, "design", "design_service_remove", assignment, assignment.plan.name)

        ensure_default_design_tasks_for_project(project, user=request.user)
        sync_project_area_records(project, request.user)
        log_activity(request.user, "design", "design_services_update", project, "Servicios de Diseño actualizados")
        messages.success(request, "Servicios de Diseño actualizados. La bitácora conservó todo el historial realizado.")
        return redirect("design:project_tasks", project_pk=project.pk)

    return render(request, "design/service_manage.html", {
        "project": project,
        "plans": plans,
        "active_ids": active_ids,
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
        return redirect("design:project_tasks", project_pk=task.project_plan.project_id)
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Nueva tarea de Diseño",
        "subtitle": "Las tareas únicas se completan una vez. El contenido recurrente se controla por periodo y por entregable.",
    })


@role_required("design")
def design_task_edit(request, pk):
    task = get_object_or_404(DesignTask.objects.select_related("project_plan__project", "project_plan__plan"), pk=pk)
    if not can_access_project(request.user, task.project_plan.project):
        raise PermissionDenied("Esta tarea no pertenece a un proyecto asignado a Diseño.")
    locked = _design_task_audit_locked(task)
    if locked and request.method == "POST":
        messages.error(request, "Esta tarea única ya fue completada y aprobada en Auditoría General. Quedó bloqueada como registro histórico.")
        return redirect("design:project_tasks", project_pk=task.project_plan.project_id)
    form = DesignTaskForm(request.POST or None, instance=task, user=request.user)
    if locked:
        for field in form.fields.values():
            field.disabled = True
        messages.info(request, "Registro protegido: la tarea fue completada y aprobada por Auditoría General.")
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.updated_by = request.user
        task.save()
        ensure_current_design_task_cycle(task)
        log_activity(request.user, "design", "design_task_update", task, task.title)
        messages.success(request, "Actividad actualizada y registrada en bitácora.")
        return redirect("design:project_tasks", project_pk=task.project_plan.project_id)
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Editar tarea de Diseño" if not locked else "Tarea protegida",
        "subtitle": f"{task.project_plan.project.client.business_name} · {task.project_plan.plan.name} · Última edición {task.updated_at:%d/%m/%Y %H:%M}",
    })


@role_required("design")
def design_task_toggle(request, pk):
    if request.method != "POST":
        return redirect("design:tasks")
    task = get_object_or_404(DesignTask.objects.select_related("project_plan__project"), pk=pk)
    if not can_access_project(request.user, task.project_plan.project):
        raise PermissionDenied("Esta tarea no pertenece a un proyecto asignado a Diseño.")
    if task.task_type == DesignTask.TaskType.CONTENT:
        messages.warning(request, "El contenido se completa con los checks Creado y Publicado de cada entregable.")
        return redirect("design:project_tasks", project_pk=task.project_plan.project_id)
    if _design_task_audit_locked(task):
        messages.error(request, "No se puede reabrir: esta tarea ya fue aprobada en Auditoría General.")
        return redirect("design:project_tasks", project_pk=task.project_plan.project_id)
    task.status = DesignTask.Status.TODO if task.status == DesignTask.Status.DONE else DesignTask.Status.DONE
    task.updated_by = request.user
    task.save(update_fields=["status", "updated_by", "updated_at"])
    log_activity(request.user, "design", "design_task_toggle", task, task.get_status_display())
    return redirect(request.POST.get("next") or "design:project_tasks", project_pk=task.project_plan.project_id) if not request.POST.get("next") else redirect(request.POST.get("next"))


@role_required("design")
def design_task_cycle_item_update(request, pk):
    if request.method != "POST":
        return redirect("design:tasks")
    item = get_object_or_404(
        DesignTaskCycleItem.objects.select_related("cycle__task__project_plan__project"), pk=pk
    )
    project = item.cycle.task.project_plan.project
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este entregable no pertenece a un proyecto asignado a Diseño.")
    action = request.POST.get("action")
    if action == "toggle_created":
        item.content_created = not item.content_created
        if not item.content_created:
            item.content_published = False
    elif action == "toggle_published":
        item.content_published = not item.content_published
        if item.content_published:
            item.content_created = True
    item.updated_by = request.user
    item.save()
    _refresh_design_cycle_summary(item.cycle, user=request.user, touch=True)
    log_activity(
        request.user,
        "design",
        "design_delivery_update",
        item.cycle.task,
        description=f"{item.cycle.label} · {item.get_content_type_display()} {item.sequence} · {'Publicado' if item.content_published else ('Creado' if item.content_created else 'Pendiente')}",
        metadata={"cycle_id": item.cycle_id, "delivery_item_id": item.pk},
    )
    return redirect(request.POST.get("next") or "design:project_tasks", project_pk=project.pk) if not request.POST.get("next") else redirect(request.POST.get("next"))


@role_required("design")
def design_task_cycle_update(request, pk):
    """Compatibilidad con los checks antiguos del ciclo completo."""
    if request.method != "POST":
        return redirect("design:tasks")
    cycle = get_object_or_404(DesignTaskCycle.objects.select_related("task__project_plan__project"), pk=pk)
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
    log_activity(request.user, "design", "design_task_cycle_update", cycle.task, description=f"{cycle.label} · {cycle.state_label}", metadata={"cycle_id": cycle.pk})
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
