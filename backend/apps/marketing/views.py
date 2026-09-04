from io import BytesIO
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
import qrcode

from apps.audit.models import ActivityLog, GeneralAuditCheck
from apps.audit.services import build_general_audit_rows, log_activity, review_general_audit_check
from apps.core.decorators import role_required
from apps.projects.models import Project
from apps.projects.selectors import can_access_project, projects_for_area

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
    SocialMediaAudit,
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
    project = get_object_or_404(Project.objects.select_related("client"), pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Marketing.")
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
    projects = projects_for_area("marketing").order_by("-updated_at", "-created_at")
    if not request.user.is_manager:
        projects = projects.filter(assignments__user=request.user, assignments__area="marketing").distinct()
    tasks_qs = MarketingTask.objects.select_related("project", "assigned_to")
    campaigns_qs = AdCampaign.objects.select_related("project__client", "assigned_to")
    if not request.user.is_manager:
        tasks_qs = tasks_qs.filter(project__assignments__user=request.user, project__assignments__area="marketing").distinct()
        campaigns_qs = campaigns_qs.filter(project__assignments__user=request.user, project__assignments__area="marketing").distinct()
    tasks = tasks_qs[:30]
    campaigns = campaigns_qs[:20]
    project_rows = []
    for project in projects:
        workspace = MarketingWorkspace.objects.filter(project=project).prefetch_related("checklist_items").first()
        if workspace:
            active = workspace.checklist_items.filter(active=True)
            total = active.count()
            complete = active.filter(status="complete").count()
        else:
            total = complete = 0
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
    """Pantalla 1: información completa de la reunión."""
    project = _project_for_marketing(request, project_pk)
    obj = ensure_workspace(project)
    form = MarketingIntakeForm(request.POST or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            saved = save_intake(form=form, user=request.user)
            # Se mantiene la sincronización ya existente con Desarrollo, sin tocar ese módulo.
            from apps.questionnaires.services import sync_marketing_shared_to_website
            sync_marketing_shared_to_website(saved, request.user)
            if saved.intake_ready:
                messages.success(
                    request,
                    "Información inicial completada. Ya puedes ingresar a Google Business, Google LSA y Publicidad Digital.",
                )
            else:
                messages.success(request, "Información inicial de Marketing guardada.")
            return redirect("marketing:workspace", project_pk=project.pk)

        messages.error(
            request,
            "No se pudo marcar la información inicial como completa. Revisa los campos señalados en rojo.",
        )

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
    return render(request, "marketing/form.html", {"form": form, "title": item.label, "subtitle": item.get_area_display()})


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
    return render(request, "marketing/form.html", {
        "form": form,
        "title": "Agregar documento de la reunión / Marketing",
        "subtitle": "Sube PDF o registra un link de Drive. Las credenciales no se manejan en este módulo.",
    })


@role_required("marketing")
def review_qr(request, project_pk):
    project = _project_for_marketing(request, project_pk)
    workspace_obj = ensure_workspace(project)
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
    records = AdCampaign.objects.select_related("project__client", "assigned_to", "manager_approved_by")
    if not request.user.is_manager and request.user.role != "administration":
        records = records.filter(project__assignments__user=request.user, project__assignments__area="marketing").distinct()
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
        report = form.save(commit=False)
        report.campaign = campaign
        report.reviewed_by = request.user
        report.save()
        log_activity(request.user, "marketing", "campaign_weekly_report", report, campaign.name)
        messages.success(request, "Seguimiento semanal registrado.")
        return redirect("marketing:campaign_edit", pk=campaign.pk)
    return render(request, "marketing/form.html", {
        "form": form,
        "title": "Seguimiento semanal de campaña",
        "subtitle": f"{campaign.get_platform_display()} · {campaign.name}",
    })


@role_required("administration")
def social_tracking_list(request):
    """Auditoría General por proyecto. Solo Gerencia/Administración."""
    from collections import OrderedDict
    from apps.projects.models import Project
    from apps.projects.selectors import project_area_flags
    from apps.projects.services import sync_project_area_records

    # La auditoría también repara proyectos antiguos: si fueron creados antes de
    # la sincronización por servicios, prepara sus fichas/tareas de área de forma
    # idempotente antes de calcular el dashboard.
    for project in Project.objects.exclude(status="cancelled").select_related("client").prefetch_related("contracted_plans__plan"):
        sync_project_area_records(project, request.user)

    all_rows = build_general_audit_rows()
    q = (request.GET.get("q") or "").strip().lower()
    selected_area = (request.GET.get("area") or "all").strip().lower()
    status = (request.GET.get("status") or "all").strip().lower()

    def row_matches(row):
        if q and not (
            q in row["client"].business_name.lower()
            or q in row["project"].project_code.lower()
            or q in row["project"].name.lower()
            or q in row["category"].lower()
            or q in row["label"].lower()
        ):
            return False
        if selected_area in {"design", "development", "marketing"} and row["area"] != selected_area:
            return False
        if status == "pending" and row["audit_current"]:
            return False
        if status == "audited" and not row["audit_current"]:
            return False
        if status == "changed" and not (row["check"].is_ready and not row["audit_current"]):
            return False
        if status == "source_pending" and row["source_progress"] >= 100:
            return False
        if status == "source_done" and row["source_progress"] < 100:
            return False
        return True

    rows_by_project = OrderedDict()
    for row in all_rows:
        rows_by_project.setdefault(row["project"].pk, []).append(row)

    area_meta = [
        ("design", "Diseño"),
        ("marketing", "Marketing"),
        ("development", "Desarrollo"),
    ]

    def progress_state(progress, applies=True):
        if not applies:
            return "neutral"
        if progress >= 100:
            return "green"
        if progress >= 50:
            return "yellow"
        return "red"

    projects = []
    total_current = source_progress_sum = audited_current = 0
    area_totals = {key: {"progress_sum": 0, "projects": 0, "tasks": 0, "audited": 0} for key, _ in area_meta}

    for project_id, project_rows in rows_by_project.items():
        project = project_rows[0]["project"]
        flags = project_area_flags(project)
        area_cards = []
        overall_parts = []
        visible_project = False

        for area_key, area_label in area_meta:
            area_rows_all = [row for row in project_rows if row["area"] == area_key]
            current_rows = [row for row in area_rows_all if row["counts_for_progress"]]
            applies = bool(flags.get(area_key) or current_rows)
            progress = round(sum(row["source_progress"] for row in current_rows) / len(current_rows)) if current_rows else 0
            current_audited = sum(1 for row in current_rows if row["audit_current"])
            audit_progress = round(current_audited * 100 / len(current_rows)) if current_rows else 0
            if applies:
                overall_parts.append(progress)
                stats = area_totals[area_key]
                stats["progress_sum"] += progress
                stats["projects"] += 1
                stats["tasks"] += len(current_rows)
                stats["audited"] += current_audited

            display_rows = [row for row in area_rows_all if row_matches(row)]
            if display_rows:
                visible_project = True

            # Agrupa las tareas dentro del área por producto/categoría para lectura rápida.
            categories = OrderedDict()
            for row in display_rows:
                categories.setdefault(row["category"], []).append(row)

            area_cards.append({
                "key": area_key,
                "label": area_label,
                "applies": applies,
                "progress": progress,
                "state": progress_state(progress, applies),
                "audit_progress": audit_progress,
                "current_total": len(current_rows),
                "current_done": sum(1 for row in current_rows if row["source_progress"] >= 100),
                "current_audited": current_audited,
                "rows": display_rows,
                "categories": [{"name": name, "rows": items} for name, items in categories.items()],
            })

        # Si no hay filtro de tareas, el proyecto siempre se muestra. Con filtros,
        # solo aparece cuando al menos una fila coincide.
        if not (q or selected_area != "all" or status != "all"):
            visible_project = True
        if not visible_project:
            continue

        overall = round(sum(overall_parts) / len(overall_parts)) if overall_parts else 0
        current_project_rows = [row for row in project_rows if row["counts_for_progress"]]
        total_current += len(current_project_rows)
        source_progress_sum += sum(row["source_progress"] for row in current_project_rows)
        audited_current += sum(1 for row in current_project_rows if row["audit_current"])
        projects.append({
            "project": project,
            "areas": area_cards,
            "overall": overall,
            "overall_state": progress_state(overall, bool(overall_parts)),
            "applicable_areas": len(overall_parts),
            "current_tasks": len(current_project_rows),
            "audited_tasks": sum(1 for row in current_project_rows if row["audit_current"]),
        })

    projects.sort(key=lambda item: item["project"].client.business_name.lower())
    source_progress = round(source_progress_sum / total_current) if total_current else 0
    audit_progress = round(audited_current * 100 / total_current) if total_current else 0
    area_stats = []
    for key, label in area_meta:
        stat = area_totals[key]
        area_stats.append({
            "key": key,
            "label": label,
            "projects": stat["projects"],
            "tasks": stat["tasks"],
            "progress": round(stat["progress_sum"] / stat["projects"]) if stat["projects"] else 0,
            "audit_progress": round(stat["audited"] * 100 / stat["tasks"]) if stat["tasks"] else 0,
        })

    return render(request, "marketing/social_tracking.html", {
        "projects": projects,
        "project_count": len(projects),
        "total": total_current,
        "source_progress": source_progress,
        "audited": audited_current,
        "audit_progress": audit_progress,
        "needs_review": max(total_current - audited_current, 0),
        "area_stats": area_stats,
        "selected_area": selected_area,
        "selected_status": status,
        "search_query": request.GET.get("q", ""),
    })


@role_required("administration")
def social_tracking_audit(request, pk):
    if request.method != "POST":
        return redirect("marketing:general_audit")
    check = get_object_or_404(
        GeneralAuditCheck.objects.select_related("project__client"),
        pk=pk,
    )
    action = request.POST.get("action", "ready")
    ready = action != "reopen"
    review_general_audit_check(
        check=check,
        user=request.user,
        ready=ready,
        note=request.POST.get("note"),
    )
    log_activity(
        request.user,
        "audit",
        "general_audit_ready" if ready else "general_audit_reopen",
        check.project,
        description=f"{check.project.client.business_name} · {check.area} · {check.label}",
        metadata={"source_key": check.source_key, "audit_check_id": check.pk},
    )
    messages.success(request, "Tarea revisada." if ready else "Revisión reabierta.")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    return redirect(next_url or "marketing:general_audit")


@role_required("marketing")
def social_tracking_create(request):
    form = SocialMediaTrackingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_activity(request.user, "marketing", "social_tracking_create", obj)
        messages.success(request, "Seguimiento creado.")
        return redirect("marketing:social_tracking")
    return render(request, "marketing/form.html", {"form": form, "title": "Nuevo seguimiento Social Media / Google", "subtitle": "Estados simples: Completo/Incompleto y Sí/No."})


@role_required("marketing")
def social_tracking_edit(request, pk):
    obj = get_object_or_404(SocialMediaTracking, pk=pk)
    form = SocialMediaTrackingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_activity(request.user, "marketing", "social_tracking_update", obj)
        messages.success(request, "Seguimiento actualizado.")
        return redirect("marketing:social_tracking")
    return render(request, "marketing/form.html", {"form": form, "title": "Editar seguimiento", "subtitle": obj.client.business_name})


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
    return render(request, "marketing/form.html", {"form": form, "title": "Nuevo plan Social Media", "subtitle": "Seguimiento diario + revisión mensual."})


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
    return render(request, "marketing/form.html", {"form": form, "title": "Editar plan Social Media", "subtitle": obj.client.business_name})


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
    return render(request, "marketing/form.html", {"form": form, "title": "Seguimiento diario", "subtitle": plan.client.business_name})


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
    return render(request, "marketing/form.html", {"form": form, "title": "Brief de marketing", "subtitle": project.name})


@role_required("marketing")
def task_create(request):
    form = MarketingTaskForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        log_activity(request.user, "marketing", "task_create", obj)
        messages.success(request, "Tarea creada.")
        return redirect("marketing:list")
    return render(request, "marketing/form.html", {"form": form, "title": "Nueva tarea de marketing", "subtitle": "Tarea operativa independiente."})
