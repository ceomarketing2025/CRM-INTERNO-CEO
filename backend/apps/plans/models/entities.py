from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimestampedModel
from .choices import (
    BillingCycle,
    ClientPlanStatus,
    DEPARTMENT_SERVICE_TYPES,
    PaymentStatus,
    PlanDepartment,
    RenewalFrequency,
    ServiceType,
)


class ServicePlan(TimestampedModel):
    """Catálogo de productos/planes por área.

    El plan define el producto. Renovación, próximo pago y redes pertenecen a la
    suscripción/asignación del cliente, nunca al catálogo.
    """

    name = models.CharField(max_length=160, verbose_name="Nombre del plan")
    code = models.SlugField(max_length=80, unique=True, verbose_name="Código interno")
    service_type = models.CharField(max_length=40, choices=ServiceType.choices, verbose_name="Categoría")
    department = models.CharField(
        max_length=24,
        choices=PlanDepartment.choices,
        default=PlanDepartment.ADMINISTRATION,
        verbose_name="Área responsable",
    )
    description = models.TextField(blank=True, verbose_name="Notas / alcance")
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Costo")
    currency = models.CharField(max_length=8, default="USD", verbose_name="Moneda")
    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.ONE_TIME,
        verbose_name="Facturación",
    )

    # Social Media: cantidad por ciclo de la suscripción.
    weekly_posts = models.PositiveSmallIntegerField(default=0, verbose_name="Cantidad de posts")
    weekly_videos = models.PositiveSmallIntegerField(default=0, verbose_name="Cantidad de videos")

    # Sitios web: alcance básico del producto, sin mezclarlo con la ficha técnica.
    website_pages = models.PositiveSmallIntegerField(default=0, verbose_name="Cantidad de páginas")
    branding_pages = models.PositiveSmallIntegerField(default=0, verbose_name="Cantidad de branding pages")
    scope_range = models.CharField(max_length=120, blank=True, verbose_name="Rango / alcance")

    rules = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_service_plans",
    )

    class Meta:
        ordering = ["department", "service_type", "name"]

    def clean(self):
        super().clean()
        allowed = DEPARTMENT_SERVICE_TYPES.get(self.department, [])
        if allowed and self.service_type not in allowed:
            raise ValidationError({"service_type": "La categoría seleccionada no pertenece a esta área."})

    @property
    def content_goal_label(self):
        if self.service_type != ServiceType.SOCIAL_MEDIA:
            return ""
        parts = []
        if self.weekly_posts:
            parts.append(f"{self.weekly_posts} posts")
        if self.weekly_videos:
            parts.append(f"{self.weekly_videos} videos")
        return " + ".join(parts) or "Sin entregables definidos"

    @property
    def weekly_content_label(self):
        return self.content_goal_label

    @property
    def web_scope_label(self):
        parts = []
        if self.website_pages:
            parts.append(f"{self.website_pages} páginas")
        if self.branding_pages:
            parts.append(f"{self.branding_pages} branding")
        if self.scope_range:
            parts.append(self.scope_range)
        return " · ".join(parts)

    @property
    def is_subscription_product(self):
        return self.service_type == ServiceType.SOCIAL_MEDIA or self.billing_cycle in {
            BillingCycle.MONTHLY,
            BillingCycle.YEARLY,
            BillingCycle.CUSTOM,
        }

    def __str__(self):
        return self.name


class ClientPlan(TimestampedModel):
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="purchased_plans")
    plan = models.ForeignKey(ServicePlan, on_delete=models.PROTECT, related_name="purchases")
    assigned_design_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_social_media_client_plans",
        verbose_name="Responsable de Diseño",
    )
    agreed_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Precio acordado")
    currency = models.CharField(max_length=8, default="USD", verbose_name="Moneda")
    purchase_date = models.DateField(null=True, blank=True, verbose_name="Fecha de compra")
    start_date = models.DateField(null=True, blank=True, verbose_name="Fecha de inicio")
    renewal_frequency = models.CharField(
        max_length=24,
        choices=RenewalFrequency.choices,
        default=RenewalFrequency.MONTHLY,
        verbose_name="Renovación",
    )
    renewal_date = models.DateField(null=True, blank=True, verbose_name="Próximo pago / renovación")
    end_date = models.DateField(null=True, blank=True, verbose_name="Fin / vencimiento")
    status = models.CharField(max_length=20, choices=ClientPlanStatus.choices, default=ClientPlanStatus.ACTIVE)
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    social_networks = models.JSONField(default=list, blank=True, verbose_name="Redes sociales")
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, verbose_name="Estado de pago")
    paid_until = models.DateField(null=True, blank=True, verbose_name="Pagado hasta")
    notes = models.TextField(blank=True, verbose_name="Notas internas")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_plan_purchases",
    )

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.assigned_design_user and getattr(self.assigned_design_user, "role", None) not in {"design", "manager"}:
            raise ValidationError({"assigned_design_user": "Selecciona un usuario de Diseño o Gerencia."})
        if self.plan_id and self.plan.service_type != ServiceType.SOCIAL_MEDIA:
            self.assigned_design_user = None
            self.social_networks = []

    @property
    def is_social_media(self):
        return bool(self.plan_id and self.plan.service_type == ServiceType.SOCIAL_MEDIA)

    @property
    def social_networks_label(self):
        labels = {
            "facebook": "Facebook",
            "instagram": "Instagram",
            "tiktok": "TikTok",
            "youtube": "YouTube",
            "x": "X / Twitter",
            "linkedin": "LinkedIn",
            "google_business": "Google Business",
            "pinterest": "Pinterest",
        }
        return ", ".join(labels.get(item, item) for item in (self.social_networks or [])) or "Sin redes definidas"

    def __str__(self):
        return f"{self.client.business_name} · {self.plan.name}"
