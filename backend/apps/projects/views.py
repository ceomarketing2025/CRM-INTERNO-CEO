from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import PermissionDenied
from apps.audit.models import ActivityLog
from apps.audit.services import log_activity
from apps.core.decorators import manager_required, role_required
from apps.design.models import DesignBrief
from apps.marketing.models import MarketingWorkspace
from apps.operations.models import WebProductionSheet
from apps.questionnaires.models import ProjectQuestionnaire
from apps.questionnaires.services import WEBSITE_TEMPLATE_CODE, website_questionnaire_progress
from apps.resources.models import ProjectResourceLink
from .forms import ProjectAssignmentForm, ProjectForm, ProjectNoteForm
from .models import Project
from .selectors import can_access_project, visible_projects_for_user


REQUIRED_PALETTE_ROLES = {"text", "background", "primary", "secondary", "accent"}


def _control_data(project):
    questionnaire = ProjectQuestionnaire.objects.filter(project=project).select_related("template").prefetch_related("answers__question").order_by("id").first()
    sheet = WebProductionSheet.objects.filter(project=project).prefetch_related("pages", "counties__services", "cities").first()
    brief = DesignBrief.objects.filter(project=project).first()
    palette = project.color_palettes.filter(is_primary=True).prefetch_related("colors").first()
    palette_roles = {c.role for c in palette.colors.all()} if palette else set()
    resource_kinds = set(ProjectResourceLink.objects.filter(project=project, area=ProjectResourceLink.Area.DESIGN).values_list("kind", flat=True))
    workspace = MarketingWorkspace.objects.filter(project=project).prefetch_related("checklist_items").first()

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

    admin_percent = 100 if project.purchased_plan_id else 0
    overall_percent = round((admin_percent + design_percent + marketing_percent + development_percent) / 4)

    last_log = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user").first()
    logs = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user")[:20]

    return {
        "questionnaire": questionnaire,
        "sheet": sheet,
        "brief": brief,
        "palette": palette,
        "workspace": workspace,
        "admin_done": bool(project.purchased_plan_id),
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
        "last_log": last_log,
        "logs": logs,
    }


@login_required
def project_list(request):
    projects = visible_projects_for_user(request.user)
    status = request.GET.get("status", "")
    if status:
        projects = projects.filter(status=status)
    rows = [{"project": p, "control": _control_data(p)} for p in projects]
    return render(request, "projects/list.html", {"project_rows": rows, "status_filter": status})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("client", "purchased_plan__plan")
        .prefetch_related(
            "assignments__user", "questionnaires__template", "color_palettes__colors",
            "resource_links", "image_references"
        ),
        pk=pk,
    )
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a tu área.")
    note_form = ProjectNoteForm()
    control = _control_data(project)
    return render(request, "projects/detail.html", {"project": project, "note_form": note_form, "control": control})


@role_required("administration")
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        log_activity(request.user, "projects", "create", obj)
        messages.success(request, "Proyecto creado.")
        return redirect("projects:detail", pk=obj.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo proyecto", "subtitle": "Gerencia o Administración pueden crear proyectos manuales."})


@role_required("administration")
def project_edit(request, pk):
    obj = get_object_or_404(Project, pk=pk)
    form = ProjectForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "projects", "update", obj)
        messages.success(request, "Proyecto actualizado.")
        return redirect("projects:detail", pk=obj.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Editar proyecto", "subtitle": obj.name})


@manager_required
def assignment_create(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = ProjectAssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.project = project
        obj.save()
        log_activity(request.user, "projects", "assign", obj)
        messages.success(request, "Responsable asignado.")
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
