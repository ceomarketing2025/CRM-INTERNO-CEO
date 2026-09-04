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


class DomainOperationType(models.TextChoices):
    NEW = "new", "Nuevo dominio"
    EXISTING = "existing", "Dominio existente"
    MIGRATION = "migration", "Migración"


class DomainRecordStatus(models.TextChoices):
    PENDING_PURCHASE = "pending_purchase", "Pendiente de compra"
    PURCHASED = "purchased", "Comprado y registrado"
    PENDING_MIGRATION = "pending_migration", "Pendiente de migración"
    MIGRATED = "migrated", "Migrado"
    # Valores heredados para no romper registros creados antes de V11.
    LEGACY_PENDING = "pending", "Pendiente (legado)"
    LEGACY_READY = "ready", "Comprado / registrado (legado)"


class HostingProvider(models.TextChoices):
    SITEGROUND = "siteground", "SiteGround"
    HOSTINGER = "hostinger", "Hostinger"
    GODADDY = "godaddy", "GoDaddy"
    BLUEHOST = "bluehost", "Bluehost"
    OTHER = "other", "Otro"


class DomainHostingRecord(TimestampedModel):
    """Control administrativo de dominio + hosting por proyecto.

    Los importes y comprobantes quedan en Administración/Gerencia. El Resumen
    compartido solo consume el estado, dominio y proveedor, nunca costos ni
    fechas financieras.
    """

    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="domain_hosting_records")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="domain_hosting_records")
    operation_type = models.CharField(max_length=20, choices=DomainOperationType.choices, default=DomainOperationType.NEW, verbose_name="Tipo")
    domain_name = models.CharField(max_length=255, blank=True, verbose_name="Dominio")
    start_date = models.DateField(verbose_name="Fecha de inicio")
    domain_expiry_date = models.DateField(null=True, blank=True, verbose_name="Fecha de caducidad del dominio")
    domain_status = models.CharField(max_length=24, choices=DomainRecordStatus.choices, default=DomainRecordStatus.PENDING_PURCHASE, verbose_name="Estado del dominio")
    domain_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Costo del dominio")
    domain_receipt_drive_url = models.URLField(blank=True, default="", verbose_name="Recibo del dominio · Google Drive")

    server_provider = models.CharField(max_length=30, choices=HostingProvider.choices, default=HostingProvider.SITEGROUND, verbose_name="Proveedor servidor / hosting")
    server_provider_other = models.CharField(max_length=120, blank=True, verbose_name="Otro proveedor")
    server_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Costo servidor / hosting")
    server_receipt_drive_url = models.URLField(blank=True, default="", verbose_name="Recibo del hosting · Google Drive")
    currency = models.CharField(max_length=8, default="USD", verbose_name="Moneda")

    # Campo legado V10. Se conserva para no eliminar enlaces ya registrados.
    receipt_drive_url = models.URLField(blank=True, verbose_name="Recibo Drive (legado)")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_domain_hosting_records")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_domain_hosting_records")

    class Meta:
        ordering = ["-start_date", "-id"]
        indexes = [models.Index(fields=["domain_status"]), models.Index(fields=["domain_expiry_date"])]

    @property
    def provider_label(self):
        return self.server_provider_other.strip() if self.server_provider == HostingProvider.OTHER and self.server_provider_other.strip() else self.get_server_provider_display()

    @property
    def is_domain_complete(self):
        return self.domain_status in {
            DomainRecordStatus.PURCHASED,
            DomainRecordStatus.MIGRATED,
            DomainRecordStatus.LEGACY_READY,
        } or self.operation_type == DomainOperationType.EXISTING

    @property
    def project_domain_label(self):
        if self.operation_type == DomainOperationType.MIGRATION:
            if self.domain_status in {DomainRecordStatus.MIGRATED, DomainRecordStatus.LEGACY_READY, DomainRecordStatus.PURCHASED}:
                return "Migrado"
            return "Pendiente de migración"
        if self.operation_type == DomainOperationType.EXISTING:
            return "Comprado y registrado"
        mapping = {
            DomainRecordStatus.PENDING_PURCHASE: "Pendiente de compra",
            DomainRecordStatus.PURCHASED: "Comprado y registrado",
            DomainRecordStatus.LEGACY_PENDING: "Pendiente de compra",
            DomainRecordStatus.LEGACY_READY: "Comprado y registrado",
        }
        return mapping.get(self.domain_status, self.get_domain_status_display())

    @property
    def status_badge_class(self):
        return "success" if self.is_domain_complete else "warning-soft"

    @property
    def allowed_statuses(self):
        if self.operation_type == DomainOperationType.MIGRATION:
            return [DomainRecordStatus.PENDING_MIGRATION, DomainRecordStatus.MIGRATED]
        if self.operation_type == DomainOperationType.EXISTING:
            return [DomainRecordStatus.PURCHASED]
        return [DomainRecordStatus.PENDING_PURCHASE, DomainRecordStatus.PURCHASED]

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.project_id and self.client_id and self.project.client_id != self.client_id:
            errors["project"] = "El proyecto debe pertenecer al cliente seleccionado."
        if self.server_provider == HostingProvider.OTHER and not self.server_provider_other.strip():
            errors["server_provider_other"] = "Escribe el nombre del proveedor."
        if self.domain_status not in self.allowed_statuses and self.domain_status not in {DomainRecordStatus.LEGACY_PENDING, DomainRecordStatus.LEGACY_READY}:
            errors["domain_status"] = "El estado no corresponde al tipo de registro seleccionado."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Normaliza registros heredados y evita combinaciones imposibles.
        if self.operation_type == DomainOperationType.EXISTING:
            self.domain_status = DomainRecordStatus.PURCHASED
        elif self.operation_type == DomainOperationType.MIGRATION:
            if self.domain_status in {DomainRecordStatus.PURCHASED, DomainRecordStatus.LEGACY_READY}:
                self.domain_status = DomainRecordStatus.MIGRATED
            elif self.domain_status in {DomainRecordStatus.PENDING_PURCHASE, DomainRecordStatus.LEGACY_PENDING}:
                self.domain_status = DomainRecordStatus.PENDING_MIGRATION
        else:
            if self.domain_status in {DomainRecordStatus.MIGRATED, DomainRecordStatus.LEGACY_READY}:
                self.domain_status = DomainRecordStatus.PURCHASED
            elif self.domain_status in {DomainRecordStatus.PENDING_MIGRATION, DomainRecordStatus.LEGACY_PENDING}:
                self.domain_status = DomainRecordStatus.PENDING_PURCHASE

        # Si V10 tenía un único recibo, lo conservamos como recibo de hosting al editar.
        if self.receipt_drive_url and not self.server_receipt_drive_url:
            self.server_receipt_drive_url = self.receipt_drive_url
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client.business_name} · {self.domain_name or self.get_operation_type_display()}"


class CredentialType(models.TextChoices):
    # Tipos principales V11.
    GOOGLE = "google", "Google / Gmail"
    SERVER = "server", "Servidor"
    WORDPRESS = "wordpress", "WordPress"
    META = "meta", "Meta"
    YOUTUBE = "youtube", "YouTube"
    TIKTOK = "tiktok", "TikTok"
    OTHER = "other", "Otro"

    # Tipos heredados V10. Se mantienen para que los accesos ya guardados sigan
    # siendo legibles, pero no se ofrecen como categorías nuevas.
    WEBMAIL = "webmail", "Webmail / correo corporativo (legado)"
    SITEGROUND = "siteground", "SiteGround (legado)"
    GOOGLE_BUSINESS = "google_business", "Google Business (legado)"
    GOOGLE_ADS = "google_ads", "Google Ads (legado)"
    GOOGLE_LSA = "google_lsa", "Google LSA / Guarantee (legado)"
    SEARCH_CONSOLE = "search_console", "Google Search Console (legado)"
    ANALYTICS = "analytics", "Google Analytics (legado)"


class ProjectCredential(TimestampedModel):
    """Acceso por proyecto con contraseña cifrada y visibilidad controlada por Gerencia."""

    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="project_credentials")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="project_credentials")
    credential_type = models.CharField(max_length=30, choices=CredentialType.choices, verbose_name="Credencial")
    custom_name = models.CharField(max_length=120, blank=True, verbose_name="Nombre personalizado / proveedor")
    account_email = models.CharField(max_length=255, blank=True, verbose_name="Correo / usuario")
    password_encrypted = models.TextField(blank=True, editable=False)
    login_url = models.URLField(blank=True, verbose_name="URL de acceso")
    enabled = models.BooleanField(default=True, verbose_name="Habilitada")
    visible_to_team = models.BooleanField(default=False, verbose_name="Visible en resumen para las áreas")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_project_credentials")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_project_credentials")

    class Meta:
        ordering = ["client__business_name", "project__name", "credential_type", "id"]
        indexes = [models.Index(fields=["credential_type", "enabled"]), models.Index(fields=["visible_to_team"])]

    @property
    def display_name(self):
        if self.credential_type == CredentialType.OTHER and self.custom_name.strip():
            return self.custom_name.strip()
        if self.credential_type == CredentialType.SERVER and self.custom_name.strip():
            return f"Servidor · {self.custom_name.strip()}"
        return self.get_credential_type_display()

    @property
    def has_access_data(self):
        return bool(self.account_email.strip() or self.password_encrypted or self.login_url)

    def set_password(self, raw_password):
        from .crypto import encrypt_secret
        self.password_encrypted = encrypt_secret(raw_password) if raw_password else ""

    def get_password(self):
        from .crypto import decrypt_secret
        return decrypt_secret(self.password_encrypted) if self.password_encrypted else ""

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.project_id and self.client_id and self.project.client_id != self.client_id:
            errors["project"] = "El proyecto debe pertenecer al cliente seleccionado."
        if self.credential_type == CredentialType.OTHER and not self.custom_name.strip():
            errors["custom_name"] = "Escribe el nombre de la credencial."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.project.project_code} · {self.display_name}"


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
