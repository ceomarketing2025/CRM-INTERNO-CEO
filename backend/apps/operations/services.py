from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from apps.audit.services import log_activity
from apps.reminders.services import ensure_credential_renewal_reminder, ensure_launch_followups
from .models import (
    CredentialType,
    DomainHostingRecord,
    HostingProvider,
    ProductionRecord,
    ProjectCredential,
    SeoComplexity,
    WebProductionCity,
    WebProductionCounty,
    WebProductionCountyService,
    WebProductionPage,
)


DEFAULT_MAIN_PAGES = [
    "Home",
    "About",
    "Services",
    "Areas We Service",
    "Gallery",
    "Contact",
    "Blog / FAQ",
    "Free Estimate",
]

DEFAULT_HEADER = "Home | About | Services | Areas We Service | Gallery | Contact | Free Estimate"


def _sync_hosting_credentials(record, user):
    """Prepara Servidor + WordPress en Credenciales usando el proveedor administrativo.

    No inventa correos ni contraseñas: solo deja los accesos habilitados para que
    Administración/Gerencia completen los datos cuando los tengan.
    """
    provider = record.provider_label
    server = ProjectCredential.objects.filter(
        project=record.project, credential_type=CredentialType.SERVER
    ).order_by("id").first()
    if server is None:
        server = ProjectCredential(
            client=record.client,
            project=record.project,
            credential_type=CredentialType.SERVER,
            created_by=user,
        )
    server.client = record.client
    server.custom_name = provider
    server.enabled = True
    server.updated_by = user
    if not server.notes:
        server.notes = "Proveedor detectado automáticamente desde Dominios y Hosting."
    server.full_clean()
    server.save()

    wordpress = ProjectCredential.objects.filter(
        project=record.project, credential_type=CredentialType.WORDPRESS
    ).order_by("id").first()
    if wordpress is None:
        wordpress = ProjectCredential(
            client=record.client,
            project=record.project,
            credential_type=CredentialType.WORDPRESS,
            created_by=user,
        )
    wordpress.client = record.client
    wordpress.enabled = True
    wordpress.updated_by = user
    if not wordpress.notes:
        wordpress.notes = f"Acceso web preparado junto al hosting {provider}."
    wordpress.full_clean()
    wordpress.save()


@transaction.atomic
def save_domain_hosting_record(*, form, user):
    obj = form.save(commit=False)
    obj.created_by = obj.created_by or user
    obj.updated_by = user
    obj.full_clean()
    obj.save()
    _sync_hosting_credentials(obj, user)
    log_activity(user, "operations", "domain_hosting_save", obj, obj.project_domain_label)
    return obj


def _sync_credential_to_shared_areas(credential, user):
    """Push positive credential state into fields shared by Marketing/Desarrollo.

    We only synchronize facts that the credential proves. Removing/turning off a
    credential never deletes manually collected business information.
    """
    if not credential.enabled:
        return

    from apps.marketing.services import ensure_workspace, sync_workspace_checks
    from apps.questionnaires.models import ProjectQuestionnaire
    from apps.questionnaires.services import WEBSITE_TEMPLATE_CODE, save_key_answer, website_questionnaire_progress
    from apps.questionnaires.models.choices import QuestionnaireStatus

    workspace = ensure_workspace(credential.project)
    now = timezone.now()
    changed = []

    if credential.credential_type in {CredentialType.GOOGLE, CredentialType.GOOGLE_BUSINESS}:
        # V11 agrupa los accesos Google en una sola credencial. Al habilitarla
        # dejamos constancia compartida de que el ecosistema Google ya tiene acceso.
        workspace.business_profile_mode = "existing"
        if credential.account_email:
            workspace.gmail_email = credential.account_email
            workspace.email_account_mode = "existing"
        workspace.shared_info_updated_by = user
        workspace.shared_info_updated_at = now
        changed += ["business_profile_mode", "gmail_email", "email_account_mode", "shared_info_updated_by", "shared_info_updated_at", "updated_at"]
    elif credential.credential_type == CredentialType.WEBMAIL:
        workspace.webmail_has = "yes"
        if credential.account_email:
            workspace.webmail_email = credential.account_email
        workspace.shared_info_updated_by = user
        workspace.shared_info_updated_at = now
        changed += ["webmail_has", "webmail_email", "shared_info_updated_by", "shared_info_updated_at", "updated_at"]

    if changed:
        workspace.save(update_fields=list(dict.fromkeys(changed)))
        sync_workspace_checks(workspace)

    if credential.credential_type in {CredentialType.GOOGLE, CredentialType.GOOGLE_BUSINESS}:
        business_item = workspace.checklist_items.filter(key="create_business_profile").first()
        if business_item and business_item.status != "complete":
            business_item.status = "complete"
            business_item.detail = (business_item.detail or "") or "Acceso Google registrado en Administración."
            business_item.save()
        gmail_item = workspace.checklist_items.filter(key="create_gmail").first()
        if gmail_item and credential.account_email and gmail_item.status != "complete":
            gmail_item.status = "complete"
            gmail_item.detail = (gmail_item.detail or "") or f"Cuenta registrada: {credential.account_email}"
            gmail_item.save()

    questionnaire = ProjectQuestionnaire.objects.filter(
        project=credential.project,
        template__code=WEBSITE_TEMPLATE_CODE,
    ).select_related("template").prefetch_related("template__sections__questions", "answers__question").first()
    if not questionnaire:
        return

    if credential.credential_type in {CredentialType.GOOGLE, CredentialType.GOOGLE_BUSINESS}:
        save_key_answer(
            questionnaire=questionnaire,
            key="has_gbp",
            user=user,
            value_text="Acceso Google disponible · credenciales registradas",
            value_json={"mode": "existing", "link": workspace.business_profile_link or "", "credential_ready": True},
            complete=True,
        )
    elif credential.credential_type == CredentialType.WEBMAIL:
        save_key_answer(
            questionnaire=questionnaire,
            key="has_webmail",
            user=user,
            value_text=credential.account_email or "Webmail configurado",
            value_json={"has": "yes", "email": credential.account_email or "", "credential_ready": True},
            complete=True,
        )

    progress = website_questionnaire_progress(questionnaire)
    questionnaire.status = QuestionnaireStatus.COMPLETE if progress["percent"] == 100 else QuestionnaireStatus.IN_PROGRESS
    questionnaire.save(update_fields=["status", "updated_at"])


@transaction.atomic
def upsert_project_credential(*, client, project, credential_type, user, account_email="", password="", login_url="", custom_name="", visible_to_team=False, enabled=True, notes=""):
    obj = ProjectCredential.objects.filter(project=project, credential_type=credential_type).order_by("id").first()
    if obj is None:
        obj = ProjectCredential(project=project, client=client, credential_type=credential_type, created_by=user)
    obj.client = client
    obj.custom_name = custom_name or obj.custom_name
    obj.account_email = account_email or ""
    obj.login_url = login_url or ""
    obj.enabled = enabled
    obj.notes = notes or obj.notes
    obj.updated_by = user
    if getattr(user, "is_manager", False):
        obj.visible_to_team = bool(visible_to_team)
    elif not obj.pk:
        obj.visible_to_team = False
    if password:
        obj.set_password(password)
    obj.full_clean()
    obj.save()
    _sync_credential_to_shared_areas(obj, user)
    log_activity(user, "operations", "credential_save", obj, f"{obj.display_name} · {'visible' if obj.visible_to_team else 'privada'}")
    return obj


@transaction.atomic
def create_custom_project_credential(*, client, project, user, custom_name, account_email="", password="", login_url="", visible_to_team=False, notes=""):
    obj = ProjectCredential(
        client=client,
        project=project,
        credential_type=CredentialType.OTHER,
        custom_name=custom_name.strip(),
        account_email=account_email.strip(),
        login_url=login_url.strip(),
        notes=notes.strip(),
        enabled=True,
        created_by=user,
        updated_by=user,
        visible_to_team=bool(visible_to_team) if getattr(user, "is_manager", False) else False,
    )
    if password:
        obj.set_password(password)
    obj.full_clean()
    obj.save()
    log_activity(user, "operations", "credential_save", obj, f"{obj.display_name} · {'visible' if obj.visible_to_team else 'privada'}")
    return obj


@transaction.atomic
def save_project_credential(*, form, user):
    obj = form.save(commit=False)
    obj.created_by = obj.created_by or user
    obj.updated_by = user
    raw_password = form.cleaned_data.get("password")
    if raw_password:
        obj.set_password(raw_password)
    if not getattr(user, "is_manager", False):
        if obj.pk:
            previous = ProjectCredential.objects.filter(pk=obj.pk).values_list("visible_to_team", flat=True).first()
            if previous is not None:
                obj.visible_to_team = previous
        else:
            obj.visible_to_team = False
    obj.full_clean()
    obj.save()
    _sync_credential_to_shared_areas(obj, user)
    log_activity(user, "operations", "credential_save", obj, f"{obj.display_name} · {'visible' if obj.visible_to_team else 'privada'}")
    return obj


@transaction.atomic
def save_credential_purchase(*, form, user):
    obj = form.save(commit=False)
    obj.created_by = obj.created_by or user
    obj.save()
    ensure_credential_renewal_reminder(obj, user=user)
    log_activity(user, "operations", "credential_purchase", obj, f"Renovación: {obj.renewal_date}")
    return obj


@transaction.atomic
def save_production_record(*, form, user):
    previous_status = None
    if form.instance.pk:
        previous_status = ProductionRecord.objects.filter(pk=form.instance.pk).values_list("status", flat=True).first()
    obj = form.save(commit=False)
    obj.created_by = obj.created_by or user
    obj.save()
    if obj.project and obj.website_url:
        obj.project.client.website = obj.website_url
        obj.project.client.save(update_fields=["website", "updated_at"])
    if obj.project and obj.status == "delivered" and previous_status != "delivered":
        ensure_launch_followups(obj.project, user=user)
    log_activity(user, "operations", "production_update", obj, obj.get_status_display())
    return obj


def auto_workload(obj):
    """Assign complexity and points consistently; users never edit these values."""
    if isinstance(obj, WebProductionCountyService):
        return SeoComplexity.COMPLEX, 3
    if isinstance(obj, (WebProductionCounty, WebProductionCity)):
        return SeoComplexity.MEDIUM, 2
    if isinstance(obj, WebProductionPage):
        name = (obj.name or "").lower()
        if any(token in name for token in ["home", "services", "areas"]):
            return SeoComplexity.MEDIUM, 2
        if any(token in name for token in ["blog", "faq"]):
            return SeoComplexity.MEDIUM, 2
        return SeoComplexity.SIMPLE, 1
    return SeoComplexity.SIMPLE, 1


def apply_seo_automation(obj):
    complexity, points = auto_workload(obj)
    obj.complexity = complexity
    obj.points = points
    # Slug starts automatically, but a developer can override it later.
    # If a custom slug is already present, never overwrite it server-side.
    if not (obj.slug or "").strip():
        obj.slug = slugify((obj.keyword or obj.name or "")[:220])
    else:
        obj.slug = slugify((obj.slug or "")[:220])
    obj.seo_status = obj.state  # legacy field kept synchronized for compatibility.
    return obj


@transaction.atomic
def ensure_web_production_structure(*, sheet, main_page_target, county_target, services_per_county_target, cities_per_county_target=0, user):
    """Adds missing rows only; existing information is never deleted.

    Hierarchy: main pages -> county -> services -> cities. Cities belong to a
    county (not a specific service), matching the production-sheet workflow.
    """
    sheet.main_page_target = main_page_target
    sheet.county_target = county_target
    sheet.services_per_county_target = services_per_county_target
    sheet.cities_per_county_target = cities_per_county_target
    sheet.header_structure = sheet.header_structure or DEFAULT_HEADER
    sheet.updated_by = user
    sheet.save(update_fields=[
        "main_page_target", "county_target", "services_per_county_target",
        "cities_per_county_target", "header_structure", "updated_by", "updated_at",
    ])

    existing_pages = list(sheet.pages.filter(page_type=WebProductionPage.PageType.PRINCIPAL).order_by("order", "id"))
    for index in range(len(existing_pages), main_page_target):
        name = DEFAULT_MAIN_PAGES[index] if index < len(DEFAULT_MAIN_PAGES) else f"Página principal {index + 1}"
        obj = WebProductionPage(
            sheet=sheet,
            page_type=WebProductionPage.PageType.PRINCIPAL,
            name=name,
            order=index + 1,
            updated_by=user,
        )
        apply_seo_automation(obj)
        obj.save()

    existing_counties = list(sheet.counties.order_by("order", "id"))
    for index in range(len(existing_counties), county_target):
        county = WebProductionCounty(
            sheet=sheet,
            name=f"Condado {index + 1}",
            order=index + 1,
            updated_by=user,
        )
        apply_seo_automation(county)
        county.save()
        existing_counties.append(county)

    for county in existing_counties:
        current_services = list(county.services.order_by("order", "id"))
        for index in range(len(current_services), services_per_county_target):
            obj = WebProductionCountyService(
                county=county,
                name=f"Servicio {index + 1} · {county.name}",
                order=index + 1,
                updated_by=user,
            )
            apply_seo_automation(obj)
            obj.save()

        current_cities = list(county.cities.order_by("order", "id"))
        for index in range(len(current_cities), cities_per_county_target):
            city = WebProductionCity(
                sheet=sheet,
                county=county,
                name=f"Ciudad {index + 1}",
                order=index + 1,
                updated_by=user,
            )
            apply_seo_automation(city)
            city.save()

    log_activity(
        user,
        "development",
        "production_structure",
        sheet,
        description=(
            f"Estructura: {main_page_target} páginas, {county_target} condados, "
            f"{services_per_county_target} servicios/condado, {cities_per_county_target} ciudades/condado"
        ),
    )
    return sheet

