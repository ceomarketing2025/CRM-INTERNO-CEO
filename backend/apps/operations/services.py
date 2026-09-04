from django.db import transaction
from django.utils.text import slugify
from apps.audit.services import log_activity
from apps.reminders.services import ensure_credential_renewal_reminder, ensure_launch_followups
from .models import (
    ProductionRecord,
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

