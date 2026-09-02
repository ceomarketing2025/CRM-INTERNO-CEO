from django.db import models
class ClientType(models.TextChoices):
    COMPANY = "company", "Empresa"
    PERSON = "person", "Persona"
class ClientStatus(models.TextChoices):
    LEAD = "lead", "Prospecto"
    ACTIVE = "active", "Activo"
    INACTIVE = "inactive", "Inactivo"
