from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel
from .choices import BillingCycle, ClientPlanStatus, PaymentStatus, ServiceType

class ServicePlan(TimestampedModel):
    name = models.CharField(max_length=160)
    code = models.SlugField(max_length=80, unique=True)
    service_type = models.CharField(max_length=30, choices=ServiceType.choices)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="USD")
    billing_cycle = models.CharField(max_length=20, choices=BillingCycle.choices, default=BillingCycle.ONE_TIME)
    rules = models.JSONField(default=dict, blank=True, help_text="Límites o reglas del plan sin rigidizar el modelo.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["service_type", "name"]

    def __str__(self):
        return self.name

class ClientPlan(TimestampedModel):
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="purchased_plans")
    plan = models.ForeignKey(ServicePlan, on_delete=models.PROTECT, related_name="purchases")
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="USD")
    purchase_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ClientPlanStatus.choices, default=ClientPlanStatus.QUOTED)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_plan_purchases")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.client.business_name} · {self.plan.name}"
