from django.db.models import Q

from apps.plans.models.choices import PlanDepartment, ServiceType
from .models import Project


ROLE_AREA_MAP = {
    "design": "design",
    "marketing": "marketing",
    "developer": "development",
}

# Un proyecto web necesita pasar por las tres fichas centrales aunque el cliente
# haya comprado únicamente el producto web. Esto evita que el proyecto desaparezca
# de Diseño o Marketing por no haber seleccionado un plan adicional de esas áreas.
WEB_WORKFLOW_SERVICE_TYPES = {
    ServiceType.WEBSITE,
    ServiceType.LANDING_PAGE,
    ServiceType.ECOMMERCE,
    ServiceType.WEBSITE_MAINTENANCE,
    ServiceType.SEO,
}

DESIGN_SERVICE_TYPES = {
    ServiceType.SOCIAL_MEDIA,
    ServiceType.JACKETS,
    ServiceType.CAPS,
    ServiceType.BRANDING,
    ServiceType.GRAPHIC_DESIGN,
    ServiceType.OTHER_DESIGN,
}

MARKETING_SERVICE_TYPES = {
    ServiceType.MARKETING,
    ServiceType.GOOGLE_GUARANTEE,
    ServiceType.GOOGLE_SEARCH_CONSOLE,
    ServiceType.GOOGLE_ADS,
    ServiceType.GOOGLE_LSA,
    ServiceType.META_ADS,
    ServiceType.GOOGLE_BUSINESS,
    ServiceType.OTHER_MARKETING,
}

DEVELOPMENT_SERVICE_TYPES = {
    ServiceType.WEBSITE,
    ServiceType.LANDING_PAGE,
    ServiceType.ECOMMERCE,
    ServiceType.WEBSITE_MAINTENANCE,
    ServiceType.SEO,
    ServiceType.SOFTWARE,
    ServiceType.OTHER_WEB,
}


def area_filter(area):
    """Filtro único para decidir qué proyectos pertenecen a cada ficha.

    Reglas:
    - Lo contratado manda.
    - Los proyectos web alimentan Diseño + Marketing + Desarrollo porque las tres
      fichas forman parte del levantamiento/producción del sitio.
    - project_type sirve como respaldo cuando un proyecto viejo todavía no tiene
      ProjectPlanAssignment.
    - Las asignaciones históricas se mantienen como compatibilidad.
    """
    if area == "design":
        return (
            Q(contracted_plans__plan__department=PlanDepartment.DESIGN, contracted_plans__is_active=True)
            | Q(contracted_plans__plan__service_type__in=WEB_WORKFLOW_SERVICE_TYPES, contracted_plans__is_active=True)
            # Compatibilidad con proyectos antiguos que todavía usan purchased_plan.
            | Q(purchased_plan__is_active=True, purchased_plan__plan__department=PlanDepartment.DESIGN)
            | Q(purchased_plan__is_active=True, purchased_plan__plan__service_type__in=WEB_WORKFLOW_SERVICE_TYPES)
            | Q(project_type__in=["website", "branding", "social_media"])
            | Q(assignments__area="design")
        )
    if area == "marketing":
        return (
            Q(contracted_plans__plan__department=PlanDepartment.MARKETING, contracted_plans__is_active=True)
            | Q(contracted_plans__plan__service_type__in=WEB_WORKFLOW_SERVICE_TYPES, contracted_plans__is_active=True)
            | Q(purchased_plan__is_active=True, purchased_plan__plan__department=PlanDepartment.MARKETING)
            | Q(purchased_plan__is_active=True, purchased_plan__plan__service_type__in=WEB_WORKFLOW_SERVICE_TYPES)
            | Q(project_type__in=["website", "seo"])
            | Q(assignments__area="marketing")
        )
    if area == "development":
        return (
            Q(contracted_plans__plan__department=PlanDepartment.DEVELOPMENT, contracted_plans__is_active=True)
            | Q(contracted_plans__plan__service_type__in=DEVELOPMENT_SERVICE_TYPES, contracted_plans__is_active=True)
            | Q(purchased_plan__is_active=True, purchased_plan__plan__department=PlanDepartment.DEVELOPMENT)
            | Q(purchased_plan__is_active=True, purchased_plan__plan__service_type__in=DEVELOPMENT_SERVICE_TYPES)
            | Q(project_type__in=["website", "software", "seo"])
            | Q(assignments__area="development")
        )
    return Q(pk__in=[])


def projects_for_area(area):
    return (
        Project.objects
        .select_related("client", "purchased_plan__plan")
        .prefetch_related("assignments__user", "contracted_plans__plan", "contracted_plans__subscription")
        .filter(area_filter(area))
        .distinct()
    )


def project_belongs_to_area(project, area):
    """Versión por instancia de area_filter, usada por permisos y sincronización."""
    active_plans = list(project.contracted_plans.select_related("plan").filter(is_active=True))
    departments = {item.plan.department for item in active_plans}
    service_types = {item.plan.service_type for item in active_plans}
    # Algunos registros previos a ProjectPlanAssignment conservan purchased_plan.
    if project.purchased_plan_id and project.purchased_plan.is_active:
        departments.add(project.purchased_plan.plan.department)
        service_types.add(project.purchased_plan.plan.service_type)
    legacy_areas = set(project.assignments.values_list("area", flat=True))

    if area == "design":
        return (
            PlanDepartment.DESIGN in departments
            or bool(service_types & WEB_WORKFLOW_SERVICE_TYPES)
            or project.project_type in {"website", "branding", "social_media"}
            or "design" in legacy_areas
        )
    if area == "marketing":
        return (
            PlanDepartment.MARKETING in departments
            or bool(service_types & WEB_WORKFLOW_SERVICE_TYPES)
            or project.project_type in {"website", "seo"}
            or "marketing" in legacy_areas
        )
    if area == "development":
        return (
            PlanDepartment.DEVELOPMENT in departments
            or bool(service_types & DEVELOPMENT_SERVICE_TYPES)
            or project.project_type in {"website", "software", "seo"}
            or "development" in legacy_areas
        )
    return False


def project_area_flags(project):
    return {
        "design": project_belongs_to_area(project, "design"),
        "marketing": project_belongs_to_area(project, "marketing"),
        "development": project_belongs_to_area(project, "development"),
    }


def visible_projects_for_user(user):
    qs = Project.objects.select_related("client", "purchased_plan__plan").prefetch_related(
        "assignments__user", "contracted_plans__plan", "contracted_plans__subscription"
    )
    if user.is_manager or user.role == "administration":
        return qs

    area = ROLE_AREA_MAP.get(user.role)
    if area:
        return qs.filter(area_filter(area)).distinct()
    return qs.none()


def can_access_project(user, project):
    if user.is_manager or user.role == "administration":
        return True

    area = ROLE_AREA_MAP.get(user.role)
    if not area:
        return False
    return project_belongs_to_area(project, area)
