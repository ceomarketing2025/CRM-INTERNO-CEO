from django.db import models


class ProjectType(models.TextChoices):
    WEBSITE = "website", "Página web"
    SOFTWARE = "software", "Software"
    SOCIAL_MEDIA = "social_media", "Social Media"
    SEO = "seo", "SEO"
    BRANDING = "branding", "Branding"
    OTHER = "other", "Otro"


class ProjectStatus(models.TextChoices):
    ACTIVE = "active", "Activo"
    PAUSED = "paused", "Pausado"
    COMPLETED = "completed", "Completado"
    CANCELLED = "cancelled", "Cancelado"
    # Valores V2 conservados para no romper datos existentes al actualizar.
    ADMINISTRATION = "administration", "Registro administrativo (V2)"
    DESIGN_INTAKE = "design_intake", "Diseño (V2)"
    DEVELOPMENT_INTAKE = "development_intake", "Desarrollo (V2)"
    INFORMATION_READY = "information_ready", "Información lista (V2)"
    IN_DEVELOPMENT = "in_development", "En desarrollo (V2)"
    REVIEW = "review", "Revisión (V2)"
    DELIVERED = "delivered", "Entregado (V2)"


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
