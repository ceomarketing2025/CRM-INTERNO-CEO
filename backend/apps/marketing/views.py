from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.projects.models import Project
from .forms import MarketingBriefForm, MarketingTaskForm
from .models import MarketingBrief, MarketingTask

@role_required("marketing")
def marketing_list(request):
    tasks = MarketingTask.objects.select_related("project", "assigned_to").all()
    projects = Project.objects.select_related("client").filter(project_type__in=["social_media", "seo", "website"])
    return render(request, "marketing/list.html", {"tasks": tasks, "projects": projects})

@role_required("marketing")
def brief_edit(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    brief, _ = MarketingBrief.objects.get_or_create(project=project)
    form = MarketingBriefForm(request.POST or None, instance=brief)
    if request.method == "POST" and form.is_valid():
        form.save(); log_activity(request.user, "marketing", "brief_update", brief); messages.success(request, "Brief de marketing guardado."); return redirect("projects:detail", pk=project.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Brief de marketing", "subtitle": project.name})

@role_required("marketing")
def task_create(request):
    form = MarketingTaskForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(); log_activity(request.user, "marketing", "task_create", obj); messages.success(request, "Tarea creada."); return redirect("marketing:list")
    return render(request, "shared/form.html", {"form": form, "title": "Nueva tarea de marketing", "subtitle": "Estructura inicial para el flujo operativo."})
