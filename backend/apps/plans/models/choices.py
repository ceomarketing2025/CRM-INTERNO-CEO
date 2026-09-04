from django.db import models


class ServiceType(models.TextChoices):
    # Diseño
    SOCIAL_MEDIA = "social_media", "Social Media"
    JACKETS = "jackets", "Chaquetas"
    CAPS = "caps", "Gorras"
    BRANDING = "branding", "Branding"
    GRAPHIC_DESIGN = "graphic_design", "Diseño gráfico"
    OTHER_DESIGN = "other_design", "Otro de Diseño"

    # Sitios web / Desarrollo
    WEBSITE = "website", "Sitio web"
    LANDING_PAGE = "landing_page", "Landing page"
    ECOMMERCE = "ecommerce", "E-commerce"
    WEBSITE_MAINTENANCE = "website_maintenance", "Mantenimiento web"
    SEO = "seo", "SEO web"
    SOFTWARE = "software", "Software"
    OTHER_WEB = "other_web", "Otro de Sitios web"

    # Marketing
    MARKETING = "marketing", "Plan de marketing"
    GOOGLE_GUARANTEE = "google_guarantee", "Google Guarantee"
    GOOGLE_SEARCH_CONSOLE = "google_search_console", "Google Search Console"
    GOOGLE_ADS = "google_ads", "Google Ads"
    GOOGLE_LSA = "google_lsa", "Google LSA"
    META_ADS = "meta_ads", "Meta Ads"
    GOOGLE_BUSINESS = "google_business", "Google Business Profile"
    OTHER_MARKETING = "other_marketing", "Otro de Marketing"

    # Administración
    DOMAIN_HOST = "domain_host", "Dominio y Host"
    CREDENTIALS = "credentials", "Credenciales"
    OTHER_ADMIN = "other_admin", "Otro de Administración"

    # Compatibilidad histórica
    OTHER = "other", "Otro"


class PlanDepartment(models.TextChoices):
    ADMINISTRATION = "administration", "Administración"
    DESIGN = "design", "Diseño"
    MARKETING = "marketing", "Marketing"
    DEVELOPMENT = "developer", "Sitios web / Desarrollo"


DEPARTMENT_SERVICE_TYPES = {
    PlanDepartment.ADMINISTRATION: [
        ServiceType.DOMAIN_HOST,
        ServiceType.CREDENTIALS,
        ServiceType.OTHER_ADMIN,
    ],
    PlanDepartment.DESIGN: [
        ServiceType.SOCIAL_MEDIA,
        ServiceType.JACKETS,
        ServiceType.CAPS,
        ServiceType.BRANDING,
        ServiceType.GRAPHIC_DESIGN,
        ServiceType.OTHER_DESIGN,
    ],
    PlanDepartment.MARKETING: [
        ServiceType.MARKETING,
        ServiceType.GOOGLE_GUARANTEE,
        ServiceType.GOOGLE_SEARCH_CONSOLE,
        ServiceType.GOOGLE_ADS,
        ServiceType.GOOGLE_LSA,
        ServiceType.META_ADS,
        ServiceType.GOOGLE_BUSINESS,
        ServiceType.OTHER_MARKETING,
    ],
    PlanDepartment.DEVELOPMENT: [
        ServiceType.WEBSITE,
        ServiceType.LANDING_PAGE,
        ServiceType.ECOMMERCE,
        ServiceType.WEBSITE_MAINTENANCE,
        ServiceType.SEO,
        ServiceType.SOFTWARE,
        ServiceType.OTHER_WEB,
    ],
}


def service_type_choices_for_department(department):
    allowed = DEPARTMENT_SERVICE_TYPES.get(department, [])
    label_map = dict(ServiceType.choices)
    return [(value, label_map[value]) for value in allowed]


class BillingCycle(models.TextChoices):
    ONE_TIME = "one_time", "Pago único"
    MONTHLY = "monthly", "Mensual"
    YEARLY = "yearly", "Anual"
    CUSTOM = "custom", "Personalizado"


class RenewalFrequency(models.TextChoices):
    NONE = "none", "Sin renovación"
    WEEKLY = "weekly", "Cada semana"
    BIWEEKLY = "biweekly", "Cada 15 días"
    MONTHLY = "monthly", "Cada mes"
    EVERY_MONDAY = "every_monday", "Todos los lunes"


class ClientPlanStatus(models.TextChoices):
    QUOTED = "quoted", "Cotizado"
    PURCHASED = "purchased", "Comprado"
    ACTIVE = "active", "Activo"
    PAUSED = "paused", "Pausado"
    COMPLETED = "completed", "Completado"
    CANCELLED = "cancelled", "Cancelado"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    PARTIAL = "partial", "Parcial"
    PAID = "paid", "Pagado"
