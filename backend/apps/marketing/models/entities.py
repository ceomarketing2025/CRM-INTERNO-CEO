from datetime import timedelta
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from apps.core.models import TimestampedModel
from .choices import BinaryStatus, BusinessProfilePresence, BusinessProfileStatus, CampaignPlatform, CampaignStatus, ChecklistArea, MarketingTaskStatus, YesNo


class MarketingBrief(TimestampedModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="marketing_brief")
    objective = models.TextField(blank=True)
    target_audience = models.TextField(blank=True)
    channels = models.CharField(max_length=255, blank=True, help_text="Facebook, Instagram, TikTok, Google, etc.")
    tone = models.CharField(max_length=180, blank=True)
    content_pillars = models.TextField(blank=True)
    campaign_notes = models.TextField(blank=True)
    def __str__(self): return f"Brief marketing · {self.project}"


class MarketingTask(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="marketing_tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="marketing_tasks")
    status = models.CharField(max_length=20, choices=MarketingTaskStatus.choices, default=MarketingTaskStatus.TODO)
    due_date = models.DateField(null=True, blank=True)
    def __str__(self): return self.title


class MarketingWorkspace(TimestampedModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="marketing_workspace")
    meeting_summary = models.TextField(blank=True, verbose_name="Datos recolectados de la reunión")
    owner_name = models.CharField(max_length=180, blank=True, verbose_name="Nombre del dueño")
    legal_business_name = models.CharField(max_length=220, blank=True, verbose_name="Nombre legal de la empresa")
    founding_date = models.DateField(null=True, blank=True, verbose_name="Fecha de fundación")
    social_links = models.TextField(blank=True, verbose_name="Redes sociales")
    company_description = models.TextField(blank=True, verbose_name="Descripción de la empresa")
    business_hours = models.TextField(blank=True, verbose_name="Horario")
    services = models.TextField(blank=True, verbose_name="Servicios")
    service_areas = models.TextField(blank=True, verbose_name="Áreas")
    gmail_email = models.EmailField(blank=True, verbose_name="Gmail creado")
    webmail_has = models.CharField(max_length=10, choices=YesNo.choices, blank=True, default="", verbose_name="¿Cuenta con webmail?")
    webmail_email = models.EmailField(blank=True, verbose_name="Webmail / correo corporativo")
    webmail_secure_reference_url = models.URLField(blank=True, verbose_name="Referencia segura de credenciales", help_text="Usa un link seguro/Drive; no guardes contraseñas en texto plano.")
    business_profile_mode = models.CharField(max_length=20, choices=BusinessProfilePresence.choices, blank=True, default="", verbose_name="Google Business: situación")
    business_profile_status = models.CharField(max_length=30, choices=BusinessProfileStatus.choices, default=BusinessProfileStatus.NOT_STARTED, verbose_name="Verificación Google Business")
    business_profile_link = models.URLField(blank=True, verbose_name="Link Google Business")
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
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="marketing_workspaces")
    shared_info_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_shared_marketing_profiles", verbose_name="Última edición compartida por")
    shared_info_updated_at = models.DateTimeField(null=True, blank=True, verbose_name="Última edición compartida")

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

    class Meta:
        ordering = ["area", "order", "id"]
        constraints = [models.UniqueConstraint(fields=["workspace", "key"], name="unique_marketing_workspace_check_key")]

    def save(self, *args, **kwargs):
        if self.status == BinaryStatus.COMPLETE and not self.completed_at:
            self.completed_at = timezone.now()
        if self.status != BinaryStatus.COMPLETE:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self): return self.label


class MarketingDocument(TimestampedModel):
    workspace = models.ForeignKey(MarketingWorkspace, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=180)
    document_type = models.CharField(max_length=100, blank=True)
    file = models.FileField(upload_to="marketing_documents/", null=True, blank=True, validators=[FileExtensionValidator(["pdf"])])
    drive_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploaded_marketing_documents")
    def __str__(self): return self.title


class AdCampaign(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="ad_campaigns")
    platform = models.CharField(max_length=20, choices=CampaignPlatform.choices)
    name = models.CharField(max_length=180)
    account_id = models.CharField(max_length=120, blank=True)
    objective = models.CharField(max_length=180, blank=True)
    campaign_type = models.CharField(max_length=180, blank=True)
    keyword_research = models.TextField(blank=True, help_text="Keywords o link al estudio.")
    creative_notes = models.TextField(blank=True, help_text="Ideas/propuesta y brief para Diseño.")
    manager_review_notes = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ad_campaigns")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1 if self.start_date and self.end_date else None

    def __str__(self): return f"{self.get_platform_display()} · {self.name}"


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

    def __str__(self): return self.client.business_name


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

    def __str__(self): return f"Social Media · {self.client.business_name}"


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

    def __str__(self): return f"{self.plan.client.business_name} · {self.date}"
