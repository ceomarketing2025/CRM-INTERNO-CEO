from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel


class CompleteStatus(models.TextChoices):
    COMPLETE = "complete", "Completo"
    INCOMPLETE = "incomplete", "Incompleto"


class GeneralServiceType(models.TextChoices):
    DOMAIN_HOST = "domain_host", "Dominio y Host"
    DOMAIN = "domain", "Solo dominio"
    HOST = "host", "Solo host"


class Provider(models.TextChoices):
    GODADDY = "godaddy", "GoDaddy"
    NAMECHEAP = "namecheap", "Namecheap"
    HOSTINGER = "hostinger", "Hostinger"
    SITEGROUND = "siteground", "SiteGround"
    GOOGLE = "google", "Google"
    META = "meta", "Meta"
    YOUTUBE = "youtube", "YouTube"
    OTHER = "other", "Other"


class GeneralPaymentStatus(models.TextChoices):
    CEO_PAID = "ceo_paid", "Pagado por CEO"
    PENDING = "pending", "Pendiente"
    REIMBURSEMENT = "reimbursement", "Pendiente reembolso"
    PAID_OTHER = "paid_other", "Pagado por tercero"


class GeneralManagementRecord(TimestampedModel):
    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name="E")
    date = models.DateField(verbose_name="Fecha")
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.SET_NULL, related_name="general_management_records")
    client_text = models.CharField(max_length=180, blank=True, verbose_name="Cliente libre")
    detail_name = models.CharField(max_length=200, blank=True, verbose_name="Nombre / Detalle")
    service_type = models.CharField(max_length=30, choices=GeneralServiceType.choices, verbose_name="Tipo Servicio")
    provider = models.CharField(max_length=30, choices=Provider.choices, verbose_name="Proveedor")
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Costo")
    currency = models.CharField(max_length=8, default="USD", verbose_name="Moneda")
    status = models.CharField(max_length=30, choices=GeneralPaymentStatus.choices, default=GeneralPaymentStatus.CEO_PAID, verbose_name="Estado")
    receipt_drive_url = models.URLField(blank=True, verbose_name="Link Recibo Drive")
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="general_management_records")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_general_management_records")

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["service_type"]), models.Index(fields=["provider"])]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.code:
            self.code = f"G-{self.pk:04d}"
            type(self).objects.filter(pk=self.pk).update(code=self.code)

    @property
    def month_name(self):
        months = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return months[self.date.month] if self.date else ""

    @property
    def client_label(self):
        return self.client.business_name if self.client else (self.client_text or "—")

    def __str__(self):
        return f"{self.code or 'G'} · {self.client_label}"


class CredentialPurchase(TimestampedModel):
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="credential_purchases")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="credential_purchases")
    credential_name = models.CharField(max_length=180, verbose_name="Credencial / recurso")
    provider = models.CharField(max_length=30, choices=Provider.choices, default=Provider.GOOGLE)
    purchase_date = models.DateField()
    renewal_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="USD")
    account_email = models.EmailField(blank=True, help_text="Correo/usuario de referencia. No se guardan contraseñas.")
    secure_reference_url = models.URLField(blank=True, help_text="Link seguro/Drive donde el equipo autorizado administra el acceso.")
    receipt_drive_url = models.URLField(blank=True)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_credential_purchases")

    class Meta:
        ordering = ["renewal_date", "-purchase_date"]

    def save(self, *args, **kwargs):
        if self.purchase_date and not self.renewal_date:
            self.renewal_date = self.purchase_date + relativedelta(years=1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client.business_name} · {self.credential_name}"


class ProductionStatus(models.TextChoices):
    FINISHED = "finished", "terminado"
    DELIVERED = "delivered", "entregado"
    PENDING_PAYMENT = "pending_payment", "pendiente pago"
    PENDING_WEB = "pending_web", "pendiente web"
    START = "start", "iniciar"


class DesignProductionStatus(models.TextChoices):
    COMPLETE = "complete", "Completo"
    INCOMPLETE = "incomplete", "Incompleto"
    NO_DESIGN = "no_design", "No diseño"


class ProductionRecord(TimestampedModel):
    """Control administrativo/financiero de producción existente en V3."""
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="production_records")
    reference = models.CharField(max_length=120, blank=True, verbose_name="REFERENCIA")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="production_records")
    project_site = models.CharField(max_length=240, verbose_name="Proyecto/Sitio")
    plan_start = models.DateField(null=True, blank=True, verbose_name="Inicio plan")
    design_status = models.CharField(max_length=20, choices=DesignProductionStatus.choices, default=DesignProductionStatus.INCOMPLETE, verbose_name="DISEÑO")
    tech_status = models.CharField(max_length=20, choices=CompleteStatus.choices, default=CompleteStatus.INCOMPLETE, verbose_name="ESTADO TEC")
    status = models.CharField(max_length=30, choices=ProductionStatus.choices, default=ProductionStatus.START, verbose_name="Estado")
    collaborator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="production_records", verbose_name="COLABORADOR")
    notes = models.TextField(blank=True, verbose_name="Notas")
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Costo")
    advance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Anticipo")
    website_url = models.URLField(blank=True, verbose_name="Link web final")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_production_records")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["plan_start"])]

    @property
    def pending(self):
        return max((self.cost or Decimal("0.00")) - (self.advance or Decimal("0.00")), Decimal("0.00"))

    def __str__(self):
        return f"{self.client.business_name} · {self.project_site}"


# ---------------------------------------------------------------------------
# FICHA DE PRODUCCIÓN WEB · DESARROLLO · V5
# ---------------------------------------------------------------------------

class SeoComplexity(models.TextChoices):
    SIMPLE = "S", "Simple"
    MEDIUM = "M", "Media"
    COMPLEX = "C", "Compleja"


class WebProductionSheet(TimestampedModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="web_production_sheet")
    main_page_target = models.PositiveIntegerField(default=8, verbose_name="Cantidad páginas principales")
    county_target = models.PositiveIntegerField(default=0, verbose_name="Cantidad de condados")
    services_per_county_target = models.PositiveIntegerField(default=0, verbose_name="Servicios por condado")
    cities_per_county_target = models.PositiveIntegerField(default=0, verbose_name="Ciudades por condado")
    header_structure = models.TextField(
        blank=True,
        default="Home | About | Services | Areas We Service | Gallery | Contact | Free Estimate",
        verbose_name="Estructura de header",
    )
    notes = models.TextField(blank=True, verbose_name="Notas generales de producción")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_web_production_sheets")

    class Meta:
        ordering = ["project"]

    def __str__(self):
        return f"Producción web · {self.project.project_code}"


class ProductionSeoBase(TimestampedModel):
    """Campos comunes SEO. Complejidad, puntos y slug se calculan automáticamente."""
    name = models.CharField(max_length=180, blank=True, verbose_name="Página")
    complexity = models.CharField(max_length=2, choices=SeoComplexity.choices, default=SeoComplexity.SIMPLE)
    points = models.PositiveSmallIntegerField(default=1)
    slug = models.CharField(max_length=220, blank=True)
    keyword = models.CharField(max_length=255, blank=True)
    secondary_keywords = models.TextField(blank=True, verbose_name="Palabras secundarias")
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    review_status = models.CharField(max_length=20, choices=CompleteStatus.choices, default=CompleteStatus.INCOMPLETE, verbose_name="Revisión realizada")
    seo_status = models.CharField(max_length=20, choices=CompleteStatus.choices, default=CompleteStatus.INCOMPLETE, verbose_name="SEO legacy")
    state = models.CharField(max_length=20, choices=CompleteStatus.choices, default=CompleteStatus.INCOMPLETE, verbose_name="Página lista")
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class WebProductionPage(ProductionSeoBase):
    class PageType(models.TextChoices):
        PRINCIPAL = "principal", "Principal"
        EXTRA = "extra", "Extra"

    sheet = models.ForeignKey(WebProductionSheet, on_delete=models.CASCADE, related_name="pages")
    page_type = models.CharField(max_length=20, choices=PageType.choices, default=PageType.PRINCIPAL)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name or f"Página {self.pk or ''}"


class WebProductionCounty(ProductionSeoBase):
    sheet = models.ForeignKey(WebProductionSheet, on_delete=models.CASCADE, related_name="counties")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name or f"Condado {self.pk or ''}"


class WebProductionCountyService(ProductionSeoBase):
    county = models.ForeignKey(WebProductionCounty, on_delete=models.CASCADE, related_name="services")
    service_name = models.CharField(max_length=180, blank=True, verbose_name="Servicio base")
    is_global = models.BooleanField(default=False, verbose_name="Servicio global")

    class Meta:
        ordering = ["order", "id"]

    @property
    def sheet(self):
        return self.county.sheet

    def __str__(self):
        return f"{self.county} · {self.name or self.service_name or 'Servicio'}"


class WebProductionCity(ProductionSeoBase):
    sheet = models.ForeignKey(WebProductionSheet, on_delete=models.CASCADE, related_name="cities")
    county = models.ForeignKey(WebProductionCounty, null=True, blank=True, on_delete=models.SET_NULL, related_name="cities")

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "Ciudades de producción web"

    def __str__(self):
        return self.name or f"Ciudad {self.pk or ''}"
