from datetime import timedelta
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from apps.core.models import TimestampedModel
from .choices import (
    AdvertisingPlatform,
    BinaryStatus,
    BusinessProfilePresence,
    BusinessProfileStatus,
    CampaignPlatform,
    CampaignStatus,
    ChecklistArea,
    EmailAccountMode,
    FollowUpMode,
    MarketingTaskStatus,
    YesNo,
)


class MarketingBrief(TimestampedModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="marketing_brief")
    objective = models.TextField(blank=True)
    target_audience = models.TextField(blank=True)
    channels = models.CharField(max_length=255, blank=True, help_text="Facebook, Instagram, TikTok, Google, etc.")
    tone = models.CharField(max_length=180, blank=True)
    content_pillars = models.TextField(blank=True)
    campaign_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Brief marketing · {self.project}"


class MarketingTask(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="marketing_tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="marketing_tasks")
    status = models.CharField(max_length=20, choices=MarketingTaskStatus.choices, default=MarketingTaskStatus.TODO)
    due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title


class MarketingWorkspace(TimestampedModel):
    """Cabecera de Marketing.

    Los campos anteriores se conservan para compatibilidad con versiones previas.
    El flujo V4 usa esta entidad como intake/reunión y distribuye GBP, LSA y Ads
    en vistas especializadas sin almacenar contraseñas.
    """

    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="marketing_workspace")

    # Información inicial / reunión
    intake_status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Información inicial")
    meeting_summary = models.TextField(blank=True, verbose_name="Datos recolectados de la reunión")
    owner_name = models.CharField(max_length=180, blank=True, verbose_name="Nombre del dueño")
    legal_business_name = models.CharField(max_length=220, blank=True, verbose_name="Nombre legal de la empresa")
    founding_date = models.DateField(null=True, blank=True, verbose_name="Fecha de fundación")
    social_links = models.TextField(blank=True, verbose_name="Redes sociales")
    company_description = models.TextField(blank=True, verbose_name="Descripción de la empresa")
    business_hours = models.TextField(blank=True, verbose_name="Horario")
    services = models.TextField(blank=True, verbose_name="Servicios")
    service_areas = models.TextField(blank=True, verbose_name="Áreas")
    contact_email = models.EmailField(blank=True, verbose_name="Correo electrónico")
    email_account_mode = models.CharField(max_length=20, choices=EmailAccountMode.choices, default=EmailAccountMode.PENDING, verbose_name="Estado del correo")
    gmail_email = models.EmailField(blank=True, verbose_name="Gmail creado")
    lsa_documents_available = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="¿Tiene documentos para LSA?")
    notes = models.TextField(blank=True)

    # Campos históricos que continúan disponibles para no romper datos existentes.
    webmail_has = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="¿Cuenta con webmail?")
    webmail_email = models.EmailField(blank=True, verbose_name="Webmail / correo corporativo")
    webmail_secure_reference_url = models.URLField(blank=True, verbose_name="Referencia segura de credenciales", help_text="Usa un link seguro/Drive; no guardes contraseñas en texto plano.")
    business_profile_mode = models.CharField(max_length=20, choices=BusinessProfilePresence.choices, blank=True, default="", verbose_name="Google Business: situación")
    business_profile_status = models.CharField(max_length=30, choices=BusinessProfileStatus.choices, default=BusinessProfileStatus.NOT_STARTED, verbose_name="Verificación Google Business")
    business_profile_link = models.URLField(blank=True, verbose_name="Link Google Business")
    business_profile_id = models.CharField(max_length=180, blank=True, verbose_name="ID Google Business")
    business_profile_social_links = models.TextField(blank=True, verbose_name="Links de redes sociales del perfil")
    business_profile_notes = models.TextField(blank=True, verbose_name="Notas Google Business")
    business_profile_reviews_status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Reseñas")
    business_profile_products_status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Productos")
    business_profile_completion_status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Porcentaje del perfil")
    business_profile_website_status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Website en Google Business")
    business_profile_last_post = models.DateField(null=True, blank=True, verbose_name="Último post en Google Business")
    business_profile_photos_status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Fotos")
    website_has = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="¿Tiene sitio web?")
    website_url = models.URLField(blank=True, verbose_name="Sitio web actual")
    review_link = models.URLField(blank=True, verbose_name="Link para reviews")
    review_message = models.TextField(blank=True, verbose_name="Mensaje para customers")
    documents_available = models.CharField(max_length=10, choices=YesNo.choices, default=YesNo.NO, verbose_name="¿Tiene documentos?")
    credentials_group_requested = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Credenciales pedidas por grupo")
    pdf_documents_requested = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Documentos PDF solicitados")
    google_ads_verification = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    google_lsa_verification = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    google_guarantee_launched = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)

    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="marketing_workspaces")
    shared_info_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_shared_marketing_profiles", verbose_name="Última edición compartida por")
    shared_info_updated_at = models.DateTimeField(null=True, blank=True, verbose_name="Última edición compartida")

    @property
    def intake_ready(self):
        return self.intake_status == BinaryStatus.COMPLETE

    def __str__(self):
        return f"Marketing · {self.project.client.business_name}"


class MarketingChecklistItem(TimestampedModel):
    workspace = models.ForeignKey(MarketingWorkspace, on_delete=models.CASCADE, related_name="checklist_items")
    area = models.CharField(max_length=30, choices=ChecklistArea.choices)
    key = models.SlugField(max_length=100)
    label = models.CharField(max_length=240)
    status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    yes_no = models.CharField(max_length=10, choices=YesNo.choices, blank=True)
    detail = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True, help_text="Permite ocultar checks de versiones anteriores sin borrar historial.")

    class Meta:
        ordering = ["area", "order", "id"]
        constraints = [models.UniqueConstraint(fields=["workspace", "key"], name="unique_marketing_workspace_check_key")]

    def save(self, *args, **kwargs):
        if self.status == BinaryStatus.COMPLETE and not self.completed_at:
            self.completed_at = timezone.now()
        if self.status != BinaryStatus.COMPLETE:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class MarketingDocument(TimestampedModel):
    workspace = models.ForeignKey(MarketingWorkspace, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=180)
    document_type = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to="marketing_documents/", null=True, blank=True, validators=[FileExtensionValidator(["pdf"])])
    drive_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploaded_marketing_documents")

    def __str__(self):
        return self.title


class GoogleLSAWorkspace(TimestampedModel):
    workspace = models.OneToOneField(MarketingWorkspace, on_delete=models.CASCADE, related_name="lsa_workspace")
    documents_drive_url = models.URLField(blank=True, verbose_name="Drive de documentos")
    driver_license_ready = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="Licencia de conducir")
    founding_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Año de fundación")
    verification_status = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Verificación LSA")
    weekly_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], verbose_name="Costo por semana")
    leads_last_7_days = models.PositiveIntegerField(null=True, blank=True, verbose_name="Leads últimos 7 días")
    last_lead_date = models.DateField(null=True, blank=True, verbose_name="Fecha del último lead")
    has_social_media = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="¿Tiene Social Media?")
    followup_mode = models.CharField(max_length=20, choices=FollowUpMode.choices, default=FollowUpMode.WEEKLY, verbose_name="Recordatorio de revisión")
    followup_start_date = models.DateField(null=True, blank=True, verbose_name="Primera revisión")
    custom_followup_date = models.DateField(null=True, blank=True, verbose_name="Fecha personalizada")
    photo_reminder_enabled = models.CharField(
        max_length=10, choices=YesNo.choices, default=YesNo.YES,
        verbose_name="¿Activar recordatorio para subir fotos cada 15 días?",
    )
    photo_reminder_start_date = models.DateField(
        null=True, blank=True, verbose_name="Primera fecha para subir fotos",
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Google LSA · {self.workspace.project.client.business_name}"


class AdvertisingAccount(TimestampedModel):
    workspace = models.ForeignKey(MarketingWorkspace, on_delete=models.CASCADE, related_name="advertising_accounts")
    platform = models.CharField(max_length=20, choices=AdvertisingPlatform.choices)
    enabled = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="¿Se trabajará esta plataforma?")
    profile_url = models.URLField(blank=True, verbose_name="Link de la plataforma")
    account_verified = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="Cuenta verificada")
    account_id = models.CharField(max_length=180, blank=True, verbose_name="ID de cuenta")
    payment_method_ready = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="Método de pago configurado")
    terms_accepted = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="Términos y condiciones aceptados")
    campaigns_enabled = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="¿Tiene / realizará campañas publicitarias?")

    # Meta Ads
    portfolio_created = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="Portafolio comercial creado")
    portfolio_id = models.CharField(max_length=180, blank=True, verbose_name="ID de portafolio")
    ad_account_created = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="Cuenta publicitaria creada")
    fanpage_connected = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="Fanpage vinculada / acceso")

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "platform"], name="unique_marketing_ad_account_platform")]
        ordering = ["platform"]

    def __str__(self):
        return f"{self.get_platform_display()} · {self.workspace.project.client.business_name}"


class AdCampaign(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="ad_campaigns")
    platform = models.CharField(max_length=20, choices=CampaignPlatform.choices)
    name = models.CharField(max_length=180)
    account_id = models.CharField(max_length=120, blank=True)
    objective = models.CharField(max_length=180, blank=True)
    campaign_type = models.CharField(max_length=180, blank=True)
    primary_keyword = models.CharField(max_length=240, blank=True, verbose_name="Keyword principal")
    keyword_research = models.TextField(blank=True, help_text="Keywords a usar o link al estudio.")
    creative_notes = models.TextField(blank=True, help_text="Ideas/propuesta y brief para Diseño.")
    manager_review_notes = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    weekly_followup_enabled = models.BooleanField(default=True, verbose_name="Seguimiento semanal")
    monthly_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], verbose_name="Costo de campaña por mes")
    conversion_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], verbose_name="Costo por conversión")
    conversions = models.PositiveIntegerField(null=True, blank=True, verbose_name="Conversiones")
    status = models.CharField(max_length=30, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT)
    manager_approved = models.BooleanField(default=False)
    manager_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_ad_campaigns")
    manager_approved_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ad_campaigns")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1 if self.start_date and self.end_date else None

    @property
    def can_launch(self):
        return self.manager_approved and self.status in {CampaignStatus.APPROVED, CampaignStatus.SCHEDULED, CampaignStatus.LAUNCHED, CampaignStatus.COMPLETED}

    def __str__(self):
        return f"{self.get_platform_display()} · {self.name}"


class CampaignWeeklyReport(TimestampedModel):
    campaign = models.ForeignKey(AdCampaign, on_delete=models.CASCADE, related_name="weekly_reports")
    review_date = models.DateField(default=timezone.localdate)
    spend = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    leads = models.PositiveIntegerField(null=True, blank=True)
    conversions = models.PositiveIntegerField(null=True, blank=True)
    conversion_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="marketing_weekly_reports")

    class Meta:
        ordering = ["-review_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["campaign", "review_date"], name="unique_campaign_weekly_report_date")]

    def __str__(self):
        return f"{self.campaign.name} · {self.review_date}"


class SocialMediaTracking(TimestampedModel):
    client = models.OneToOneField("clients.Client", on_delete=models.CASCADE, related_name="social_media_tracking")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="social_tracking_rows")
    reviews = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    products = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    profile_percentage = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="Porcentaje perfil")
    google_business = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="GB")
    networks = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="REDES")
    website_in_gb = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="WEBSITE EN GB")
    last_post_gb = models.DateField(null=True, blank=True, verbose_name="Último Post GB")
    gb_notes = models.TextField(blank=True, verbose_name="Notas GB")
    lsa = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    photos = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="FOTOS")
    last_lead = models.CharField(max_length=80, blank=True, verbose_name="Último Lead")
    ads_verified = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE, verbose_name="ADS VERIFICADO")
    google_followup = models.CharField(max_length=10, choices=YesNo.choices, default=YesNo.NO, verbose_name="Seguimiento con Google?")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["client__business_name"]

    def __str__(self):
        return self.client.business_name


class SocialMediaAudit(TimestampedModel):
    """Auditoría liviana del seguimiento Social Media.

    La información operativa no se duplica aquí: se lee de Diseño, Marketing y
    del plan contratado. Este modelo solo guarda la confirmación de revisión.
    """

    project_plan = models.OneToOneField(
        "projects.ProjectPlanAssignment",
        on_delete=models.CASCADE,
        related_name="social_media_audit",
        verbose_name="Plan Social Media del proyecto",
    )
    is_ready = models.BooleanField(default=False, verbose_name="Auditoría lista")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Última revisión")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_social_media_audits",
        verbose_name="Revisado por",
    )
    note = models.TextField(blank=True, verbose_name="Nota de auditoría")

    class Meta:
        ordering = ["project_plan__project__client__business_name", "project_plan__plan__name"]

    @property
    def project(self):
        return self.project_plan.project

    @property
    def client(self):
        return self.project_plan.project.client

    def __str__(self):
        return f"Auditoría Social Media · {self.client.business_name} · {self.project_plan.plan.name}"


class SocialMediaPlan(TimestampedModel):
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="social_media_plans")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="social_media_plans")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="social_media_plans")
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    next_report_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.start_date and not self.next_report_date:
            self.next_report_date = self.start_date + timedelta(days=30)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Social Media · {self.client.business_name}"


class SocialMediaDailyLog(TimestampedModel):
    plan = models.ForeignKey(SocialMediaPlan, on_delete=models.CASCADE, related_name="daily_logs")
    date = models.DateField(default=timezone.localdate)
    follow_up = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    publication = models.CharField(max_length=20, choices=BinaryStatus.choices, default=BinaryStatus.INCOMPLETE)
    post_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["plan", "date"], name="unique_social_daily_plan_date")]

    def __str__(self):
        return f"{self.plan.client.business_name} · {self.date}"
