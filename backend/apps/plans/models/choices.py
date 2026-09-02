from django.db import models
class ServiceType(models.TextChoices):
    WEBSITE = "website", "Página web"
    SOFTWARE = "software", "Software"
    SOCIAL_MEDIA = "social_media", "Social Media"
    SEO = "seo", "SEO"
    BRANDING = "branding", "Branding"
    OTHER = "other", "Otro"
class BillingCycle(models.TextChoices):
    ONE_TIME = "one_time", "Pago único"
    MONTHLY = "monthly", "Mensual"
    YEARLY = "yearly", "Anual"
    CUSTOM = "custom", "Personalizado"
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
