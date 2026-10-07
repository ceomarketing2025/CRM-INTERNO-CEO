from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel
from .choices import DomainStatus

class Domain(TimestampedModel):
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="domains")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="domains")
    domain_name = models.CharField(max_length=255, unique=True)
    registrar = models.CharField(max_length=120, blank=True)
    provider_url = models.URLField(blank=True)
    account_email = models.EmailField(blank=True, help_text="Correo de la cuenta. No se almacenan contraseñas en texto plano.")
    purchase_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    annual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="USD")
    auto_renew = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=DomainStatus.choices, default=DomainStatus.PLANNED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_domains")

    class Meta:
        ordering = ["domain_name"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["renewal_date"])]

    def __str__(self):
        return self.domain_name
