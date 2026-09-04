from django.db import models


class MarketingTaskStatus(models.TextChoices):
    TODO = "todo", "Pendiente"
    DOING = "doing", "En proceso"
    REVIEW = "review", "Revisión"
    DONE = "done", "Finalizada"


class BinaryStatus(models.TextChoices):
    INCOMPLETE = "incomplete", "Incompleto"
    COMPLETE = "complete", "Completo"


class YesNo(models.TextChoices):
    YES = "yes", "Sí"
    NO = "no", "No"


class BusinessProfileStatus(models.TextChoices):
    NOT_STARTED = "not_started", "No iniciado"
    VERIFICATION = "verification", "En verificación"
    APPROVED = "approved", "Aprobado"
    DENIED = "denied", "Desaprobado"


class BusinessProfilePresence(models.TextChoices):
    EXISTING = "existing", "Ya tiene perfil"
    CREATE = "create", "Crear perfil"
    NO = "no", "No tiene / no crear"


class ChecklistArea(models.TextChoices):
    INTAKE = "intake", "Recolección / reunión"
    GOOGLE_PROFILE = "google_profile", "Google Business Profile"
    GOOGLE_LSA = "google_lsa", "Google LSA / Guarantee"
    META_ADS = "meta_ads", "Meta Ads"
    GOOGLE_ADS = "google_ads", "Google Ads"
    SOCIAL_MEDIA = "social_media", "Social Media"


class CampaignPlatform(models.TextChoices):
    META = "meta", "Meta Ads"
    GOOGLE = "google", "Google Ads"
    TRADITIONAL = "traditional", "Pauta tradicional"


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    MANAGER_REVIEW = "manager_review", "Revisión Gerencia"
    READY = "ready", "Lista para lanzar"
    LAUNCHED = "launched", "Lanzada"
    COMPLETED = "completed", "Finalizada"
    PAUSED = "paused", "Pausada"
