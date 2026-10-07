from django.db import models
class DomainStatus(models.TextChoices):
    PLANNED = "planned", "Por registrar"
    ACTIVE = "active", "Activo"
    RENEWAL_DUE = "renewal_due", "Por renovar"
    EXPIRED = "expired", "Vencido"
    TRANSFERRED = "transferred", "Transferido"
    CANCELLED = "cancelled", "Cancelado"
