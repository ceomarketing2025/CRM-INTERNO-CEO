from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.core.decorators import manager_required
from apps.projects.models import Project
from apps.projects.selectors import project_area_flags
from apps.projects.services import sync_project_area_records

from .forms import AREA_ROLE_MAP, ManagementTaskForm
from .models import ActivityLog, GeneralAuditCheck, ManagementTask
from .services import (
    build_project_audit_rows,
    log_activity,
    review_general_audit_check,
    subscription_audit_rows,
)


@manager_required
def project_audit(request):
    """Auditoría de Gerencia para trabajo único, agrupado por módulo real."""
    for project in (
        Project.objects.exclude(status="cancelled")
        .select_related("client")
        .prefetch_related("contracted_plans__plan")
    ):
        sync_project_area_records(project, request.user)

    all_rows = build_project_audit_rows()
    q = (request.GET.get("q") or "").strip().lower()
    selected_area = (request.GET.get("area") or "all").strip().lower()
    status = (request.GET.get("status") or "all").strip().lower()

    def row_matches(row):
        if q and not (
            q in row["client"].business_name.lower()
            or q in row["project"].project_code.lower()
            or q in row["project"].name.lower()
            or q in row["category"].lower()
            or q in row["label"].lower()
            or q in (row.get("detail") or "").lower()
        ):
            return False
        if selected_area in {"design", "development", "marketing"} and row["area"] != selected_area:
            return False
        if status == "pending" and row["audit_decision"] != GeneralAuditCheck.Decision.PENDING:
            return False
        if status == "approved" and not (row["audit_current"] and row["audit_decision"] == GeneralAuditCheck.Decision.APPROVED):
            return False
        if status == "rejected" and not (row["audit_current"] and row["audit_decision"] == GeneralAuditCheck.Decision.REJECTED):
            return False
        if status == "changed" and not (
            row["audit_decision"] != GeneralAuditCheck.Decision.PENDING and not row["audit_current"]
        ):
            return False
        if status == "source_pending" and row["source_progress"] >= 100:
            return False
        if status == "source_done" and row["source_progress"] < 100:
            return False
        return True

    rows_by_project = OrderedDict()
    for row in all_rows:
        rows_by_project.setdefault(row["project"].pk, []).append(row)

    area_meta = [
        ("design", "Diseño"),
        ("marketing", "Marketing"),
        ("development", "Desarrollo"),
    ]

    def progress_state(progress, applies=True):
        if not applies:
            return "neutral"
        if progress >= 100:
            return "green"
        if progress >= 50:
            return "yellow"
        return "red"

    projects = []
    total_current = source_progress_sum = reviewed_current = 0
    approved_current = rejected_current = 0
    area_totals = {
        key: {"progress_sum": 0, "projects": 0, "tasks": 0, "reviewed": 0, "approved": 0, "rejected": 0}
        for key, _ in area_meta
    }

    for _project_id, project_rows in rows_by_project.items():
        project = project_rows[0]["project"]
        flags = project_area_flags(project)
        area_cards = []
        overall_parts = []
        visible_project = False

        for area_key, area_label in area_meta:
            area_rows_all = [row for row in project_rows if row["area"] == area_key]
            current_rows = [row for row in area_rows_all if row["counts_for_progress"]]
            applies = bool(flags.get(area_key) or current_rows)
            progress = round(sum(row["source_progress"] for row in current_rows) / len(current_rows)) if current_rows else 0
            current_reviewed = sum(1 for row in current_rows if row["audit_current"])
            current_approved = sum(
                1 for row in current_rows
                if row["audit_current"] and row["audit_decision"] == GeneralAuditCheck.Decision.APPROVED
            )
            current_rejected = sum(
                1 for row in current_rows
                if row["audit_current"] and row["audit_decision"] == GeneralAuditCheck.Decision.REJECTED
            )
            audit_progress = round(current_reviewed * 100 / len(current_rows)) if current_rows else 0

            if applies:
                overall_parts.append(progress)
                stats = area_totals[area_key]
                stats["progress_sum"] += progress
                stats["projects"] += 1
                stats["tasks"] += len(current_rows)
                stats["reviewed"] += current_reviewed
                stats["approved"] += current_approved
                stats["rejected"] += current_rejected

            display_rows = [row for row in area_rows_all if row_matches(row)]
            if display_rows:
                visible_project = True

            categories = OrderedDict()
            for row in display_rows:
                categories.setdefault(row["category"], []).append(row)

            area_cards.append({
                "key": area_key,
                "label": area_label,
                "applies": applies,
                "progress": progress,
                "state": progress_state(progress, applies),
                "audit_progress": audit_progress,
                "current_total": len(current_rows),
                "current_done": sum(1 for row in current_rows if row["source_progress"] >= 100),
                "current_reviewed": current_reviewed,
                "current_approved": current_approved,
                "current_rejected": current_rejected,
                "rows": display_rows,
                "categories": [{"name": name, "rows": items} for name, items in categories.items()],
            })

        if not (q or selected_area != "all" or status != "all"):
            visible_project = True
        if not visible_project:
            continue

        overall = round(sum(overall_parts) / len(overall_parts)) if overall_parts else 0
        current_project_rows = [row for row in project_rows if row["counts_for_progress"]]
        project_reviewed = sum(1 for row in current_project_rows if row["audit_current"])
        project_approved = sum(
            1 for row in current_project_rows
            if row["audit_current"] and row["audit_decision"] == GeneralAuditCheck.Decision.APPROVED
        )
        project_rejected = sum(
            1 for row in current_project_rows
            if row["audit_current"] and row["audit_decision"] == GeneralAuditCheck.Decision.REJECTED
        )
        total_current += len(current_project_rows)
        source_progress_sum += sum(row["source_progress"] for row in current_project_rows)
        reviewed_current += project_reviewed
        approved_current += project_approved
        rejected_current += project_rejected
        projects.append({
            "project": project,
            "areas": area_cards,
            "overall": overall,
            "overall_state": progress_state(overall, bool(overall_parts)),
            "applicable_areas": len(overall_parts),
            "current_tasks": len(current_project_rows),
            "reviewed_tasks": project_reviewed,
            "approved_tasks": project_approved,
            "rejected_tasks": project_rejected,
            "pending_tasks": max(len(current_project_rows) - project_reviewed, 0),
        })

    projects.sort(key=lambda item: item["project"].client.business_name.lower())
    source_progress = round(source_progress_sum / total_current) if total_current else 0
    audit_progress = round(reviewed_current * 100 / total_current) if total_current else 0
    area_stats = []
    for key, label in area_meta:
        stat = area_totals[key]
        area_stats.append({
            "key": key,
            "label": label,
            "projects": stat["projects"],
            "tasks": stat["tasks"],
            "progress": round(stat["progress_sum"] / stat["projects"]) if stat["projects"] else 0,
            "audit_progress": round(stat["reviewed"] * 100 / stat["tasks"]) if stat["tasks"] else 0,
            "approved": stat["approved"],
            "rejected": stat["rejected"],
        })

    return render(request, "audit/project_audit.html", {
        "projects": projects,
        "project_count": len(projects),
        "total": total_current,
        "source_progress": source_progress,
        "reviewed": reviewed_current,
        "approved": approved_current,
        "rejected": rejected_current,
        "audit_progress": audit_progress,
        "needs_review": max(total_current - reviewed_current, 0),
        "area_stats": area_stats,
        "selected_area": selected_area,
        "selected_status": status,
        "search_query": request.GET.get("q", ""),
    })


@manager_required
def project_audit_check(request, pk):
    if request.method != "POST":
        return redirect("audit:projects")
    check = get_object_or_404(
        GeneralAuditCheck.objects.select_related("project__client"),
        pk=pk,
    )
    action = (request.POST.get("action") or "approved").strip().lower()
    if action == "reopen":
        decision = GeneralAuditCheck.Decision.PENDING
    elif action == "rejected":
        decision = GeneralAuditCheck.Decision.REJECTED
    else:
        decision = GeneralAuditCheck.Decision.APPROVED

    note = (request.POST.get("note") or "").strip()
    if decision == GeneralAuditCheck.Decision.REJECTED and not note:
        messages.error(request, "Para rechazar una auditoría debes indicar la observación o corrección requerida.")
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        return redirect(next_url or "audit:projects")

    # Las tareas con workflow solo pueden aprobarse/rechazarse cuando el
    # responsable las envió explícitamente a Para revisión.
    if decision in {GeneralAuditCheck.Decision.APPROVED, GeneralAuditCheck.Decision.REJECTED}:
        source_key = check.source_key or ""
        if source_key.startswith("design:task:"):
            parts = source_key.split(":")
            if len(parts) == 3 and parts[2].isdigit():
                from apps.design.models import DesignTask
                source_task = DesignTask.objects.filter(pk=int(parts[2])).first()
                if source_task and source_task.status != DesignTask.Status.REVIEW:
                    messages.error(request, "Esta actividad de Diseño todavía no está en Para revisión.")
                    return redirect(request.POST.get("next") or "audit:projects")
        elif source_key.startswith("management:task:"):
            parts = source_key.split(":")
            if len(parts) == 3 and parts[2].isdigit():
                source_task = ManagementTask.objects.filter(pk=int(parts[2])).first()
                if source_task and source_task.status != ManagementTask.Status.REVIEW:
                    messages.error(request, "Esta tarea todavía no está en Para revisión.")
                    return redirect(request.POST.get("next") or "audit:projects")

    review_general_audit_check(
        check=check,
        user=request.user,
        decision=decision,
        note=note,
    )
    label = dict(GeneralAuditCheck.Decision.choices).get(decision, "Actualizado")
    log_activity(
        request.user,
        "audit",
        f"project_audit_{decision}",
        check.project,
        description=f"{check.project.client.business_name} · {check.area} · {check.label} · {label}",
        metadata={"source_key": check.source_key, "audit_check_id": check.pk, "decision": decision},
    )
    messages.success(request, f"Auditoría guardada: {label}.")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    return redirect(next_url or "audit:projects")


@manager_required
def management_task_list(request):
    tasks = ManagementTask.objects.select_related("assigned_to", "client", "project", "created_by")
    q = (request.GET.get("q") or "").strip()
    area = (request.GET.get("area") or "all").strip()
    status = (request.GET.get("status") or "all").strip()

    if q:
        tasks = tasks.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(assigned_to__first_name__icontains=q)
            | Q(assigned_to__last_name__icontains=q)
            | Q(assigned_to__email__icontains=q)
            | Q(client__business_name__icontains=q)
            | Q(project__name__icontains=q)
            | Q(project__project_code__icontains=q)
        )
    if area != "all":
        tasks = tasks.filter(area=area)
    if status != "all":
        tasks = tasks.filter(status=status)

    base = ManagementTask.objects.all()
    stats = {
        "total": base.count(),
        "pending": base.filter(status=ManagementTask.Status.TODO).count(),
        "doing": base.filter(status=ManagementTask.Status.DOING).count(),
        "paused": base.filter(status=ManagementTask.Status.PAUSED).count(),
        "changes": base.filter(status=ManagementTask.Status.CHANGES).count(),
        "review": base.filter(status=ManagementTask.Status.REVIEW).count(),
        "done": base.filter(status=ManagementTask.Status.DONE).count(),
    }
    return render(request, "audit/management_task_list.html", {
        "tasks": tasks,
        "stats": stats,
        "search_query": q,
        "selected_area": area,
        "selected_status": status,
        "area_choices": ManagementTask.Area.choices,
        "status_choices": ManagementTask.Status.choices,
    })


@manager_required
def management_task_create(request):
    initial = {}
    if request.GET.get("area"):
        initial["area"] = request.GET.get("area")
    if request.GET.get("client"):
        initial["client"] = request.GET.get("client")
    if request.GET.get("project"):
        initial["project"] = request.GET.get("project")
    form = ManagementTaskForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.created_by = request.user
        task.updated_by = request.user
        task.save()
        log_activity(
            request.user,
            "management_tasks",
            "create",
            task.project or task,
            description=f"{task.get_area_display()} · {task.title} · {task.assigned_to.display_name if task.assigned_to else 'Sin responsable'}",
            metadata={"management_task_id": task.pk, "area": task.area},
        )
        messages.success(request, "Tarea creada y enviada al área correspondiente.")
        return redirect("audit:management_tasks")
    return render(request, "audit/management_task_form.html", {
        "form": form,
        "title": "Crear tarea para el equipo",
        "task": None,
    })


@manager_required
def management_task_edit(request, pk):
    task = get_object_or_404(ManagementTask, pk=pk)
    form = ManagementTaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.updated_by = request.user
        task.save()
        log_activity(
            request.user,
            "management_tasks",
            "update",
            task.project or task,
            description=f"{task.get_area_display()} · {task.title}",
            metadata={"management_task_id": task.pk, "area": task.area},
        )
        messages.success(request, "Tarea actualizada.")
        return redirect("audit:management_tasks")
    return render(request, "audit/management_task_form.html", {
        "form": form,
        "title": "Editar tarea del equipo",
        "task": task,
    })


@login_required
def management_task_status(request, pk):
    if request.method != "POST":
        return redirect("dashboard:home")
    task = get_object_or_404(ManagementTask.objects.select_related("assigned_to", "project"), pk=pk)
    user = request.user
    if not (user.is_manager or user.is_superuser or task.assigned_to_id == user.pk):
        raise PermissionDenied("Esta tarea no está asignada a tu usuario.")

    action = (request.POST.get("action") or "").strip().lower()
    note = (request.POST.get("note") or "").strip()
    old_status = task.status

    if action:
        if action in {"start", "resume"}:
            if task.status not in {ManagementTask.Status.TODO, ManagementTask.Status.PAUSED, ManagementTask.Status.CHANGES}:
                messages.warning(request, "La tarea no puede iniciarse desde su estado actual.")
                return redirect(request.POST.get("next") or "dashboard:home")
            task.status = ManagementTask.Status.DOING
            task.status_note = ""
        elif action == "pause":
            if task.status not in {ManagementTask.Status.DOING, ManagementTask.Status.CHANGES, ManagementTask.Status.REVIEW}:
                messages.warning(request, "Primero debes iniciar la tarea para poder pausarla.")
                return redirect(request.POST.get("next") or "dashboard:home")
            if not note:
                messages.error(request, "Indica el motivo de la pausa.")
                return redirect(request.POST.get("next") or "dashboard:home")
            task.status = ManagementTask.Status.PAUSED
            task.status_note = note
        elif action == "review":
            if task.status not in {ManagementTask.Status.DOING, ManagementTask.Status.CHANGES}:
                messages.warning(request, "La tarea debe estar en proceso antes de enviarla a revisión.")
                return redirect(request.POST.get("next") or "dashboard:home")
            task.status = ManagementTask.Status.REVIEW
            task.status_note = ""
        elif action == "close" and (user.is_manager or user.is_superuser):
            task.status = ManagementTask.Status.DONE
            task.status_note = ""
        else:
            messages.error(request, "Acción de estado inválida.")
            return redirect(request.POST.get("next") or "dashboard:home")
    else:
        # Compatibilidad con paneles antiguos de otras áreas que todavía envían
        # un select de estado. Diseño ya usa el workflow por acciones.
        new_status = (request.POST.get("status") or "").strip()
        allowed = {choice[0] for choice in ManagementTask.Status.choices}
        if new_status not in allowed:
            messages.error(request, "Estado inválido.")
            return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard:home")
        task.status = new_status
        if new_status not in {ManagementTask.Status.PAUSED, ManagementTask.Status.CHANGES}:
            task.status_note = ""

    task.updated_by = user
    task.save(update_fields=["status", "status_note", "updated_by", "updated_at"])
    description = f"{dict(ManagementTask.Status.choices).get(old_status, old_status)} → {task.get_status_display()}"
    if note:
        description += f" · {note}"
    log_activity(
        user,
        "management_tasks",
        "status",
        task.project or task,
        description=f"{task.title} · {description}",
        metadata={"management_task_id": task.pk, "area": task.area, "from": old_status, "to": task.status},
    )
    messages.success(request, f"Estado actualizado: {task.get_status_display()}.")
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "dashboard:home")


@manager_required
def management_task_options(request):
    area = (request.GET.get("area") or "").strip()
    client_id = (request.GET.get("client") or "").strip()
    role = AREA_ROLE_MAP.get(area)
    users = UserAccount.objects.filter(is_active=True)
    if role:
        users = users.filter(role=role)
    else:
        users = users.none()
    responsibles = [
        {"id": user.pk, "label": f"{user.display_name} · {user.get_role_display()}"}
        for user in users.order_by("first_name", "last_name", "email")
    ]

    projects = Project.objects.none()
    if client_id.isdigit():
        projects = Project.objects.filter(client_id=int(client_id)).order_by("name")
    project_rows = [
        {"id": project.pk, "label": f"{project.project_code} · {project.name}"}
        for project in projects
    ]
    return JsonResponse({"responsibles": responsibles, "projects": project_rows})


@manager_required
def subscription_audit_check(request, pk):
    """Aprueba/rechaza una semana de una suscripción usando el check vivo."""
    if request.method != "POST":
        return redirect("audit:subscriptions")
    check = get_object_or_404(
        GeneralAuditCheck.objects.select_related("project__client"),
        pk=pk,
        area="social_media",
    )
    action = (request.POST.get("action") or "approved").strip().lower()
    if action == "reopen":
        decision = GeneralAuditCheck.Decision.PENDING
    elif action == "rejected":
        decision = GeneralAuditCheck.Decision.REJECTED
    else:
        decision = GeneralAuditCheck.Decision.APPROVED

    note = (request.POST.get("note") or "").strip()
    if decision == GeneralAuditCheck.Decision.REJECTED and not note:
        messages.error(request, "Para rechazar una semana debes indicar qué debe corregirse.")
        return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "audit:subscriptions")

    review_general_audit_check(check=check, user=request.user, decision=decision, note=note)
    label = dict(GeneralAuditCheck.Decision.choices).get(decision, "Actualizado")
    log_activity(
        request.user,
        "audit",
        f"subscription_audit_{decision}",
        check.project,
        description=f"{check.project.client.business_name} · {check.category} · {check.label} · {label}",
        metadata={"source_key": check.source_key, "audit_check_id": check.pk, "decision": decision},
    )
    messages.success(request, f"Auditoría de suscripción guardada: {label}.")
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or "audit:subscriptions")


@manager_required
def subscription_audit(request):
    """Auditoría de renovaciones y ciclos recurrentes."""
    rows, totals = subscription_audit_rows()
    q = (request.GET.get("q") or "").strip().lower()
    kind = (request.GET.get("kind") or "all").strip().lower()
    status = (request.GET.get("status") or "all").strip().lower()
    audit_status = (request.GET.get("audit") or "all").strip().lower()

    filtered = []
    for row in rows:
        assignment = row["assignment"]
        project = row["project"]
        haystack = " ".join([
            assignment.client.business_name,
            assignment.plan.name,
            project.project_code if project else "",
            project.name if project else "",
        ]).lower()
        if q and q not in haystack:
            continue
        if kind == "social" and not row["is_social"]:
            continue
        if kind == "other" and row["is_social"]:
            continue
        if status == "alert" and row["state"] != "red":
            continue
        if status == "current" and row["state"] != "yellow":
            continue
        if status == "complete" and row["state"] != "green":
            continue
        if audit_status != "all":
            if not row["is_social"]:
                continue
            def audit_matches(week):
                if audit_status == "pending":
                    return week.get("audit_decision") == GeneralAuditCheck.Decision.PENDING
                if audit_status == "approved":
                    return week.get("audit_current") and week.get("audit_decision") == GeneralAuditCheck.Decision.APPROVED
                if audit_status == "rejected":
                    return week.get("audit_current") and week.get("audit_decision") == GeneralAuditCheck.Decision.REJECTED
                if audit_status == "changed":
                    return week.get("audit_decision") != GeneralAuditCheck.Decision.PENDING and not week.get("audit_current")
                return True
            if not any(audit_matches(week) for week in row.get("weeks", [])):
                continue
        filtered.append(row)

    visible_weeks = [week for row in filtered if row["is_social"] for week in row.get("weeks", [])]
    filtered_totals = {
        "subscriptions": len(filtered),
        "social": sum(1 for row in filtered if row["is_social"]),
        "alerts": sum(1 for row in filtered if row["state"] == "red"),
        "complete": sum(1 for row in filtered if row["state"] == "green"),
        "design_pending": sum(max(row["total_items"] - row["design_done"], 0) for row in filtered if row["is_social"]),
        "marketing_pending": sum(max(row["total_items"] - row["marketing_done"], 0) for row in filtered if row["is_social"]),
        "audit_approved": sum(1 for week in visible_weeks if week.get("audit_current") and week.get("audit_decision") == GeneralAuditCheck.Decision.APPROVED),
        "audit_rejected": sum(1 for week in visible_weeks if week.get("audit_current") and week.get("audit_decision") == GeneralAuditCheck.Decision.REJECTED),
        "audit_pending": sum(1 for week in visible_weeks if week.get("audit_decision") == GeneralAuditCheck.Decision.PENDING),
        "audit_changed": sum(1 for week in visible_weeks if week.get("audit_decision") != GeneralAuditCheck.Decision.PENDING and not week.get("audit_current")),
    }

    return render(request, "audit/subscription_audit.html", {
        "rows": filtered,
        "totals": filtered_totals,
        "global_totals": totals,
        "search_query": request.GET.get("q", ""),
        "selected_kind": kind,
        "selected_status": status,
        "selected_audit": audit_status,
    })


@manager_required
def log_list(request):
    """Bitácora central de cambios para Gerencia/Configuración."""
    records = ActivityLog.objects.select_related("user").all()
    q = (request.GET.get("q") or "").strip()
    module = (request.GET.get("module") or "").strip()

    if q:
        records = records.filter(
            Q(description__icontains=q)
            | Q(action__icontains=q)
            | Q(module__icontains=q)
            | Q(entity_type__icontains=q)
            | Q(user__email__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )
    if module:
        records = records.filter(module=module)

    modules = list(
        ActivityLog.objects.exclude(module="")
        .order_by("module")
        .values_list("module", flat=True)
        .distinct()
    )
    page = Paginator(records, 80).get_page(request.GET.get("page"))
    return render(request, "audit/log_list.html", {
        "page": page,
        "modules": modules,
        "q": q,
        "selected_module": module,
    })
