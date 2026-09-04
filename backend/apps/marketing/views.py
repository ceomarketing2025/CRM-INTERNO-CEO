from io import BytesIO
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
import qrcode

from apps.audit.models import ActivityLog
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.plans.models.choices import PlanDepartment
from apps.projects.models import Project
from apps.projects.selectors import can_access_project, projects_for_area
from apps.projects.services import sync_project_area_records

from .forms import (
    AdCampaignForm,
    AdvertisingAccountForm,
    CampaignManagerReviewForm,
    CampaignWeeklyReportForm,
    ChecklistItemForm,
    GoogleBusinessForm,
    GoogleLSAForm,
    MarketingBriefForm,
    MarketingDocumentForm,
    MarketingIntakeForm,
    MarketingTaskForm,
    SocialMediaDailyLogForm,
    SocialMediaPlanForm,
    SocialMediaTrackingForm,
    TraditionalAdvertisingForm,
)
from .models import (
    AdCampaign,
    AdvertisingAccount,
    CampaignWeeklyReport,
    MarketingBrief,
    MarketingChecklistItem,
    MarketingDocument,
    MarketingTask,
    MarketingWorkspace,
    SocialMediaDailyLog,
    SocialMediaPlan,
    SocialMediaTracking,
)
from .services import (
    ensure_workspace,
    review_campaign,
    save_advertising_account,
    save_campaign,
    save_google_business,
    save_intake,
    save_lsa,
    save_social_plan,
    sync_workspace_checks,
)


def _project_for_marketing(request, project_pk):
    project = get_object_or_404(
        Project.objects.select_related("client", "purchased_plan__plan")
        .prefetch_related("assignments__user", "contracted_plans__plan", "contracted_plans__subscription"),
        pk=project_pk,
    )
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no pertenece a la ficha de Marketing.")
    # Mantiene listas las fichas de Diseño / Marketing / Desarrollo del mismo proyecto.
    sync_project_area_records(project, request.user)
    return project


def _active_groups(workspace):
    groups = []
    for area, label in MarketingChecklistItem._meta.get_field("area").choices:
        items = workspace.checklist_items.filter(area=area, active=True)
        if items.exists():
            groups.append((area, label, items))
    return groups


@role_required("marketing")
def marketing_list(request):
    # Fuente única del CRM: plan contratado + tipo de servicio + flujo web + compatibilidad histórica.
    projects = projects_for_area("marketing").order_by("-updated_at", "-created_at")
    marketing_project_ids = projects.values_list("pk", flat=True)
    tasks = (
        MarketingTask.objects.select_related("project", "assigned_to")
        .filter(project_id__in=marketing_project_ids)
        .order_by("-updated_at")[:30]
    )
    campaigns = (
        AdCampaign.objects.select_related("project__client", "assigned_to", "manager_approved_by")
        .filter(project_id__in=marketing_project_ids)
        .order_by("-updated_at")[:20]
    )

    project_rows = []
    for project in projects:
        sync_project_area_records(project, request.user)
        workspace_obj = (
            MarketingWorkspace.objects.filter(project=project)
            .prefetch_related("checklist_items")
            .first()
        )
        if workspace_obj:
            active = workspace_obj.checklist_items.filter(active=True)
            total = active.count()
            complete = active.filter(status="complete").count()
        else:
            total = complete = 0
        percent = round((complete / total) * 100) if total else 0
        last_log = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user").first()
        area_plans = [
            item.plan for item in project.contracted_plans.all()
            if item.is_active and item.plan.department == PlanDepartment.MARKETING
        ]
        workflow_plans = [item.plan for item in project.contracted_plans.all() if item.is_active]
        project_rows.append({
            "project": project,
            "workspace": workspace_obj,
            "checks_total": total,
            "checks_complete": complete,
            "percent": percent,
            "last_log": last_log,
            "area_plans": area_plans,
            "workflow_plans": workflow_plans,
        })

    return render(request, "marketing/dashboard.html", {
        "project_rows": project_rows,
        "tasks": tasks,
        "campaigns": campaigns,
    })


@role_required("marketing")
def workspace(request, project_pk):
    """Pantalla 1: información completa de la reunión."""
    project = _project_for_marketing(request, project_pk)
    obj = ensure_workspace(project)
    form = MarketingIntakeForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = save_intake(form=form, user=request.user)
        # Se mantiene la sincronización ya existente con Desarrollo, sin tocar ese módulo.
        from apps.questionnaires.services import sync_marketing_shared_to_website
        sync_marketing_shared_to_website(saved, request.user)
        messages.success(request, "Información inicial de Marketing guardada.")
        return redirect("marketing:workspace", project_pk=project.pk)

    return render(request, "marketing/workspace.html", {
        "project": project,
        "workspace": obj,
        "form": form,
        "groups": _active_groups(obj),
    })


@role_required("marketing")
def google_business(request, project_pk):
    project = _project_for_marketing(request, project_pk)
    obj = ensure_workspace(project)
    if not obj.intake_ready:
        messages.warning(request, "Completa primero la información inicial de la reunión.")
        return redirect("marketing:workspace", project_pk=project.pk)
    form = GoogleBusinessForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = save_google_business(form=form, user=request.user)
        from apps.questionnaires.services import sync_marketing_shared_to_website
        sync_marketing_shared_to_website(saved, request.user)
        messages.success(request, "Google Business actualizado.")
        return redirect("marketing:google_business", project_pk=project.pk)
    sync_workspace_checks(obj)
    return render(request, "marketing/google_business.html", {
        "project": project,
        "workspace": obj,
        "form": form,
        "checks": obj.checklist_items.filter(area="google_profile", active=True),
    })


@role_required("marketing")
def google_lsa(request, project_pk):
    project = _project_for_marketing(request, project_pk)
    workspace_obj = ensure_workspace(project)
    if not workspace_obj.intake_ready:
        messages.warning(request, "Completa primero la información inicial de la reunión.")
        return redirect("marketing:workspace", project_pk=project.pk)
    lsa = workspace_obj.lsa_workspace
    form = GoogleLSAForm(request.POST or None, instance=lsa, workspace=workspace_obj)
    if request.method == "POST" and form.is_valid():
        save_lsa(form=form, user=request.user)
        messages.success(request, "Google LSA actualizado y recordatorios sincronizados.")
        return redirect("marketing:google_lsa", project_pk=project.pk)
    return render(request, "marketing/google_lsa.html", {
        "project": project,
        "workspace": workspace_obj,
        "lsa": lsa,
        "form": form,
        "checks": workspace_obj.checklist_items.filter(area="google_lsa", active=True),
    })


@role_required("marketing")
def digital_ads(request, project_pk):
    project = _project_for_marketing(request, project_pk)
    workspace_obj = ensure_workspace(project)
    if not workspace_obj.intake_ready:
        messages.warning(request, "Completa primero la información inicial de la reunión.")
        return redirect("marketing:workspace", project_pk=project.pk)

    accounts = {a.platform: a for a in workspace_obj.advertising_accounts.all()}
    platform = request.POST.get("_platform") if request.method == "POST" else None
    valid_platforms = {"meta", "google", "tiktok", "traditional"}

    forms = {
        "traditional": TraditionalAdvertisingForm(
            request.POST if request.method == "POST" and platform == "traditional" else None,
            instance=accounts["traditional"], prefix="traditional",
        )
    }
    for key in ["meta", "google", "tiktok"]:
        forms[key] = AdvertisingAccountForm(
            request.POST if request.method == "POST" and platform == key else None,
            instance=accounts[key], prefix=key, platform=key,
        )

    if request.method == "POST":
        if platform not in valid_platforms:
            messages.error(request, "Plataforma no válida.")
        elif platform != "traditional" and accounts["traditional"].enabled != "yes":
            messages.error(request, "Primero activa Publicidad tradicional para habilitar Meta Ads, Google Ads y TikTok Ads.")
        elif forms[platform].is_valid():
            save_advertising_account(form=forms[platform], account=accounts[platform], user=request.user)
            if platform == "traditional":
                messages.success(request, "Publicidad tradicional actualizada. Las plataformas se habilitan únicamente cuando seleccionas Sí.")
            else:
                messages.success(request, f"Configuración de {accounts[platform].get_platform_display()} guardada.")
            return redirect("marketing:digital_ads", project_pk=project.pk)

    campaigns = AdCampaign.objects.filter(project=project).select_related("assigned_to", "manager_approved_by")
    campaign_map = {key: campaigns.filter(platform=key) for key in ["meta", "google", "tiktok"]}
    return render(request, "marketing/digital_ads.html", {
        "project": project,
        "workspace": workspace_obj,
        "accounts": accounts,
        "forms": forms,
        "campaign_map": campaign_map,
        "traditional_enabled": accounts["traditional"].enabled == "yes",
    })


@role_required("marketing")
def checklist_edit(request, pk):
    item = get_object_or_404(MarketingChecklistItem.objects.select_related("workspace__project"), pk=pk, active=True)
    if not can_access_project(request.user, item.workspace.project):
        raise PermissionDenied("Este proyecto no está asignado a Marketing.")
    form = ChecklistItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        log_activity(request.user, "marketing", "checklist_update", item, description=item.label)
        messages.success(request, "Check actualizado.")
        return redirect("marketing:workspace", project_pk=item.workspace.project_id)
    return render(request, "shared/form.html", {"form": form, "title": item.label, "subtitle": item.get_area_display()})


@role_required("marketing")
def document_add(request, project_pk):
    project = _project_for_marketing(request, project_pk)
    workspace_obj = ensure_workspace(project)
    form = MarketingDocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.workspace = workspace_obj
        obj.uploaded_by = request.user
        obj.save()
        sync_workspace_checks(workspace_obj)
        log_activity(request.user, "marketing", "document_add", obj, description=obj.title)
        messages.success(request, "Documento agregado.")
        return redirect("marketing:workspace", project_pk=project_pk)
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Agregar documento de la reunión / Marketing",
        "subtitle": "Sube PDF o registra un link de Drive. Las credenciales no se manejan en este módulo.",
    })


@role_required("marketing")
def review_qr(request, project_pk):
    project = _project_for_marketing(request, project_pk)
    workspace_obj = ensure_workspace(project)
    if workspace_obj.business_profile_status != "approved":
        messages.error(request, "El QR de reviews se habilita cuando Google Business está aprobado.")
        return redirect("marketing:google_business", project_pk=project_pk)
    if not workspace_obj.review_link:
        messages.error(request, "Primero registra el link de reviews.")
        return redirect("marketing:google_business", project_pk=project_pk)
    img = qrcode.make(workspace_obj.review_link)
    buf = BytesIO()
    img.save(buf, format="PNG")
    response = HttpResponse(buf.getvalue(), content_type="image/png")
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="reviews-{workspace_obj.project.client.client_code}.png"'
    return response


@role_required("marketing", "administration")
def campaign_list(request):
    marketing_project_ids = projects_for_area("marketing").values_list("pk", flat=True)
    records = (
        AdCampaign.objects.select_related("project__client", "assigned_to", "manager_approved_by")
        .filter(project_id__in=marketing_project_ids)
        .distinct()
    )
    return render(request, "marketing/campaign_list.html", {"records": records})


@role_required("marketing")
def campaign_create(request):
    project = None
    platform = request.GET.get("platform") or request.POST.get("platform")
    project_pk = request.GET.get("project") or request.POST.get("project")
    if project_pk:
        project = _project_for_marketing(request, project_pk)

    if project and platform:
        workspace_obj = ensure_workspace(project)
        controller = workspace_obj.advertising_accounts.filter(platform="traditional").first()
        account = workspace_obj.advertising_accounts.filter(platform=platform).first()
        if platform not in {"meta", "google", "tiktok"}:
            messages.error(request, "Selecciona Meta Ads, Google Ads o TikTok Ads para crear la campaña.")
            return redirect("marketing:digital_ads", project_pk=project.pk)
        if not controller or controller.enabled != "yes":
            messages.error(request, "Publicidad tradicional debe estar activada antes de crear campañas.")
            return redirect("marketing:digital_ads", project_pk=project.pk)
        if not account or account.enabled != "yes":
            messages.error(request, f"Primero habilita {account.get_platform_display() if account else platform}.")
            return redirect("marketing:digital_ads", project_pk=project.pk)
        if account.campaigns_enabled != "yes":
            messages.error(request, "La opción de campañas publicitarias debe estar en Sí para esta plataforma.")
            return redirect("marketing:digital_ads", project_pk=project.pk)

    form = AdCampaignForm(request.POST or None, user=request.user, project=project, platform=platform)
    if request.method == "POST" and form.is_valid():
        obj, invalidated = save_campaign(form=form, user=request.user)
        messages.success(request, "Campaña guardada. Para lanzar, envíala a validación del administrador/Gerencia.")
        return redirect("marketing:digital_ads", project_pk=obj.project_id)
    return render(request, "marketing/campaign_form.html", {
        "form": form,
        "title": "Nueva campaña",
        "project": project,
        "platform": platform,
    })


@role_required("marketing")
def campaign_edit(request, pk):
    obj = get_object_or_404(AdCampaign.objects.select_related("project__client", "manager_approved_by"), pk=pk)
    if not can_access_project(request.user, obj.project):
        raise PermissionDenied("Esta campaña no pertenece a un proyecto asignado a Marketing.")
    form = AdCampaignForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj, invalidated = save_campaign(form=form, user=request.user)
        if invalidated:
            messages.warning(request, "Cambiaste datos críticos: la aprobación anterior se anuló y la campaña volvió a validación.")
        else:
            messages.success(request, "Campaña actualizada.")
        return redirect("marketing:digital_ads", project_pk=obj.project_id)
    return render(request, "marketing/campaign_form.html", {
        "form": form,
        "title": "Editar campaña",
        "project": obj.project,
        "campaign": obj,
        "weekly_reports": obj.weekly_reports.all()[:12],
    })


@role_required("manager", "administration")
def campaign_manager_review(request, pk):
    campaign = get_object_or_404(AdCampaign.objects.select_related("project__client"), pk=pk)
    form = CampaignManagerReviewForm(request.POST or None, instance=campaign)
    if request.method == "POST" and form.is_valid():
        review_campaign(
            campaign=campaign,
            decision=form.cleaned_data["decision"],
            notes=form.cleaned_data.get("manager_review_notes", ""),
            user=request.user,
        )
        messages.success(request, "Validación de Gerencia registrada y Marketing notificado.")
        return redirect("marketing:campaign_list")
    return render(request, "marketing/campaign_review.html", {"campaign": campaign, "form": form})


@role_required("marketing")
def campaign_weekly_report(request, pk):
    campaign = get_object_or_404(AdCampaign, pk=pk)
    if not can_access_project(request.user, campaign.project):
        raise PermissionDenied("Esta campaña no pertenece a un proyecto asignado a Marketing.")
    form = CampaignWeeklyReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review_date = form.cleaned_data["review_date"]
        if CampaignWeeklyReport.objects.filter(campaign=campaign, review_date=review_date).exists():
            form.add_error("review_date", "Ya existe un seguimiento para esta campaña en esa fecha.")
        else:
            report = form.save(commit=False)
            report.campaign = campaign
            report.reviewed_by = request.user
            report.save()
            log_activity(request.user, "marketing", "campaign_weekly_report", report, campaign.name)
            messages.success(request, "Seguimiento semanal registrado.")
            return redirect("marketing:campaign_edit", pk=campaign.pk)
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Seguimiento semanal de campaña",
        "subtitle": f"{campaign.get_platform_display()} · {campaign.name}",
    })


@role_required("marketing", "administration")
def social_tracking_list(request):
    records = SocialMediaTracking.objects.select_related("client", "project")
    return render(request, "marketing/social_tracking.html", {"records": records})


@role_required("marketing")
def social_tracking_create(request):
    form = SocialMediaTrackingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_activity(request.user, "marketing", "social_tracking_create", obj)
        messages.success(request, "Seguimiento creado.")
        return redirect("marketing:social_tracking")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo seguimiento Social Media / Google", "subtitle": "Estados simples: Completo/Incompleto y Sí/No."})


@role_required("marketing")
def social_tracking_edit(request, pk):
    obj = get_object_or_404(SocialMediaTracking, pk=pk)
    form = SocialMediaTrackingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_activity(request.user, "marketing", "social_tracking_update", obj)
        messages.success(request, "Seguimiento actualizado.")
        return redirect("marketing:social_tracking")
    return render(request, "shared/form.html", {"form": form, "title": "Editar seguimiento", "subtitle": obj.client.business_name})


@role_required("marketing")
def social_plan_list(request):
    records = SocialMediaPlan.objects.select_related("client", "project", "assigned_to")
    return render(request, "marketing/social_plans.html", {"records": records})


@role_required("marketing")
def social_plan_create(request):
    form = SocialMediaPlanForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_social_plan(form=form, user=request.user)
        messages.success(request, "Plan Social Media creado con recordatorio de informe mensual.")
        return redirect("marketing:social_plans")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo plan Social Media", "subtitle": "Seguimiento diario + revisión mensual."})


@role_required("marketing")
def social_plan_edit(request, pk):
    obj = get_object_or_404(SocialMediaPlan, pk=pk)
    if obj.project and not can_access_project(request.user, obj.project):
        raise PermissionDenied("Este plan no pertenece a un proyecto asignado a Marketing.")
    form = SocialMediaPlanForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_social_plan(form=form, user=request.user)
        messages.success(request, "Plan Social Media actualizado.")
        return redirect("marketing:social_plans")
    return render(request, "shared/form.html", {"form": form, "title": "Editar plan Social Media", "subtitle": obj.client.business_name})


@role_required("marketing")
def social_daily_add(request, plan_pk):
    plan = get_object_or_404(SocialMediaPlan, pk=plan_pk)
    form = SocialMediaDailyLogForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.plan = plan
        obj.save()
        log_activity(request.user, "marketing", "social_daily_add", obj)
        messages.success(request, "Seguimiento diario guardado.")
        return redirect("marketing:social_plans")
    return render(request, "shared/form.html", {"form": form, "title": "Seguimiento diario", "subtitle": plan.client.business_name})


@role_required("marketing")
def brief_edit(request, project_pk):
    project = _project_for_marketing(request, project_pk)
    brief, _ = MarketingBrief.objects.get_or_create(project=project)
    form = MarketingBriefForm(request.POST or None, instance=brief)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "marketing", "brief_update", brief)
        messages.success(request, "Brief de marketing guardado.")
        return redirect("projects:detail", pk=project.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Brief de marketing", "subtitle": project.name})


@role_required("marketing")
def task_create(request):
    form = MarketingTaskForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_activity(request.user, "marketing", "task_create", obj)
        messages.success(request, "Tarea creada.")
        return redirect("marketing:list")
    return render(request, "shared/form.html", {"form": form, "title": "Nueva tarea de marketing", "subtitle": "Tarea operativa independiente."})
