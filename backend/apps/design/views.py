from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.projects.models import Project
from .forms import DesignBriefForm, PaletteColorForm, PaletteForm, PaletteGradientForm
from .models import ColorPalette, DesignBrief
from .services import build_palette_pdf, complete_design_brief


@role_required("design")
def design_list(request):
    projects = Project.objects.select_related("client", "purchased_plan__plan").filter(project_type__in=["website", "branding", "software"]).prefetch_related("color_palettes__colors")
    if not request.user.is_manager:
        projects = projects.filter(status__in=["design_intake", "development_intake", "information_ready", "in_development", "review"])
    return render(request, "design/list.html", {"projects": projects})


@role_required("design")
def brief_edit(request, project_pk):
    project = get_object_or_404(Project.objects.select_related("client", "purchased_plan__plan"), pk=project_pk)
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
            messages.success(request, "Asesoría visual completada. El proyecto pasó a Desarrollo.")
            return redirect("projects:detail", pk=project.pk)
        log_activity(request.user, "design", "brief_update", brief)
        messages.success(request, "Asesoría visual guardada.")
        return redirect("design:brief_edit", project_pk=project.pk)
    return render(request, "design/brief.html", {"form": form, "project": project, "brief": brief, "palette": palette})


@role_required("design")
def palette_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    form = PaletteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        palette = form.save(commit=False)
        palette.project = project
        if palette.is_primary:
            ColorPalette.objects.filter(project=project, is_primary=True).update(is_primary=False)
        palette.save()
        log_activity(request.user, "design", "palette_create", palette)
        messages.success(request, "Paleta creada. Ahora añade colores y degradados.")
        return redirect("design:palette_detail", pk=palette.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Nueva paleta", "subtitle": project.name})


@role_required("design")
def palette_detail(request, pk):
    palette = get_object_or_404(ColorPalette.objects.select_related("project__client").prefetch_related("colors", "gradients"), pk=pk)
    color_form = PaletteColorForm(prefix="color")
    gradient_form = PaletteGradientForm(prefix="gradient")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_gradient":
            gradient_form = PaletteGradientForm(request.POST, prefix="gradient")
            if gradient_form.is_valid():
                obj = gradient_form.save(commit=False)
                obj.palette = palette
                obj.save()
                log_activity(request.user, "design", "gradient_add", obj)
                messages.success(request, "Degradado añadido.")
                return redirect("design:palette_detail", pk=pk)
        else:
            color_form = PaletteColorForm(request.POST, prefix="color")
            if color_form.is_valid():
                color = color_form.save(commit=False)
                color.palette = palette
                color.save()
                log_activity(request.user, "design", "color_add", color)
                messages.success(request, "Color añadido.")
                return redirect("design:palette_detail", pk=pk)
    return render(request, "design/palette_detail.html", {"palette": palette, "color_form": color_form, "gradient_form": gradient_form})


@role_required("design")
def palette_pdf(request, pk):
    palette = get_object_or_404(ColorPalette.objects.select_related("project__client", "project__design_brief").prefetch_related("colors", "gradients"), pk=pk)
    pdf_bytes = build_palette_pdf(palette.project, palette)
    filename = f"asesoria-visual-{palette.project.client.business_name}".lower().replace(" ", "-") + ".pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response
