from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import PermissionDenied
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.projects.models import Project
from apps.projects.selectors import can_access_project
from .forms import DesignCoreLinksForm, DesignPhotoLinkForm
from .models import ImageReference, ProjectResourceLink


CORE_LINKS = {
    "information_url": (ProjectResourceLink.Kind.INFORMATION, "Información"),
    "logo_url": (ProjectResourceLink.Kind.LOGO, "Logo"),
    "palette_url": (ProjectResourceLink.Kind.PALETTE_DRIVE, "Paleta de colores"),
}


def _link_value(project, kind):
    item = project.resource_links.filter(area=ProjectResourceLink.Area.DESIGN, kind=kind).order_by("id").first()
    return item.url if item else ""


def _save_core_link(project, user, kind, label, url):
    qs = project.resource_links.filter(area=ProjectResourceLink.Area.DESIGN, kind=kind).order_by("id")
    item = qs.first()
    if not url:
        if item:
            item.delete()
        qs.exclude(pk=getattr(item, "pk", None)).delete()
        return
    if item:
        item.label = label
        item.url = url
        item.created_by = item.created_by or user
        item.save(update_fields=["label", "url", "created_by", "updated_at"])
        qs.exclude(pk=item.pk).delete()
    else:
        ProjectResourceLink.objects.create(
            project=project,
            area=ProjectResourceLink.Area.DESIGN,
            kind=kind,
            label=label,
            url=url,
            created_by=user,
        )


@role_required("design")
def project_resources(request, project_pk):
    project = get_object_or_404(
        Project.objects.select_related("client").prefetch_related("resource_links", "image_references"),
        pk=project_pk,
    )
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")

    initial = {field: _link_value(project, kind) for field, (kind, _) in CORE_LINKS.items()}
    core_form = DesignCoreLinksForm(initial=initial)
    client_form = DesignPhotoLinkForm(prefix="client")
    stock_form = DesignPhotoLinkForm(prefix="stock")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_core":
            core_form = DesignCoreLinksForm(request.POST)
            if core_form.is_valid():
                for field, (kind, label) in CORE_LINKS.items():
                    _save_core_link(project, request.user, kind, label, core_form.cleaned_data.get(field, ""))
                log_activity(request.user, "design", "resource_links_update", project)
                messages.success(request, "Links principales de Diseño guardados.")
                return redirect("resources:project", project_pk=project.pk)

        elif action in {"add_client_photo", "add_stock_photo"}:
            prefix = "client" if action == "add_client_photo" else "stock"
            form = DesignPhotoLinkForm(request.POST, prefix=prefix)
            if form.is_valid():
                obj = ImageReference.objects.create(
                    project=project,
                    category=form.cleaned_data["service_name"],
                    image_url=form.cleaned_data["url"],
                    source="client" if prefix == "client" else "stock",
                    created_by=request.user,
                )
                log_activity(request.user, "design", "image_reference_add", obj, description=obj.category)
                messages.success(request, "Link de fotos añadido.")
                return redirect("resources:project", project_pk=project.pk)
            if prefix == "client":
                client_form = form
            else:
                stock_form = form

        elif action == "delete_photo":
            obj = get_object_or_404(ImageReference, pk=request.POST.get("photo_id"), project=project)
            label = obj.category
            obj.delete()
            log_activity(request.user, "design", "image_reference_delete", project, description=label)
            messages.success(request, "Link de fotos eliminado.")
            return redirect("resources:project", project_pk=project.pk)

    client_photos = project.image_references.filter(source="client").order_by("order", "id")
    stock_photos = project.image_references.filter(source="stock").order_by("order", "id")
    other_photos = project.image_references.exclude(source__in=["client", "stock"]).order_by("order", "id")

    return render(request, "resources/project.html", {
        "project": project,
        "core_form": core_form,
        "client_form": client_form,
        "stock_form": stock_form,
        "client_photos": client_photos,
        "stock_photos": stock_photos,
        "other_photos": other_photos,
    })
