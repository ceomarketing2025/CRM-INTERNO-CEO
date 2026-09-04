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


class EmailAccountMode(models.TextChoices):
    EXISTING = "existing", "Ya existe"
    CREATE = "create", "Lo crea Marketing"
    PENDING = "pending", "Pendiente de definir"


class BusinessProfileStatus(models.TextChoices):
    NOT_STARTED = "not_started", "No iniciado"
    VERIFICATION = "verification", "En verificación"
    APPROVED = "approved", "Aprobado"
    DENIED = "denied", "Desaprobado"


class BusinessProfilePresence(models.TextChoices):
    EXISTING = "existing", "Ya tiene perfil"
    CREATE = "create", "Crear perfil"
    NO = "no", "No tiene perfil"


class FollowUpMode(models.TextChoices):
    NONE = "none", "Sin recordatorio"
    WEEKLY = "weekly", "Semanal"
    CUSTOM = "custom", "Personalizado"


class ChecklistArea(models.TextChoices):
    INTAKE = "intake", "Información inicial / reunión"
    GOOGLE_PROFILE = "google_profile", "Google Business Profile"
    GOOGLE_LSA = "google_lsa", "Google LSA"
    DIGITAL_ADS = "digital_ads", "Publicidad digital"
    META_ADS = "meta_ads", "Meta Ads"
    GOOGLE_ADS = "google_ads", "Google Ads"
    TIKTOK_ADS = "tiktok_ads", "TikTok Ads"
    TRADITIONAL = "traditional", "Publicidad tradicional"
    SOCIAL_MEDIA = "social_media", "Social Media"


class CampaignPlatform(models.TextChoices):
    META = "meta", "Meta Ads"
    GOOGLE = "google", "Google Ads"
    TIKTOK = "tiktok", "TikTok Ads"
    TRADITIONAL = "traditional", "Publicidad tradicional"


class CampaignStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    MANAGER_REVIEW = "manager_review", "Esperando validación"
    CHANGES_REQUESTED = "changes_requested", "Correcciones requeridas"
    APPROVED = "approved", "Aprobada"
    SCHEDULED = "scheduled", "Programada"
    LAUNCHED = "launched", "Lanzada"
    PAUSED = "paused", "Pausada"
    COMPLETED = "completed", "Finalizada"


class AdvertisingPlatform(models.TextChoices):
    META = "meta", "Meta Ads"
    GOOGLE = "google", "Google Ads"
    TIKTOK = "tiktok", "TikTok Ads"
    TRADITIONAL = "traditional", "Publicidad tradicional"
