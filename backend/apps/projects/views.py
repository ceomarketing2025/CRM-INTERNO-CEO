from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.models import ActivityLog
from apps.audit.services import log_activity
from apps.core.decorators import manager_required, role_required
from apps.design.models import DesignBrief
from apps.finance.services import project_payment_summary
from apps.marketing.models import MarketingWorkspace
from apps.operations.models import WebProductionSheet
from apps.plans.models.choices import PlanDepartment, ServiceType
from apps.questionnaires.models import ProjectQuestionnaire
from apps.questionnaires.services import WEBSITE_TEMPLATE_CODE, website_questionnaire_progress
from apps.resources.models import ProjectResourceLink
from .forms import ProjectAssignmentForm, ProjectForm, ProjectNoteForm
from .models import Project
from .selectors import can_access_project, visible_projects_for_user, project_area_flags
from .services import sync_project_area_records


REQUIRED_PALETTE_ROLES = {"text", "background", "primary", "secondary", "accent"}


def _contracted_by_department(project):
    groups = {value: [] for value, _ in PlanDepartment.choices}
    for assignment in project.contracted_plans.select_related("plan", "subscription").filter(is_active=True):
        groups.setdefault(assignment.plan.department, []).append(assignment)
    return groups


def _control_data(project, viewer=None):
    questionnaire = ProjectQuestionnaire.objects.filter(project=project).select_related("template").prefetch_related("answers__question").order_by("id").first()
    sheet = WebProductionSheet.objects.filter(project=project).prefetch_related("pages", "counties__services", "cities").first()
    brief = DesignBrief.objects.filter(project=project).first()
    palette = project.color_palettes.filter(is_primary=True).prefetch_related("colors").first()
    palette_roles = {c.role for c in palette.colors.all()} if palette else set()
    resource_kinds = set(ProjectResourceLink.objects.filter(project=project, area=ProjectResourceLink.Area.DESIGN).values_list("kind", flat=True))
    workspace = MarketingWorkspace.objects.filter(project=project).prefetch_related("checklist_items").first()
    contracted = _contracted_by_department(project)

    design_steps = [
        ("Ficha de Diseño", bool(brief and brief.completed)),
        ("Paleta", bool(palette and REQUIRED_PALETTE_ROLES.issubset(palette_roles))),
        ("Links Diseño", ProjectResourceLink.Kind.LOGO in resource_kinds and ProjectResourceLink.Kind.PALETTE_DRIVE in resource_kinds),
    ]
    design_done = sum(1 for _, ok in design_steps if ok)
    design_percent = round((design_done / len(design_steps)) * 100) if design_steps else 0

    marketing_total = workspace.checklist_items.count() if workspace else 0
    marketing_done = workspace.checklist_items.filter(status="complete").count() if workspace else 0
    marketing_percent = round((marketing_done / marketing_total) * 100) if marketing_total else 0

    if questionnaire and questionnaire.template.code == WEBSITE_TEMPLATE_CODE:
        technical_progress = website_questionnaire_progress(questionnaire)
    else:
        technical_complete = bool(questionnaire and questionnaire.status == "complete")
        technical_progress = {
            "complete": 1 if technical_complete else 0,
            "total": 1 if questionnaire else 0,
            "percent": 100 if technical_complete else 0,
        }

    if sheet:
        pages = list(sheet.pages.all())
        counties = list(sheet.counties.all())
        services = [service for county in counties for service in county.services.all()]
        cities = list(sheet.cities.all())
        production_rows = pages + counties + services + cities
        production_total = len(production_rows)
        production_done = sum(1 for row in production_rows if row.state == "complete")
        production_percent = round((production_done / production_total) * 100) if production_total else 0
    else:
        production_total = production_done = production_percent = 0

    development_percent = round((technical_progress["percent"] + production_percent) / 2)
    development_steps = [
        (f"Ficha técnica · {technical_progress['percent']}%", technical_progress["percent"] == 100),
        (f"Ficha producción · {production_percent}%", bool(sheet and production_percent == 100 and production_total)),
    ]
    development_done = sum(1 for _, ok in development_steps if ok)

    has_any_contract = any(contracted.values())
    admin_percent = 100 if has_any_contract or project.purchased_plan_id else 0

    # Las áreas que forman parte del flujo pesan en el porcentaje aunque el proyecto
    # web haya sido vendido con un único plan de Desarrollo.
    area_flags = project_area_flags(project)
    progress_parts = [admin_percent]
    if area_flags["design"]:
        progress_parts.append(design_percent)
    if area_flags["marketing"]:
        progress_parts.append(marketing_percent)
    if area_flags["development"]:
        progress_parts.append(development_percent)
    overall_percent = round(sum(progress_parts) / len(progress_parts)) if progress_parts else 0

    can_view_administration = bool(
        viewer and (getattr(viewer, "is_manager", False) or getattr(viewer, "role", "") == "administration")
    )
    logs_qs = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user")
    if not can_view_administration:
        logs_qs = logs_qs.exclude(module__in=["finance", "administration"]).exclude(
            module="operations",
            action__in=[
                "domain_status", "domain_hosting_delete", "domain_hosting_save",
                "credential_delete", "credential_save", "credential_purchase",
            ],
        )
    last_log = logs_qs.first()
    logs = logs_qs[:20]

    social_contracts = [
        item for item in contracted.get(PlanDepartment.DESIGN, [])
        if item.plan.service_type == ServiceType.SOCIAL_MEDIA
    ]
    subscription_contracts = [
        item
        for group in contracted.values()
        for item in group
        if item.plan.is_subscription_product
    ]

    domain_rows = list(project.domain_hosting_records.all())
    domain_pending = [row for row in domain_rows if not row.is_domain_complete]
    if domain_rows and not domain_pending:
        domain_status_label = "Dominios en orden" if len(domain_rows) > 1 else domain_rows[0].project_domain_label
        domain_status_code = "ready"
    elif domain_rows:
        domain_status_label = f"{len(domain_pending)} dominio(s) pendiente(s)"
        domain_status_code = "pending"
    else:
        domain_status_label = "Dominio pendiente"
        domain_status_code = "pending"
    visible_credentials = list(
        project.project_credentials.filter(enabled=True, visible_to_team=True).order_by("credential_type", "custom_name", "id")
    )
    visible_credential_count = len(visible_credentials)
    credential_count = project.project_credentials.filter(enabled=True).count()

    return {
        "questionnaire": questionnaire,
        "sheet": sheet,
        "brief": brief,
        "palette": palette,
        "workspace": workspace,
        "contracted": contracted,
        "social_contracts": social_contracts,
        "subscription_contracts": subscription_contracts,
        "domain_rows": domain_rows,
        "domain_status_label": domain_status_label,
        "domain_status_code": domain_status_code,
        "credential_count": credential_count,
        "visible_credential_count": visible_credential_count,
        "visible_credentials": visible_credentials,
        "admin_done": bool(admin_percent),
        "admin_percent": admin_percent,
        "design_steps": design_steps,
        "design_done": design_done,
        "design_percent": design_percent,
        "marketing_total": marketing_total,
        "marketing_done": marketing_done,
        "marketing_percent": marketing_percent,
        "technical_progress": technical_progress,
        "development_steps": development_steps,
        "development_done": development_done,
        "development_percent": development_percent,
        "production_total": production_total,
        "production_done": production_done,
        "production_percent": production_percent,
        "overall_percent": overall_percent,
        "area_flags": area_flags,
        "can_view_administration": can_view_administration,
        "last_log": last_log,
        "logs": logs,
    }


@login_required
def project_list(request):
    projects = visible_projects_for_user(request.user).prefetch_related("contracted_plans__plan", "contracted_plans__subscription", "domain_hosting_records", "project_credentials")
    status = request.GET.get("status", "")
    if status:
        projects = projects.filter(status=status)
    rows = []
    for project in projects:
        sync_project_area_records(project, request.user)
        rows.append({"project": project, "control": _control_data(project, viewer=request.user)})
    return render(request, "projects/list.html", {"project_rows": rows, "status_filter": status})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("client", "purchased_plan__plan")
        .prefetch_related(
            "assignments__user", "questionnaires__template", "color_palettes__colors",
            "resource_links", "image_references", "contracted_plans__plan", "contracted_plans__subscription",
            "domain_hosting_records", "project_credentials", "client_payments",
        ),
        pk=pk,
    )
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a tu área.")
    sync_project_area_records(project, request.user)
    note_form = ProjectNoteForm()
    control = _control_data(project, viewer=request.user)
    payment_summary = project_payment_summary(project)
    project_payments = project.client_payments.select_related("created_by").all()
    return render(request, "projects/detail.html", {
        "project": project,
        "note_form": note_form,
        "control": control,
        "payment_summary": payment_summary,
        "project_payments": project_payments,
    })


@role_required("administration")
def project_create(request):
    initial = {}
    client_id = request.GET.get("client")
    if client_id:
        initial["client"] = client_id
    form = ProjectForm(request.POST or None, initial=initial, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        form.save_plan_assignments(obj)
        form.save_responsible_assignments(obj)
        sync_project_area_records(obj, request.user)
        log_activity(request.user, "projects", "create", obj)
        messages.success(request, "Proyecto creado y productos contratados asignados por área.")
        return redirect("projects:detail", pk=obj.pk)
    return render(request, "projects/form.html", {
        "form": form,
        "title": "Nuevo proyecto",
        "subtitle": "Selecciona el cliente y todos los productos contratados, separados por área.",
    })


@role_required("administration")
def project_edit(request, pk):
    obj = get_object_or_404(Project.objects.prefetch_related("contracted_plans__plan"), pk=pk)
    form = ProjectForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        sync_project_area_records(obj, request.user)
        log_activity(request.user, "projects", "update", obj)
        messages.success(request, "Proyecto actualizado.")
        return redirect("projects:detail", pk=obj.pk)
    return render(request, "projects/form.html", {
        "form": form,
        "title": "Editar proyecto",
        "subtitle": obj.name,
        "project": obj,
    })


@manager_required
def assignment_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = ProjectAssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.project = project
        # Regla actual: un único responsable principal por área. Esta ruta se
        # conserva por compatibilidad, pero no puede crear duplicados del área.
        project.assignments.filter(area=obj.area).exclude(user=obj.user).delete()
        existing = project.assignments.filter(area=obj.area, user=obj.user).first()
        if existing:
            existing.status = obj.status
            existing.responsibility = obj.responsibility
            existing.save(update_fields=["status", "responsibility", "updated_at"])
            obj = existing
        else:
            obj.save()
        log_activity(request.user, "projects", "assign", obj)
        messages.success(request, "Responsable principal del área actualizado.")
        return redirect("projects:detail", pk=project.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Asignar responsable", "subtitle": project.name})


@login_required
def note_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method != "POST":
        return redirect("projects:detail", pk=pk)
    form = ProjectNoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.project = project
        note.author = request.user
        note.save()
        log_activity(request.user, "projects", "note", note)
        messages.success(request, "Nota añadida.")
    return redirect("projects:detail", pk=pk)
