"""Business logic shared by Projects and the three operational area modules."""

from .selectors import project_area_flags


def _development_template_for_project(project):
    from apps.questionnaires.models import QuestionnaireTemplate
    from apps.questionnaires.services import WEBSITE_TEMPLATE_CODE

    active_types = set(
        project.contracted_plans.filter(is_active=True).values_list("plan__service_type", flat=True)
    )

    # Website / SEO flows use the guided website technical sheet.
    if project.project_type in {"website", "seo"} or active_types.intersection(
        {"website", "landing_page", "ecommerce", "website_maintenance", "seo"}
    ):
        template = QuestionnaireTemplate.objects.filter(code=WEBSITE_TEMPLATE_CODE, is_active=True).first()
        if template:
            return template

    # Software keeps its own discovery sheet.
    if project.project_type == "software" or "software" in active_types:
        template = QuestionnaireTemplate.objects.filter(project_type="software", is_active=True).order_by("id").first()
        if template:
            return template

    # Final fallback for older/custom development plans.
    return QuestionnaireTemplate.objects.filter(project_type=project.project_type, is_active=True).order_by("id").first()


def sync_project_area_records(project, user=None):
    """Ensure every area that owns the project has its own editable sheet ready.

    This function is intentionally idempotent. It can safely run after project
    create/edit and whenever an area dashboard opens, which also repairs projects
    created with older versions of the CRM.
    """
    flags = project_area_flags(project)

    if flags["design"]:
        from apps.design.models import DesignBrief
        DesignBrief.objects.get_or_create(project=project)

    if flags["marketing"]:
        from apps.marketing.services import ensure_workspace
        ensure_workspace(project)

    if flags["development"]:
        from apps.questionnaires.models import ProjectQuestionnaire
        from apps.questionnaires.models.choices import QuestionnaireStatus

        template = _development_template_for_project(project)
        if template:
            ProjectQuestionnaire.objects.get_or_create(
                project=project,
                template=template,
                defaults={
                    "created_by": user if getattr(user, "is_authenticated", False) else None,
                    "status": QuestionnaireStatus.DRAFT,
                },
            )

    return flags
