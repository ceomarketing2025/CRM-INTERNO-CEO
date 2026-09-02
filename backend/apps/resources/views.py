from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.projects.models import Project
from .forms import ImageReferenceForm, ProjectResourceLinkForm


@role_required("design", "developer", "marketing", "administration")
def project_resources(request, project_pk):
    project = get_object_or_404(Project.objects.select_related("client").prefetch_related("resource_links", "image_references"), pk=project_pk)
    link_form = ProjectResourceLinkForm(prefix="link")
    image_form = ImageReferenceForm(prefix="image")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_image":
            image_form = ImageReferenceForm(request.POST, prefix="image")
            if image_form.is_valid():
                obj = image_form.save(commit=False)
                obj.project = project
                obj.created_by = request.user
                obj.save()
                log_activity(request.user, "resources", "image_reference_add", obj)
                messages.success(request, "Referencia de imagen añadida.")
                return redirect("resources:project", project_pk=project.pk)
        else:
            link_form = ProjectResourceLinkForm(request.POST, prefix="link")
            if link_form.is_valid():
                obj = link_form.save(commit=False)
                obj.project = project
                obj.created_by = request.user
                obj.save()
                log_activity(request.user, "resources", "link_add", obj)
                messages.success(request, "Link de respaldo añadido.")
                return redirect("resources:project", project_pk=project.pk)
    return render(request, "resources/project.html", {"project": project, "link_form": link_form, "image_form": image_form})
