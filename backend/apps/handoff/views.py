from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import PermissionDenied
from apps.projects.models import Project
from apps.projects.selectors import can_access_project
from apps.projects.services import sync_project_area_records
from .services import build_project_summary


@login_required
def summary(request, project_pk):
    project = get_object_or_404(
        Project.objects.select_related("client", "purchased_plan__plan")
        .prefetch_related(
            "color_palettes__colors", "color_palettes__gradients",
            "questionnaires__template__sections__questions", "questionnaires__answers",
            "resource_links", "image_references", "production_records__collaborator",
            "web_production_sheet__pages__responsible", "web_production_sheet__counties__responsible", "web_production_sheet__counties__services__responsible",
            "credential_purchases", "project_credentials", "domain_hosting_records", "ad_campaigns__assigned_to", "social_media_plans__assigned_to",
            "reminders__assigned_to", "contracted_plans__plan", "contracted_plans__subscription",
        ), pk=project_pk,
    )
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a tu área.")
    sync_project_area_records(project, request.user)
    context = build_project_summary(project, viewer=request.user)
    context["project"] = project
    return render(request, "handoff/summary.html", context)
