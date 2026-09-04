from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import PermissionDenied
from apps.audit.models import ActivityLog
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.projects.models import Project
from apps.projects.selectors import can_access_project
from apps.resources.models import ProjectResourceLink
from .forms import DesignBriefForm, PaletteForm, PaletteQuickForm
from .models import ColorPalette, DesignBrief, PaletteColor
from .services import build_palette_pdf, complete_design_brief


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
    projects = Project.objects.select_related("client", "purchased_plan__plan").filter(project_type__in=["website", "branding", "software"]).prefetch_related(
        "color_palettes__colors", "resource_links", "image_references", "assignments__user"
    )
    if not request.user.is_manager:
        projects = projects.filter(assignments__user=request.user, assignments__area="design").distinct()

    project_rows = []
    for project in projects:
        try:
            brief = project.design_brief
        except DesignBrief.DoesNotExist:
            brief = None
        palette = next((p for p in project.color_palettes.all() if p.is_primary), None)
        roles = {c.role for c in palette.colors.all()} if palette else set()
        resource_kinds = {r.kind for r in project.resource_links.all() if r.area == ProjectResourceLink.Area.DESIGN}
        resources_ready = ProjectResourceLink.Kind.LOGO in resource_kinds and ProjectResourceLink.Kind.PALETTE_DRIVE in resource_kinds
        last_log = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user").first()
        project_rows.append({
            "project": project,
            "brief_done": bool(brief and brief.completed),
            "palette_done": all(role in roles for role in PALETTE_DEFAULTS),
            "resources_ready": resources_ready,
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
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Diseño.")
    form = PaletteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        palette = form.save(commit=False)
        palette.project = project
        if palette.is_primary:
            ColorPalette.objects.filter(project=project, is_primary=True).update(is_primary=False)
        palette.save()
        log_activity(request.user, "design", "palette_create", palette)
        messages.success(request, "Paleta creada.")
        return redirect("design:palette_detail", pk=palette.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Nueva paleta", "subtitle": project.name})


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
