from io import BytesIO
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
import qrcode
from apps.audit.models import ActivityLog
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.accounts.models import UserAccount
from apps.projects.models import Project
from apps.projects.selectors import can_access_project
from apps.reminders.models import ReminderCategory
from apps.reminders.services import ensure_reminder
from django.utils import timezone
from .forms import AdCampaignForm, ChecklistItemForm, MarketingBriefForm, MarketingDocumentForm, MarketingTaskForm, MarketingWorkspaceForm, SocialMediaDailyLogForm, SocialMediaPlanForm, SocialMediaTrackingForm
from .models import AdCampaign, MarketingBrief, MarketingChecklistItem, MarketingDocument, MarketingTask, MarketingWorkspace, SocialMediaDailyLog, SocialMediaPlan, SocialMediaTracking
from .services import ensure_workspace, save_campaign, save_social_plan


@role_required("marketing")
def marketing_list(request):
    projects = Project.objects.select_related("client", "purchased_plan__plan").filter(project_type__in=["social_media", "seo", "website"])
    if not request.user.is_manager:
        projects = projects.filter(assignments__user=request.user, assignments__area="marketing").distinct()
    tasks = MarketingTask.objects.select_related("project", "assigned_to").all()[:30]
    campaigns = AdCampaign.objects.select_related("project__client", "assigned_to")[:20]
    project_rows = []
    for project in projects:
        workspace = MarketingWorkspace.objects.filter(project=project).prefetch_related("checklist_items").first()
        total = workspace.checklist_items.count() if workspace else 0
        complete = workspace.checklist_items.filter(status="complete").count() if workspace else 0
        percent = round((complete / total) * 100) if total else 0
        last_log = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user").first()
        project_rows.append({
            "project": project,
            "workspace": workspace,
            "checks_total": total,
            "checks_complete": complete,
            "percent": percent,
            "last_log": last_log,
        })
    return render(request, "marketing/dashboard.html", {"project_rows": project_rows, "tasks": tasks, "campaigns": campaigns})


@role_required("marketing")
def workspace(request, project_pk):
    project = get_object_or_404(Project.objects.select_related("client"), pk=project_pk)
    if not can_access_project(request.user, project):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Este proyecto no está asignado a Marketing.")
    obj = ensure_workspace(project)
    form = MarketingWorkspaceForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        if saved.business_profile_status == "approved" and saved.review_link and not saved.review_message:
            saved.review_message = f"Hola, gracias por confiar en {project.client.business_name}. ¿Nos ayudas dejando una reseña sobre tu experiencia? {saved.review_link}"
        saved.shared_info_updated_by = request.user
        saved.shared_info_updated_at = timezone.now()
        saved.save()
        from apps.questionnaires.services import sync_marketing_shared_to_website
        sync_marketing_shared_to_website(saved, request.user)
        log_activity(request.user, "marketing", "workspace_update", saved)
        messages.success(request, "Información de Marketing guardada.")
        return redirect("marketing:workspace", project_pk=project.pk)
    groups = []
    for area, label in MarketingChecklistItem._meta.get_field("area").choices:
        groups.append((label, obj.checklist_items.filter(area=area)))
    return render(request, "marketing/workspace.html", {"project": project, "workspace": obj, "form": form, "groups": groups})


@role_required("marketing")
def checklist_edit(request, pk):
    item = get_object_or_404(MarketingChecklistItem.objects.select_related("workspace__project"), pk=pk)
    form = ChecklistItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        if item.key == "create_business_profile" and item.status == "complete":
            admin_user = UserAccount.objects.filter(role=UserAccount.Role.ADMINISTRATION, is_active=True).order_by("id").first() or UserAccount.objects.filter(role=UserAccount.Role.MANAGER, is_active=True).order_by("id").first()
            ensure_reminder(
                source_key=f"marketing-workspace:{item.workspace_id}:buy-credentials",
                title=f"Comprar credenciales · {item.workspace.project.client.business_name}",
                category=ReminderCategory.CREDENTIAL_PURCHASE,
                due_at=timezone.now(),
                client=item.workspace.project.client,
                project=item.workspace.project,
                assigned_to=admin_user,
                notes="Marketing marcó el perfil como creado. Registrar la compra en Credenciales y su renovación anual.",
                user=request.user,
            )
        log_activity(request.user, "marketing", "checklist_update", item, description=item.label)
        messages.success(request, "Check actualizado.")
        return redirect("marketing:workspace", project_pk=item.workspace.project_id)
    return render(request, "shared/form.html", {"form": form, "title": item.label, "subtitle": item.get_area_display()})


@role_required("marketing")
def document_add(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_project(request.user, project):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Este proyecto no está asignado a Marketing.")
    workspace = ensure_workspace(project)
    form = MarketingDocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.workspace = workspace; obj.uploaded_by = request.user; obj.save(); log_activity(request.user, "marketing", "document_add", obj, description=obj.title); messages.success(request, "Documento agregado."); return redirect("marketing:workspace", project_pk=project_pk)
    return render(request, "shared/form.html", {"form": form, "title": "Agregar documento de Marketing", "subtitle": "PDF local o link de Drive."})


@role_required("marketing")
def review_qr(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_project(request.user, project):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Este proyecto no está asignado a Marketing.")
    workspace = ensure_workspace(project)
    if not workspace.review_link:
        messages.error(request, "Primero registra el link de reviews."); return redirect("marketing:workspace", project_pk=project_pk)
    img = qrcode.make(workspace.review_link)
    buf = BytesIO(); img.save(buf, format="PNG")
    response = HttpResponse(buf.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="reviews-{workspace.project.client.client_code}.png"'
    return response


@role_required("marketing")
def campaign_list(request):
    records = AdCampaign.objects.select_related("project__client", "assigned_to")
    if not request.user.is_manager:
        records = records.filter(project__assignments__user=request.user, project__assignments__area="marketing").distinct()
    return render(request, "marketing/campaign_list.html", {"records": records})


@role_required("marketing")
def campaign_create(request):
    form = AdCampaignForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_campaign(form=form, user=request.user); messages.success(request, "Campaña guardada; se crearán recordatorios según su estado y fechas."); return redirect("marketing:campaign_list")
    return render(request, "shared/form.html", {"form": form, "title": "Nueva campaña", "subtitle": "Meta Ads, Google Ads o pauta tradicional."})


@role_required("marketing")
def campaign_edit(request, pk):
    obj = get_object_or_404(AdCampaign, pk=pk)
    if not can_access_project(request.user, obj.project):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Esta campaña no pertenece a un proyecto asignado a Marketing.")
    form = AdCampaignForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_campaign(form=form, user=request.user); messages.success(request, "Campaña actualizada."); return redirect("marketing:campaign_list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar campaña", "subtitle": obj.name})


@role_required("marketing", "administration")
def social_tracking_list(request):
    records = SocialMediaTracking.objects.select_related("client", "project")
    return render(request, "marketing/social_tracking.html", {"records": records})


@role_required("marketing")
def social_tracking_create(request):
    form = SocialMediaTrackingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(); log_activity(request.user, "marketing", "social_tracking_create", obj); messages.success(request, "Seguimiento creado."); return redirect("marketing:social_tracking")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo seguimiento Social Media / Google", "subtitle": "Estados simples: Completo/Incompleto y Sí/No."})


@role_required("marketing")
def social_tracking_edit(request, pk):
    obj = get_object_or_404(SocialMediaTracking, pk=pk); form = SocialMediaTrackingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save(); log_activity(request.user, "marketing", "social_tracking_update", obj); messages.success(request, "Seguimiento actualizado."); return redirect("marketing:social_tracking")
    return render(request, "shared/form.html", {"form": form, "title": "Editar seguimiento", "subtitle": obj.client.business_name})


@role_required("marketing")
def social_plan_list(request):
    records = SocialMediaPlan.objects.select_related("client", "project", "assigned_to")
    return render(request, "marketing/social_plans.html", {"records": records})


@role_required("marketing")
def social_plan_create(request):
    form = SocialMediaPlanForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_social_plan(form=form, user=request.user); messages.success(request, "Plan Social Media creado con recordatorio de informe mensual."); return redirect("marketing:social_plans")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo plan Social Media", "subtitle": "Seguimiento diario + revisión mensual."})


@role_required("marketing")
def social_plan_edit(request, pk):
    obj = get_object_or_404(SocialMediaPlan, pk=pk)
    if obj.project and not can_access_project(request.user, obj.project):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Este plan no pertenece a un proyecto asignado a Marketing.")
    form = SocialMediaPlanForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_social_plan(form=form, user=request.user)
        messages.success(request, "Plan Social Media actualizado.")
        return redirect("marketing:social_plans")
    return render(request, "shared/form.html", {"form": form, "title": "Editar plan Social Media", "subtitle": obj.client.business_name})


@role_required("marketing")
def social_daily_add(request, plan_pk):
    plan = get_object_or_404(SocialMediaPlan, pk=plan_pk); form = SocialMediaDailyLogForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.plan = plan; obj.save(); log_activity(request.user, "marketing", "social_daily_add", obj); messages.success(request, "Seguimiento diario guardado."); return redirect("marketing:social_plans")
    return render(request, "shared/form.html", {"form": form, "title": "Seguimiento diario", "subtitle": plan.client.business_name})


@role_required("marketing")
def brief_edit(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_project(request.user, project):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Este proyecto no está asignado a Marketing.")
    brief, _ = MarketingBrief.objects.get_or_create(project=project); form = MarketingBriefForm(request.POST or None, instance=brief)
    if request.method == "POST" and form.is_valid():
        form.save(); log_activity(request.user, "marketing", "brief_update", brief); messages.success(request, "Brief de marketing guardado."); return redirect("projects:detail", pk=project.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Brief de marketing", "subtitle": project.name})


@role_required("marketing")
def task_create(request):
    form = MarketingTaskForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(); log_activity(request.user, "marketing", "task_create", obj); messages.success(request, "Tarea creada."); return redirect("marketing:list")
    return render(request, "shared/form.html", {"form": form, "title": "Nueva tarea de marketing", "subtitle": "Tarea operativa independiente."})
