from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from apps.projects.models import Project
from .services import build_project_summary


@login_required
def summary(request, project_pk):
    project = get_object_or_404(
        Project.objects.select_related("client", "purchased_plan__plan")
        .prefetch_related(
            "color_palettes__colors", "color_palettes__gradients",
            "questionnaires__template__sections__questions", "questionnaires__answers",
            "resource_links", "image_references",
        ),
        pk=project_pk,
    )
    context = build_project_summary(project)
    context["project"] = project
    return render(request, "handoff/summary.html", context)
