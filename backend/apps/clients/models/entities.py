from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel
from .choices import ClientStatus, ClientType


class Client(TimestampedModel):
    client_code = models.CharField(max_length=20, unique=True, blank=True)
    client_type = models.CharField(max_length=20, choices=ClientType.choices, default=ClientType.COMPANY)
    first_name = models.CharField(max_length=100, blank=True, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Apellido")
    identity_document = models.CharField(max_length=80, blank=True, verbose_name="ID / identificación")
    business_name = models.CharField(max_length=180, verbose_name="Nombre de la empresa")
    contact_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True, verbose_name="Número de teléfono")
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=140, blank=True, verbose_name="Categoría / industria")
    country = models.CharField(max_length=100, blank=True)
    state_region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=ClientStatus.choices, default=ClientStatus.ACTIVE)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_clients")

    class Meta:
        ordering = ["business_name"]
        indexes = [models.Index(fields=["business_name"]), models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        if not self.contact_name:
            self.contact_name = f"{self.first_name} {self.last_name}".strip()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.client_code:
            self.client_code = f"CLI-{self.pk:05d}"
            type(self).objects.filter(pk=self.pk).update(client_code=self.client_code)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.contact_name

    def __str__(self):
        return f"{self.client_code or 'CLI'} · {self.business_name}"
