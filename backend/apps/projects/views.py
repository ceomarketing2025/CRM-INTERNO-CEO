from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from apps.audit.services import log_activity
from apps.core.decorators import manager_required, role_required
from .forms import ProjectAssignmentForm, ProjectForm, ProjectNoteForm
from .models import Project


@login_required
def project_list(request):
    projects = Project.objects.select_related("client", "purchased_plan__plan").prefetch_related("assignments__user")
    status = request.GET.get("status", "")
    if status:
        projects = projects.filter(status=status)
    if not request.user.is_manager and request.user.role in {"design", "developer", "marketing"}:
        # En V2 se muestran los proyectos pertinentes al área aunque aún no exista una asignación explícita.
        stage_map = {
            "design": ["design_intake", "development_intake", "information_ready", "in_development", "review"],
            "developer": ["development_intake", "information_ready", "in_development", "review"],
            "marketing": ["information_ready", "in_development", "review", "delivered"],
        }
        projects = projects.filter(status__in=stage_map.get(request.user.role, []))
    return render(request, "projects/list.html", {"projects": projects, "status_filter": status})


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
    note_form = ProjectNoteForm()
    return render(request, "projects/detail.html", {"project": project, "note_form": note_form})


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
