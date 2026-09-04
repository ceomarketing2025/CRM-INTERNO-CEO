from datetime import datetime, time, timedelta
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import UserAccount
from apps.audit.services import log_activity
from apps.reminders.models import Reminder, ReminderCategory, ReminderStatus
from apps.reminders.services import ensure_reminder, ensure_social_monthly_reminder
from .models import (
    AdCampaign,
    AdvertisingAccount,
    GoogleLSAWorkspace,
    MarketingChecklistItem,
    MarketingWorkspace,
)


CHECKLIST_TEMPLATE = [
    ("intake", "v4_meeting_loaded", "Información de la reunión cargada", 10),
    ("intake", "v4_meeting_document", "Documento de la reunión cargado / referenciado", 20),
    ("intake", "v4_email_defined", "Correo definido: existente o creado por Marketing", 30),
    ("intake", "v4_business_presence", "Situación de Google Business definida", 40),
    ("intake", "v4_lsa_documents", "Disponibilidad de documentos para LSA definida", 50),
    ("google_profile", "v4_gbp_link", "Link del perfil registrado", 10),
    ("google_profile", "v4_gbp_id", "ID del perfil registrado", 20),
    ("google_profile", "v4_gbp_social", "Links de redes sociales registrados", 30),
    ("google_profile", "v6_gbp_notes", "Notas registradas", 40),
    ("google_profile", "v4_gbp_reviews", "QR y mensaje de reviews preparados", 50),
    ("google_lsa", "v4_lsa_drive", "Drive de documentos registrado", 10),
    ("google_lsa", "v4_lsa_license", "Licencia de conducir validada", 20),
    ("google_lsa", "v4_lsa_founding", "Año de fundación registrado", 30),
    ("google_lsa", "v4_lsa_verification", "Verificación LSA registrada", 40),
    ("google_lsa", "v4_lsa_metrics", "Costo semanal y leads de 7 días actualizados", 50),
    ("google_lsa", "v4_lsa_followup", "Seguimiento / recordatorio configurado", 60),
    ("google_lsa", "v5_lsa_photos", "Recordatorio de fotos cada 15 días configurado", 70),
    ("meta_ads", "v4_meta_setup", "Configuración de Meta Ads registrada", 10),
    ("google_ads", "v4_google_setup", "Configuración de Google Ads registrada", 10),
    ("tiktok_ads", "v4_tiktok_setup", "Configuración de TikTok Ads registrada", 10),
    ("traditional", "v4_traditional_setup", "Publicidad tradicional definida", 10),
]

ACTIVE_CHECK_KEYS = {row[1] for row in CHECKLIST_TEMPLATE}
CRITICAL_CAMPAIGN_FIELDS = (
    "platform",
    "account_id",
    "objective",
    "campaign_type",
    "primary_keyword",
    "keyword_research",
    "creative_notes",
    "start_date",
    "end_date",
    "monthly_cost",
)


def _aware_on_date(date_value, hour=9):
    dt = datetime.combine(date_value, time(hour=hour))
    return timezone.make_aware(dt, timezone.get_current_timezone()) if timezone.is_naive(dt) else dt


def _marketing_users(project, preferred=None):
    users = []
    if preferred and getattr(preferred, "is_active", False):
        users.append(preferred)
    users.extend(
        assignment.user
        for assignment in project.assignments.select_related("user").filter(
            area="marketing", status__in=["assigned", "active"], user__is_active=True
        )
        if assignment.user
    )
    seen = set()
    result = []
    if not users:
        users.extend(UserAccount.objects.filter(role=UserAccount.Role.MARKETING, is_active=True).order_by("id"))
    for user in users:
        if user.pk in seen:
            continue
        seen.add(user.pk)
        result.append(user)
    return result


def _manager_users():
    return list(
        UserAccount.objects.filter(
            role__in=[UserAccount.Role.MANAGER, UserAccount.Role.ADMINISTRATION],
            is_active=True,
        ).order_by("role", "id")
    )


def _dual_assignees(project, marketing_user=None):
    """Gerencia + Marketing, sin duplicados."""
    result = []
    seen = set()
    for user in [*_manager_users(), *_marketing_users(project, marketing_user)]:
        if user.pk in seen:
            continue
        seen.add(user.pk)
        result.append(user)
    return result


def _cancel_source_prefix(prefix):
    Reminder.objects.filter(source_key__startswith=prefix, status=ReminderStatus.PENDING).update(
        status=ReminderStatus.CANCELLED
    )


def _set_check(workspace, key, complete, detail=""):
    try:
        item = workspace.checklist_items.get(key=key)
    except MarketingChecklistItem.DoesNotExist:
        return
    new_status = "complete" if complete else "incomplete"
    changed = item.status != new_status or (detail and item.detail != detail)
    if changed:
        item.status = new_status
        if detail:
            item.detail = detail
        item.save()


def sync_workspace_checks(workspace):
    docs = workspace.documents.all()
    _set_check(workspace, "v4_meeting_loaded", bool(workspace.meeting_summary.strip()))
    _set_check(workspace, "v4_meeting_document", docs.exists())
    _set_check(
        workspace,
        "v4_email_defined",
        workspace.email_account_mode in {"existing", "create"} and bool(workspace.gmail_email or workspace.contact_email),
        workspace.get_email_account_mode_display() if workspace.email_account_mode else "",
    )
    _set_check(workspace, "v4_business_presence", bool(workspace.business_profile_mode))
    _set_check(workspace, "v4_lsa_documents", bool(workspace.lsa_documents_available))

    _set_check(workspace, "v4_gbp_link", bool(workspace.business_profile_link))
    _set_check(workspace, "v4_gbp_id", bool(workspace.business_profile_id.strip()))
    _set_check(workspace, "v4_gbp_social", bool(workspace.business_profile_social_links.strip()))
    _set_check(workspace, "v6_gbp_notes", bool(workspace.business_profile_notes.strip()))
    _set_check(
        workspace,
        "v4_gbp_reviews",
        bool(workspace.review_link and workspace.review_message.strip()),
    )

    lsa = getattr(workspace, "lsa_workspace", None)
    if lsa:
        if workspace.lsa_documents_available == "no":
            _set_check(workspace, "v4_lsa_drive", True, "No aplica: cliente sin documentos LSA")
            _set_check(workspace, "v4_lsa_license", True, "No aplica: cliente sin documentos LSA")
        else:
            _set_check(workspace, "v4_lsa_drive", bool(lsa.documents_drive_url))
            _set_check(workspace, "v4_lsa_license", lsa.driver_license_ready == "yes")
        _set_check(workspace, "v4_lsa_founding", bool(lsa.founding_year))
        _set_check(workspace, "v4_lsa_verification", lsa.verification_status == "complete")
        _set_check(workspace, "v4_lsa_metrics", lsa.weekly_cost is not None and lsa.leads_last_7_days is not None)
        followup_ready = (
            (lsa.has_social_media == "yes" and lsa.followup_mode == "weekly" and bool(lsa.followup_start_date))
            or (lsa.has_social_media == "no" and lsa.followup_mode == "custom" and bool(lsa.custom_followup_date))
        )
        _set_check(workspace, "v4_lsa_followup", followup_ready)
        photo_ready = (
            lsa.photo_reminder_enabled == "no"
            or (lsa.photo_reminder_enabled == "yes" and bool(lsa.photo_reminder_start_date))
        )
        _set_check(workspace, "v5_lsa_photos", photo_ready)

    traditional = workspace.advertising_accounts.filter(platform="traditional").first()
    traditional_enabled = traditional.enabled if traditional else ""
    _set_check(
        workspace,
        "v4_traditional_setup",
        traditional_enabled in {"yes", "no"},
        "Publicidad tradicional activada" if traditional_enabled == "yes" else ("Publicidad tradicional desactivada" if traditional_enabled == "no" else ""),
    )

    for platform, key in [
        ("meta", "v4_meta_setup"),
        ("google", "v4_google_setup"),
        ("tiktok", "v4_tiktok_setup"),
    ]:
        account = workspace.advertising_accounts.filter(platform=platform).first()
        if not account:
            continue
        if traditional_enabled != "yes":
            _set_check(workspace, key, True, "No aplica: Publicidad tradicional no está activada")
            continue
        if account.enabled == "no":
            _set_check(workspace, key, True, "No aplica / desactivado")
        elif account.enabled == "yes":
            if platform == "meta":
                ready = (
                    bool(account.profile_url)
                    and account.portfolio_created == "yes"
                    and bool(account.portfolio_id.strip())
                    and account.ad_account_created == "yes"
                    and bool(account.account_id.strip())
                    and account.payment_method_ready == "yes"
                    and account.account_verified == "yes"
                    and account.fanpage_connected == "yes"
                    and account.campaigns_enabled in {"yes", "no"}
                )
            elif platform in {"google", "tiktok"}:
                ready = (
                    bool(account.profile_url)
                    and account.account_verified == "yes"
                    and bool(account.account_id.strip())
                    and account.payment_method_ready == "yes"
                    and account.terms_accepted == "yes"
                    and account.campaigns_enabled in {"yes", "no"}
                )
            else:
                ready = True
            _set_check(workspace, key, ready)
        else:
            _set_check(workspace, key, False)


def marketing_flow_statuses(workspace):
    """Estado semántico de cada etapa para la navegación de Marketing.

    success = todos los checks del área están completos.
    wait = existe avance, pero todavía faltan checks.
    danger = no hay avance / faltan datos obligatorios.
    """
    sync_workspace_checks(workspace)

    def area_status(areas):
        qs = workspace.checklist_items.filter(area__in=areas, active=True)
        total = qs.count()
        complete = qs.filter(status="complete").count()
        if total and complete == total:
            return "success"
        if complete:
            return "wait"
        return "danger"

    return {
        "intake": area_status(["intake"]),
        "business": area_status(["google_profile"]) if workspace.intake_ready else "danger",
        "lsa": area_status(["google_lsa"]) if workspace.intake_ready else "danger",
        "ads": area_status(["traditional", "meta_ads", "google_ads", "tiktok_ads"]) if workspace.intake_ready else "danger",
    }


def ensure_workspace(project):
    workspace, _ = MarketingWorkspace.objects.get_or_create(project=project)

    # Los checks históricos no se borran: se ocultan del flujo V4.
    workspace.checklist_items.exclude(key__in=ACTIVE_CHECK_KEYS).filter(active=True).update(active=False)
    for area, key, label, order in CHECKLIST_TEMPLATE:
        item, _ = MarketingChecklistItem.objects.get_or_create(
            workspace=workspace,
            key=key,
            defaults={"area": area, "label": label, "order": order, "active": True},
        )
        updates = []
        if item.area != area:
            item.area = area
            updates.append("area")
        if item.label != label:
            item.label = label
            updates.append("label")
        if item.order != order:
            item.order = order
            updates.append("order")
        if not item.active:
            item.active = True
            updates.append("active")
        if updates:
            item.save(update_fields=[*updates, "updated_at"])

    GoogleLSAWorkspace.objects.get_or_create(workspace=workspace)
    for platform in ["meta", "google", "tiktok", "traditional"]:
        AdvertisingAccount.objects.get_or_create(workspace=workspace, platform=platform)
    sync_workspace_checks(workspace)
    return workspace


@transaction.atomic
def save_intake(*, form, user):
    workspace = form.save(commit=False)
    workspace.shared_info_updated_by = user
    workspace.shared_info_updated_at = timezone.now()
    workspace.documents_available = workspace.lsa_documents_available or workspace.documents_available
    workspace.save()
    sync_workspace_checks(workspace)
    log_activity(user, "marketing", "intake_update", workspace, "Información inicial / reunión")
    return workspace


@transaction.atomic
def save_google_business(*, form, user):
    workspace = form.save(commit=False)

    # Cuando ya existe un link real del perfil, la situación inicial deja de ser
    # "no tiene"/"crear" y pasa a perfil existente sin pedir al usuario repetir
    # esa selección en esta pantalla.
    if workspace.business_profile_link and workspace.business_profile_mode in {"", "no", "create"}:
        workspace.business_profile_mode = "existing"

    # El mensaje de reviews es controlado por el CRM para que siempre coincida
    # con el link que genera el QR.
    if workspace.review_link:
        workspace.review_message = build_google_review_message(
            workspace.review_link,
            workspace.project.client.business_name,
        )
    else:
        workspace.review_message = ""

    workspace.shared_info_updated_by = user
    workspace.shared_info_updated_at = timezone.now()
    workspace.save()
    sync_workspace_checks(workspace)
    log_activity(user, "marketing", "google_business_update", workspace, workspace.get_business_profile_status_display())
    return workspace


def build_google_review_message(review_link, company_name):
    """Genera un mensaje de reviews general usando el nombre real del cliente."""
    company_name = (company_name or "our company").strip()
    return (
        "Hi there! 👋\n\n"
        f"Thank you for choosing {company_name}. We truly appreciate the opportunity to work with you.\n\n"
        "If you were happy with our service, would you mind taking a minute to leave us a 5-star Google review? ⭐ "
        "Your feedback helps our business grow and helps other customers feel confident choosing our services.\n\n"
        "You can leave your review by clicking the link below or simply scanning the QR code attached.\n\n"
        "⭐ Google Review:\n\n"
        f"{review_link}\n\n"
        "Thank you so much for your support! 🙌\n\n"
        f"{company_name}"
    )


def ensure_lsa_followup_reminders(lsa, *, user=None, horizon_weeks=12):
    project = lsa.workspace.project
    _cancel_source_prefix(f"marketing-lsa:{lsa.pk}:review:")
    if lsa.followup_mode == "none":
        return

    dates = []
    if lsa.followup_mode == "custom" and lsa.custom_followup_date:
        dates = [lsa.custom_followup_date]
    elif lsa.followup_mode == "weekly" and lsa.followup_start_date:
        current = lsa.followup_start_date
        today = timezone.localdate()
        while current < today:
            current += timedelta(days=7)
        dates = [current + timedelta(days=7 * i) for i in range(horizon_weeks)]

    for due_date in dates:
        for assignee in _dual_assignees(project, lsa.workspace.assigned_to):
            ensure_reminder(
                source_key=f"marketing-lsa:{lsa.pk}:review:{due_date.isoformat()}:user:{assignee.pk}",
                title=f"Revisión Google LSA · {project.client.business_name}",
                category=ReminderCategory.CAMPAIGN_WEEKLY,
                due_at=_aware_on_date(due_date),
                client=project.client,
                project=project,
                assigned_to=assignee,
                notes="Revisar LSA: documentos, licencia, costo semanal, leads de los últimos 7 días y observaciones.",
                user=user,
            )


def ensure_lsa_photo_reminders(lsa, *, user=None, occurrences=12):
    project = lsa.workspace.project
    _cancel_source_prefix(f"marketing-lsa:{lsa.pk}:photos:")
    if lsa.photo_reminder_enabled != "yes" or not lsa.photo_reminder_start_date:
        return
    current = lsa.photo_reminder_start_date
    today = timezone.localdate()
    while current < today:
        current += timedelta(days=15)
    for i in range(occurrences):
        due_date = current + timedelta(days=15 * i)
        for assignee in _dual_assignees(project, lsa.workspace.assigned_to):
            ensure_reminder(
                source_key=f"marketing-lsa:{lsa.pk}:photos:{due_date.isoformat()}:user:{assignee.pk}",
                title=f"Subir fotos Google LSA · {project.client.business_name}",
                category=ReminderCategory.FOLLOWUP_15,
                due_at=_aware_on_date(due_date),
                client=project.client,
                project=project,
                assigned_to=assignee,
                notes="Recordatorio de Marketing: subir/actualizar fotos de Google LSA. Se repite cada 15 días para Marketing y Administración/Gerencia.",
                user=user,
            )


@transaction.atomic
def save_lsa(*, form, user):
    lsa = form.save()
    _cancel_source_prefix(f"marketing-lsa:{lsa.pk}:")
    ensure_lsa_followup_reminders(lsa, user=user)
    ensure_lsa_photo_reminders(lsa, user=user)
    sync_workspace_checks(lsa.workspace)
    log_activity(user, "marketing", "lsa_update", lsa, lsa.get_verification_status_display())
    return lsa


@transaction.atomic
def save_advertising_account(*, form, account, user):
    obj = form.save(commit=False)
    obj.workspace = account.workspace
    obj.platform = account.platform
    obj.save()
    sync_workspace_checks(obj.workspace)
    log_activity(user, "marketing", "ad_account_update", obj, obj.get_platform_display())
    return obj


def _campaign_manager_review_reminders(campaign, *, user=None):
    project = campaign.project
    _cancel_source_prefix(f"campaign:{campaign.pk}:manager-review")
    managers = _manager_users()
    for manager in managers:
        ensure_reminder(
            source_key=f"campaign:{campaign.pk}:manager-review:manager:{manager.pk}",
            title=f"VALIDAR antes de lanzar · {campaign.get_platform_display()} · {project.client.business_name}",
            category=ReminderCategory.CAMPAIGN_MANAGER_REVIEW,
            due_at=timezone.now(),
            client=project.client,
            project=project,
            assigned_to=manager,
            notes="Marketing solicita validación obligatoria. Revisar objetivo, tipo, fechas, configuración, presupuesto, keywords/artes cuando apliquen. No lanzar hasta aprobar.",
            user=user,
        )
    for marketing_user in _marketing_users(project, campaign.assigned_to):
        ensure_reminder(
            source_key=f"campaign:{campaign.pk}:manager-review:marketing:{marketing_user.pk}",
            title=f"Campaña esperando validación · {campaign.get_platform_display()} · {project.client.business_name}",
            category=ReminderCategory.CAMPAIGN_MANAGER_REVIEW,
            due_at=timezone.now(),
            client=project.client,
            project=project,
            assigned_to=marketing_user,
            notes="La campaña fue enviada a Gerencia. No debe lanzarse hasta que sea aprobada.",
            user=user,
        )


def ensure_campaign_weekly_dual_reminders(campaign, *, user=None):
    _cancel_source_prefix(f"campaign:{campaign.pk}:weekly-v4:")
    _cancel_source_prefix(f"campaign:{campaign.pk}:week:")  # recordatorios V3
    if not campaign.weekly_followup_enabled or not campaign.start_date or not campaign.end_date:
        return
    current = campaign.start_date + timedelta(days=7)
    today = timezone.localdate()
    while current < today:
        current += timedelta(days=7)
    index = max(1, ((current - campaign.start_date).days // 7))
    while current <= campaign.end_date and index <= 60:
        for assignee in _dual_assignees(campaign.project, campaign.assigned_to):
            ensure_reminder(
                source_key=f"campaign:{campaign.pk}:weekly-v4:{index}:user:{assignee.pk}",
                title=f"Seguimiento semanal {campaign.get_platform_display()} · {campaign.project.client.business_name}",
                category=ReminderCategory.CAMPAIGN_WEEKLY,
                due_at=_aware_on_date(current),
                client=campaign.project.client,
                project=campaign.project,
                assigned_to=assignee,
                notes="Registrar resultados del periodo, gasto, leads/conversiones, ajustes y notas. Marketing y Gerencia reciben este seguimiento.",
                user=user,
            )
        current += timedelta(days=7)
        index += 1


@transaction.atomic
def save_campaign(*, form, user):
    original = None
    if form.instance.pk:
        original = AdCampaign.objects.filter(pk=form.instance.pk).first()

    obj = form.save(commit=False)
    critical_changed = False
    if original and original.manager_approved:
        critical_changed = any(getattr(original, field) != getattr(obj, field) for field in CRITICAL_CAMPAIGN_FIELDS)
        if critical_changed:
            obj.manager_approved = False
            obj.manager_approved_by = None
            obj.manager_approved_at = None
            if obj.status not in {"draft", "changes_requested"}:
                obj.status = "manager_review"

    # Marketing nunca puede saltarse la revisión cambiando directamente el estado.
    if obj.status in {"approved", "scheduled", "launched", "completed"} and not obj.manager_approved:
        obj.status = "manager_review"

    obj.save()

    if obj.status == "manager_review":
        _campaign_manager_review_reminders(obj, user=user)
    else:
        _cancel_source_prefix(f"campaign:{obj.pk}:manager-review")

    if obj.status == "launched" and obj.manager_approved:
        ensure_campaign_weekly_dual_reminders(obj, user=user)
    else:
        _cancel_source_prefix(f"campaign:{obj.pk}:weekly-v4:")
        _cancel_source_prefix(f"campaign:{obj.pk}:week:")

    description = obj.get_status_display()
    if critical_changed:
        description += " · aprobación invalidada por cambios críticos"
    log_activity(user, "marketing", "campaign_save", obj, description)
    return obj, critical_changed


@transaction.atomic
def review_campaign(*, campaign, decision, notes, user):
    _cancel_source_prefix(f"campaign:{campaign.pk}:manager-review")
    campaign.manager_review_notes = notes
    if decision == "approved":
        campaign.manager_approved = True
        campaign.manager_approved_by = user
        campaign.manager_approved_at = timezone.now()
        campaign.status = "approved"
    else:
        campaign.manager_approved = False
        campaign.manager_approved_by = None
        campaign.manager_approved_at = None
        campaign.status = "changes_requested"
    campaign.save(update_fields=[
        "manager_review_notes", "manager_approved", "manager_approved_by",
        "manager_approved_at", "status", "updated_at"
    ])

    # Marketing recibe la decisión.
    for marketing_user in _marketing_users(campaign.project, campaign.assigned_to):
        ensure_reminder(
            source_key=f"campaign:{campaign.pk}:decision:{campaign.updated_at.isoformat()}:user:{marketing_user.pk}",
            title=("Campaña aprobada" if decision == "approved" else "Campaña requiere correcciones") + f" · {campaign.project.client.business_name}",
            category=ReminderCategory.CAMPAIGN_MANAGER_REVIEW,
            due_at=timezone.now(),
            client=campaign.project.client,
            project=campaign.project,
            assigned_to=marketing_user,
            notes=notes or ("Puede programarse/lanzarse." if decision == "approved" else "Revisar observaciones de Gerencia y volver a enviar a validación."),
            user=user,
        )
    log_activity(user, "marketing", "campaign_manager_review", campaign, campaign.get_status_display())
    return campaign


def refresh_lsa_followups(*, user=None):
    for lsa in GoogleLSAWorkspace.objects.select_related("workspace__project", "workspace__assigned_to").all():
        _cancel_source_prefix(f"marketing-lsa:{lsa.pk}:")
        if lsa.followup_mode in {"weekly", "custom"}:
            ensure_lsa_followup_reminders(lsa, user=user)
        if lsa.photo_reminder_enabled == "yes":
            ensure_lsa_photo_reminders(lsa, user=user)


def save_social_plan(*, form, user):
    obj = form.save()
    ensure_social_monthly_reminder(obj, user=user)
    log_activity(user, "marketing", "social_plan_save", obj)
    return obj


# ---------------------------------------------------------------------------
# Seguimiento Social Media · dashboard automático de auditoría
# ---------------------------------------------------------------------------

def _social_audit_chip(label, state="wait", detail=""):
    return {"label": label, "state": state, "detail": detail}


def _social_binary_chip(value, *, missing=False):
    if missing:
        return _social_audit_chip("Sin ficha", "muted")
    if value == "complete":
        return _social_audit_chip("Completo", "success")
    return _social_audit_chip("Pendiente", "wait")


def _social_max_datetime(*values):
    values = [value for value in values if value]
    return max(values) if values else None


def build_social_media_audit_rows(*, today=None):
    """Construye el reporte desde las fuentes reales, sin duplicar captura.

    Fuente de verdad:
    - Plan/proyecto: ProjectPlanAssignment.
    - Contenido y redes: Diseño / ClientPlan / SocialMediaCycle.
    - GBP, LSA y Ads: MarketingWorkspace y sus módulos.
    - SocialMediaTracking: solo fallback histórico para datos previos a V7.
    """
    from django.utils import timezone

    from apps.design.services import ensure_current_social_media_cycle
    from apps.plans.models.choices import PlanDepartment, ServiceType
    from apps.projects.models import ProjectPlanAssignment
    from .models import SocialMediaAudit, SocialMediaTracking

    today = today or timezone.localdate()
    assignments = list(
        ProjectPlanAssignment.objects
        .select_related(
            "project__client",
            "plan",
            "subscription",
            "subscription__assigned_design_user",
            "project__marketing_workspace",
            "project__marketing_workspace__lsa_workspace",
        )
        .prefetch_related(
            "project__marketing_workspace__advertising_accounts",
            "project__marketing_workspace__checklist_items",
        )
        .filter(
            is_active=True,
            plan__department=PlanDepartment.DESIGN,
            plan__service_type=ServiceType.SOCIAL_MEDIA,
        )
        .order_by("project__client__business_name", "plan__name", "id")
    )

    client_ids = {item.project.client_id for item in assignments}
    legacy_by_client = {
        item.client_id: item
        for item in SocialMediaTracking.objects.filter(client_id__in=client_ids).select_related("project")
    }

    rows = []
    for project_plan in assignments:
        project = project_plan.project
        client = project.client
        subscription = project_plan.subscription
        legacy = legacy_by_client.get(client.pk)
        audit, _ = SocialMediaAudit.objects.get_or_create(project_plan=project_plan)

        cycle = None
        items = []
        if subscription and subscription.is_active:
            cycle = ensure_current_social_media_cycle(subscription, today=today)
            if cycle:
                items = list(cycle.items.all())

        try:
            workspace = project.marketing_workspace
        except Exception:
            workspace = None
        if workspace:
            # Mantiene el checklist V7 sincronizado sin crear una ficha de
            # Marketing para proyectos que todavía no la tienen.
            workspace = ensure_workspace(project)
        try:
            lsa = workspace.lsa_workspace if workspace else None
        except Exception:
            lsa = None

        accounts = list(workspace.advertising_accounts.all()) if workspace else []
        checks = list(workspace.checklist_items.all()) if workspace else []
        active_checks = [item for item in checks if item.active]
        complete_checks = [item for item in active_checks if item.status == "complete"]
        marketing_progress = round(len(complete_checks) * 100 / len(active_checks)) if active_checks else 0

        if not subscription:
            content = _social_audit_chip("Falta configurar", "danger", "El plan está contratado pero aún no tiene suscripción operativa en Diseño.")
            design_progress = 0
            networks_label = "Sin configurar"
        elif not cycle or not items:
            content = _social_audit_chip("Sin entregables", "wait", "Configura posts/videos del plan para generar el ciclo.")
            design_progress = 0
            networks_label = subscription.social_networks_label
        else:
            design_progress = cycle.progress_percent
            if cycle.completed:
                content = _social_audit_chip(f"100% · {cycle.completed_items}/{cycle.total_items}", "success", "Contenido listo y publicado en todas las redes seleccionadas.")
            else:
                content = _social_audit_chip(f"{design_progress}% · {cycle.completed_items}/{cycle.total_items}", "wait", "Avance sincronizado desde Diseño.")
            networks_label = subscription.social_networks_label

        if workspace:
            reviews = _social_binary_chip(workspace.business_profile_reviews_status)
            products = _social_binary_chip(workspace.business_profile_products_status)
            profile_percentage = _social_binary_chip(workspace.business_profile_completion_status)
            website_gb = _social_binary_chip(workspace.business_profile_website_status)
            photos = _social_binary_chip(workspace.business_profile_photos_status)
            last_post = workspace.business_profile_last_post
            gb_notes = workspace.business_profile_notes.strip()

            gb_state = workspace.business_profile_status
            if gb_state == "approved":
                google_business = _social_audit_chip("Aprobado", "success")
            elif gb_state == "denied":
                google_business = _social_audit_chip("Desaprobado", "danger")
            elif gb_state == "verification":
                google_business = _social_audit_chip("En verificación", "wait")
            else:
                google_business = _social_audit_chip("No iniciado", "wait")
        else:
            reviews = _social_binary_chip(None, missing=True)
            products = _social_binary_chip(None, missing=True)
            profile_percentage = _social_binary_chip(None, missing=True)
            website_gb = _social_binary_chip(None, missing=True)
            photos = _social_binary_chip(None, missing=True)
            last_post = None
            gb_notes = ""
            google_business = _social_audit_chip("Sin ficha", "muted")

        # Fallback histórico: conserva el valor del seguimiento anterior cuando
        # todavía no fue migrado a la ficha fuente de Marketing.
        if legacy:
            if workspace and workspace.business_profile_reviews_status == "incomplete" and legacy.reviews == "complete":
                reviews = _social_binary_chip(legacy.reviews)
            if workspace and workspace.business_profile_products_status == "incomplete" and legacy.products == "complete":
                products = _social_binary_chip(legacy.products)
            if workspace and workspace.business_profile_completion_status == "incomplete" and legacy.profile_percentage == "complete":
                profile_percentage = _social_binary_chip(legacy.profile_percentage)
            if workspace and workspace.business_profile_website_status == "incomplete" and legacy.website_in_gb == "complete":
                website_gb = _social_binary_chip(legacy.website_in_gb)
            if workspace and workspace.business_profile_photos_status == "incomplete" and legacy.photos == "complete":
                photos = _social_binary_chip(legacy.photos)
            last_post = last_post or legacy.last_post_gb
            gb_notes = gb_notes or legacy.gb_notes.strip()

        if lsa:
            if lsa.verification_status == "complete":
                lsa_status = _social_audit_chip("Completo", "success")
            elif workspace and workspace.lsa_documents_available == "no":
                lsa_status = _social_audit_chip("Sin documentos", "muted")
            else:
                lsa_status = _social_audit_chip("Pendiente", "wait")

            if lsa.followup_mode == "weekly" and lsa.followup_start_date:
                google_followup = _social_audit_chip("Sí · semanal", "success")
            elif lsa.followup_mode == "custom" and lsa.custom_followup_date:
                google_followup = _social_audit_chip("Sí · fecha", "success")
            elif lsa.followup_mode == "none":
                google_followup = _social_audit_chip("No", "muted")
            else:
                google_followup = _social_audit_chip("Pendiente", "wait")

            if lsa.last_lead_date:
                leads_label = lsa.last_lead_date.strftime("%d/%m/%Y")
            elif lsa.leads_last_7_days is not None:
                leads_label = f"{lsa.leads_last_7_days} / 7 días"
            else:
                leads_label = "—"
        else:
            lsa_status = _social_audit_chip("Sin ficha", "muted")
            google_followup = _social_audit_chip("Sin ficha", "muted")
            leads_label = "—"

        if legacy and leads_label == "—" and legacy.last_lead:
            leads_label = legacy.last_lead

        enabled_ads = [account for account in accounts if account.platform != "traditional" and account.enabled == "yes"]
        if not enabled_ads:
            ads_verified = _social_audit_chip("No aplica", "muted")
        else:
            platforms = ", ".join(account.get_platform_display() for account in enabled_ads)
            if all(account.account_verified == "yes" for account in enabled_ads):
                ads_verified = _social_audit_chip("Verificado", "success", platforms)
            else:
                ads_verified = _social_audit_chip("Pendiente", "wait", platforms)

        source_updated_at = _social_max_datetime(
            project_plan.updated_at,
            subscription.updated_at if subscription else None,
            cycle.updated_at if cycle else None,
            max((item.updated_at for item in items), default=None),
            workspace.updated_at if workspace else None,
            lsa.updated_at if lsa else None,
            max((account.updated_at for account in accounts), default=None),
            max((check.updated_at for check in checks), default=None),
        )
        audit_current = bool(
            audit.is_ready
            and audit.reviewed_at
            and (not source_updated_at or audit.reviewed_at >= source_updated_at)
        )
        if audit_current:
            audit_chip = _social_audit_chip("Listo", "success")
        elif audit.is_ready:
            audit_chip = _social_audit_chip("Cambios nuevos", "wait", "Diseño o Marketing cambió después de la última auditoría.")
        else:
            audit_chip = _social_audit_chip("Pendiente", "wait")

        notes = []
        if workspace and workspace.notes.strip():
            notes.append(workspace.notes.strip())
        if lsa and lsa.notes.strip():
            notes.append(lsa.notes.strip())
        if legacy and legacy.notes.strip() and legacy.notes.strip() not in notes:
            notes.append(legacy.notes.strip())

        rows.append({
            "project_plan": project_plan,
            "project": project,
            "client": client,
            "subscription": subscription,
            "cycle": cycle,
            "audit": audit,
            "audit_current": audit_current,
            "audit_chip": audit_chip,
            "content": content,
            "design_progress": design_progress,
            "reviews": reviews,
            "products": products,
            "profile_percentage": profile_percentage,
            "google_business": google_business,
            "networks_label": networks_label,
            "website_gb": website_gb,
            "last_post": last_post,
            "gb_notes": gb_notes,
            "lsa": lsa_status,
            "photos": photos,
            "last_lead": leads_label,
            "ads_verified": ads_verified,
            "google_followup": google_followup,
            "marketing_progress": marketing_progress,
            "marketing_checks_complete": len(complete_checks),
            "marketing_checks_total": len(active_checks),
            "notes": notes,
            "source_updated_at": source_updated_at,
        })

    return rows


def review_social_media_audit(*, audit, user, ready=True, note=None):
    """Única escritura del dashboard: confirmar o reabrir la auditoría."""
    audit.is_ready = bool(ready)
    if note is not None:
        audit.note = note.strip()
    if audit.is_ready:
        audit.reviewed_at = timezone.now()
        audit.reviewed_by = user
    else:
        audit.reviewed_at = None
        audit.reviewed_by = None
    audit.save(update_fields=["is_ready", "reviewed_at", "reviewed_by", "note", "updated_at"])
    return audit
