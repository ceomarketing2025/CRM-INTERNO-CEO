from django.db import models


class ProjectType(models.TextChoices):
    WEBSITE = "website", "Página web"
    SOFTWARE = "software", "Software"
    SOCIAL_MEDIA = "social_media", "Social Media"
    SEO = "seo", "SEO"
    BRANDING = "branding", "Branding"
    OTHER = "other", "Otro"


class ProjectStatus(models.TextChoices):
    ADMINISTRATION = "administration", "Registro administrativo"
    DESIGN_INTAKE = "design_intake", "Reunión de diseño"
    DEVELOPMENT_INTAKE = "development_intake", "Levantamiento de desarrollo"
    INFORMATION_READY = "information_ready", "Información lista"
    IN_DEVELOPMENT = "in_development", "En desarrollo"
    REVIEW = "review", "Revisión"
    DELIVERED = "delivered", "Entregado"
    PAUSED = "paused", "Pausado"
    CANCELLED = "cancelled", "Cancelado"


class Priority(models.TextChoices):
    LOW = "low", "Baja"
    MEDIUM = "medium", "Media"
    HIGH = "high", "Alta"
    URGENT = "urgent", "Urgente"


class AssignmentArea(models.TextChoices):
    GLOBAL = "global", "Global"
    ADMINISTRATION = "administration", "Administración"
    MARKETING = "marketing", "Marketing"
    DESIGN = "design", "Diseño"
    DEVELOPMENT = "development", "Desarrollo"


class AssignmentStatus(models.TextChoices):
    ASSIGNED = "assigned", "Asignado"
    ACTIVE = "active", "Activo"
    DONE = "done", "Finalizado"
