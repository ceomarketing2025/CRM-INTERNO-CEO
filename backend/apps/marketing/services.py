from django.db import transaction
from apps.audit.services import log_activity
from apps.reminders.models import ReminderCategory
from apps.reminders.services import ensure_campaign_weekly_reminders, ensure_reminder, ensure_social_monthly_reminder
from django.utils import timezone
from apps.accounts.models import UserAccount
from .models import MarketingChecklistItem, MarketingWorkspace


CHECKLIST_TEMPLATE = [
    ("intake", "meeting_data", "Recolectar datos de la reunión", 10),
    ("intake", "request_credentials", "Pedir credenciales por el grupo", 20),
    ("intake", "request_pdf_docs", "Pedir documentos en PDF", 30),
    ("google_profile", "create_gmail", "Crear Gmail", 10),
    ("google_profile", "create_business_profile", "Crear Google Business Profile", 20),
    ("google_profile", "load_business_info", "Cargar dueño, nombre legal, fundación, redes, descripción, horario, servicios y áreas", 30),
    ("google_profile", "business_verification", "Enviar a verificación y registrar aprobado/desaprobado", 40),
    ("google_profile", "review_link_qr", "Con perfil verificado: generar link de reviews, QR y mensaje", 50),
    ("google_lsa", "verify_google_ads", "Verificación de Google Ads", 10),
    ("google_lsa", "verify_lsa", "Verificación de Google LSA", 20),
    ("google_lsa", "launch_guarantee", "Lanzar Google Guarantee / seguimiento si falta por reviews", 30),
    ("meta_ads", "meta_portfolio", "Crear portafolio", 10),
    ("meta_ads", "meta_ad_account", "Crear cuenta publicitaria", 20),
    ("meta_ads", "meta_fanpage", "Vincular fanpage / pedir acceso", 30),
    ("meta_ads", "meta_creative_ideas", "Crear ideas de artes", 40),
    ("meta_ads", "meta_study", "Realizar estudio", 50),
    ("meta_ads", "meta_client_proposal", "Enviar propuesta de artes al cliente", 60),
    ("meta_ads", "meta_design_brief", "Enviar a Diseño cómo deben realizarse los artes", 70),
    ("meta_ads", "meta_manager_review", "Crear campaña y verificar con Gerencia antes de lanzar", 80),
    ("meta_ads", "meta_duration", "Establecer duración de campaña", 90),
    ("meta_ads", "meta_launch", "Lanzar campaña", 100),
    ("meta_ads", "meta_weekly", "Seguimiento semanal durante el periodo", 110),
    ("google_ads", "google_account", "Crear cuenta y registrar ID", 10),
    ("google_ads", "google_account_verify", "Verificar cuenta", 20),
    ("google_ads", "google_tags", "Vincular tags si es necesario", 30),
    ("google_ads", "google_objective", "Definir objetivo y tipo de campaña", 40),
    ("google_ads", "google_keywords", "Buscar keywords", 50),
    ("google_ads", "google_client_proposal", "Si aplica: enviar propuesta de artes al cliente", 60),
    ("google_ads", "google_design_brief", "Enviar a Diseño cómo deben realizarse los artes", 70),
    ("google_ads", "google_manager_review", "Crear campaña y verificar con Gerencia antes de lanzar", 80),
    ("google_ads", "google_duration", "Establecer duración de campaña", 90),
    ("google_ads", "google_launch", "Lanzar campaña", 100),
    ("google_ads", "google_weekly", "Seguimiento semanal durante el periodo", 110),
    ("social_media", "social_daily", "Seguimiento diario", 10),
    ("social_media", "social_publications", "Publicaciones del plan", 20),
    ("social_media", "social_monthly_report", "Revisión / informe mensual", 30),
]


def ensure_workspace(project):
    workspace, _ = MarketingWorkspace.objects.get_or_create(project=project)
    for area, key, label, order in CHECKLIST_TEMPLATE:
        MarketingChecklistItem.objects.get_or_create(workspace=workspace, key=key, defaults={"area": area, "label": label, "order": order})
    return workspace


@transaction.atomic
def save_campaign(*, form, user):
    obj = form.save()
    if obj.status == "manager_review":
        manager = UserAccount.objects.filter(role=UserAccount.Role.MANAGER, is_active=True).order_by("id").first()
        ensure_reminder(
            source_key=f"campaign:{obj.pk}:manager-review",
            title=f"Revisar campaña {obj.get_platform_display()} · {obj.project.client.business_name}",
            category=ReminderCategory.CAMPAIGN_MANAGER_REVIEW,
            due_at=timezone.now(),
            client=obj.project.client, project=obj.project, assigned_to=manager, user=user,
            notes="Revisar configuración, objetivo, segmentación, presupuesto, artes y duración antes del lanzamiento.",
        )
    if obj.status == "launched":
        ensure_campaign_weekly_reminders(obj, user=user)
    log_activity(user, "marketing", "campaign_save", obj, obj.get_status_display())
    return obj


def save_social_plan(*, form, user):
    obj = form.save()
    ensure_social_monthly_reminder(obj, user=user)
    log_activity(user, "marketing", "social_plan_save", obj)
    return obj
