from django import forms
from django.utils import timezone
from apps.accounts.models import UserAccount
from apps.plans.models import ClientPlan, ServicePlan
from apps.plans.models.choices import BillingCycle, ClientPlanStatus, PlanDepartment, RenewalFrequency, ServiceType
from apps.plans.services import current_cycle_bounds
from apps.projects.models import Project
from .models import (
    AdCampaign,
    AdvertisingAccount,
    CampaignWeeklyReport,
    GoogleLSAWorkspace,
    MarketingBrief,
    MarketingChecklistItem,
    MarketingDocument,
    MarketingTask,
    MarketingWorkspace,
    SocialMediaDailyLog,
    SocialMediaPlan,
    SocialMediaSubscriptionProfile,
    SocialMediaContentRecord,
    SocialMediaTracking,
)


TEXTAREA_2 = forms.Textarea(attrs={"rows": 2})
TEXTAREA_3 = forms.Textarea(attrs={"rows": 3})
TEXTAREA_4 = forms.Textarea(attrs={"rows": 4})
DATE = forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
NUMBER_MONEY = forms.NumberInput(attrs={"step": "0.01", "min": "0"})


class MarketingBriefForm(forms.ModelForm):
    class Meta:
        model = MarketingBrief
        exclude = ["project"]
        widgets = {f: TEXTAREA_3 for f in ["objective", "target_audience", "content_pillars", "campaign_notes"]}


class MarketingTaskForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(
            role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True
        )
        if user and not user.is_manager:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(
                assignments__user=user, assignments__area="marketing"
            ).distinct()

    class Meta:
        model = MarketingTask
        fields = ["project", "area", "title", "description", "assigned_to", "status", "due_date"]
        widgets = {"description": TEXTAREA_3, "due_date": DATE}


class MarketingIntakeForm(forms.ModelForm):
    """Pantalla 1: datos de reunión y checks que habilitan el flujo.

    Horario, Servicios y Áreas se excluyen porque ya se solicitan en otra etapa del CRM.
    """

    class Meta:
        model = MarketingWorkspace
        fields = [
            "meeting_summary",
            "owner_name",
            "legal_business_name",
            "founding_date",
            "company_description",
            "contact_email",
            "email_account_mode",
            "gmail_email",
            "business_profile_mode",
            "lsa_documents_available",
            "assigned_to",
            "notes",
        ]
        widgets = {
            "founding_date": forms.TextInput(attrs={"placeholder": "Ej.: 2018, marzo de 2018, 15 años operando"}),
            "meeting_summary": TEXTAREA_4,
            "company_description": TEXTAREA_4,
            "notes": TEXTAREA_3,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(
            role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True
        )

        project = None
        if getattr(self.instance, "project_id", None):
            project = self.instance.project

        if project:
            marketing_assignment = (
                project.assignments.select_related("user")
                .filter(
                    area="marketing",
                    status__in=["assigned", "active"],
                    user__is_active=True,
                )
                .order_by("-updated_at", "-created_at", "-pk")
                .first()
            )

            if marketing_assignment:
                self.instance.assigned_to = marketing_assignment.user
                self.initial["assigned_to"] = marketing_assignment.user_id
                self.fields["assigned_to"].disabled = True
                self.fields["assigned_to"].help_text = (
                    "Responsable heredado de la asignación del proyecto."
                )
            else:
                self.fields["assigned_to"].help_text = (
                    "El proyecto no tiene responsable de Marketing; puedes elegirlo aquí."
                )

            if not (self.instance.owner_name or "").strip():
                inherited_owner = (project.client.full_name or "").strip()
                if inherited_owner:
                    self.initial["owner_name"] = inherited_owner

        self.fields["meeting_summary"].label = "Notas de la reunión"
        self.fields["meeting_summary"].required = False
        self.fields["meeting_summary"].help_text = (
            "Opcional. Registra únicamente observaciones útiles de la reunión."
        )
        self.fields["owner_name"].required = False
        self.fields["owner_name"].help_text = (
            "Se precarga desde el cliente cuando existe y puedes editarlo."
        )
        self.fields["gmail_email"].label = "Correo / Gmail utilizado"
        self.fields["notes"].label = "Notas generales"
        self.fields["founding_date"].help_text = "Campo libre: puedes registrar una fecha, un año o una referencia indicada por el cliente."
        self.fields["email_account_mode"].help_text = (
            "Si ya existe, registra el correo. Si lo crea CEO Marketing, puedes continuar sin ingresar una dirección."
        )
        self.fields["email_account_mode"].choices = [
            ("existing", "Ya existe"),
            ("create", "Lo crea CEO Marketing"),
            ("pending", "Pendiente de definir"),
        ]
        self.fields["lsa_documents_available"].help_text = "Selecciona Sí o No. La respuesta condiciona los campos documentales dentro de Google LSA."

    def clean(self):
        cleaned = super().clean()
        email_mode = cleaned.get("email_account_mode")
        gmail_email = (cleaned.get("gmail_email") or "").strip()
        contact_email = (cleaned.get("contact_email") or "").strip()

        if email_mode == "existing":
            operational_email = gmail_email or contact_email
            if not operational_email:
                self.add_error(
                    "contact_email",
                    "Registra el correo electrónico existente.",
                )
                self.add_error(
                    "gmail_email",
                    "Registra el correo utilizado. Puedes usar el mismo correo electrónico del cliente.",
                )
            elif not gmail_email:
                cleaned["gmail_email"] = operational_email
        elif email_mode in {"create", "pending"}:
            cleaned["gmail_email"] = ""

        return cleaned


# Compatibilidad con imports anteriores.
MarketingWorkspaceForm = MarketingIntakeForm


class GoogleBusinessForm(forms.ModelForm):
    """Google Business: perfil + reviews.

    La situación del perfil se define en la información inicial. En esta vista se
    trabaja únicamente la información operativa del perfil, su verificación y el
    QR de reviews.
    """

    class Meta:
        model = MarketingWorkspace
        fields = [
            "business_profile_status",
            "business_profile_link",
            "business_profile_id",
            "business_profile_social_links",
            "business_profile_notes",
            "review_link",
            "review_message",
        ]
        widgets = {
            "business_profile_social_links": TEXTAREA_3,
            "business_profile_notes": TEXTAREA_3,
            "review_message": forms.Textarea(attrs={"rows": 12, "readonly": "readonly"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["business_profile_status"].label = "Estado de verificación"
        self.fields["business_profile_link"].label = "Link del perfil de Google Business"
        self.fields["business_profile_id"].label = "ID del perfil"
        self.fields["business_profile_social_links"].label = "Links de redes sociales"
        self.fields["business_profile_notes"].label = "Notas"
        self.fields["review_link"].label = "Link directo para dejar la review"
        self.fields["review_message"].label = "Mensaje para enviar al customer"
        self.fields["review_message"].help_text = "Se genera automáticamente con el nombre de la empresa y el link de review guardado."

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("business_profile_status")

        if status in {"verification", "approved"}:
            required = {
                "business_profile_link": "Registra el link del perfil de Google Business.",
                "business_profile_id": "Registra el ID del perfil.",
                "business_profile_social_links": "Registra al menos un link de red social.",
            }
            for field, message in required.items():
                value = cleaned.get(field)
                if not value or (isinstance(value, str) and not value.strip()):
                    self.add_error(field, message)

        if status == "approved" and not cleaned.get("review_link"):
            self.add_error("review_link", "Para aprobar Google Business registra el link directo de reviews.")

        return cleaned


class GoogleLSAForm(forms.ModelForm):
    """Google LSA con dependencias reales entre documentos, Social Media y recordatorios."""

    class Meta:
        model = GoogleLSAWorkspace
        fields = [
            "documents_drive_url",
            "driver_license_ready",
            "founding_year",
            "verification_status",
            "weekly_cost",
            "leads_last_7_days",
            "last_lead_date",
            "has_social_media",
            "followup_mode",
            "followup_start_date",
            "custom_followup_date",
            "photo_reminder_enabled",
            "photo_reminder_start_date",
            "notes",
        ]
        widgets = {
            "followup_mode": forms.HiddenInput(),
            "followup_start_date": DATE,
            "custom_followup_date": forms.HiddenInput(),
            "photo_reminder_start_date": DATE,
            "last_lead_date": DATE,
            "weekly_cost": NUMBER_MONEY,
            "founding_year": forms.NumberInput(attrs={"min": "1800", "max": "2100", "step": "1"}),
            "notes": TEXTAREA_4,
        }

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace or (self.instance.workspace if getattr(self.instance, "workspace_id", None) else None)
        self.fields["documents_drive_url"].label = "Link del Drive de documentos"
        self.fields["driver_license_ready"].label = "Licencia de conducir"
        self.fields["founding_year"].label = "Año de fundación"
        self.fields["verification_status"].label = "Validación Google LSA"
        self.fields["weekly_cost"].label = "Costo por semana"
        self.fields["leads_last_7_days"].label = "Cantidad de leads en los últimos 7 días"
        self.fields["last_lead_date"].label = "Fecha del último lead"
        self.fields["has_social_media"].label = "¿Tiene Social Media?"
        self.fields["followup_start_date"].label = "Primera revisión semanal"
        self.fields["custom_followup_date"].label = "Fecha del recordatorio personalizado"
        self.fields["photo_reminder_enabled"].label = "¿Activar recordatorio para subir fotos cada 15 días?"
        self.fields["photo_reminder_start_date"].label = "Primera fecha para subir fotos"
        self.fields["photo_reminder_enabled"].help_text = "Sí es el valor predeterminado. Cada fecha genera una sola ocurrencia; guardar nuevamente no reactiva recordatorios ya atendidos."
        self.fields["has_social_media"].help_text = "Sí = revisión semanal. No = sin recordatorio adicional y sin fecha obligatoria."
        self.fields["notes"].label = "Notas"

    def clean(self):
        cleaned = super().clean()
        docs_expected = bool(self.workspace and self.workspace.lsa_documents_available == "yes")
        has_social = cleaned.get("has_social_media")
        verification = cleaned.get("verification_status")

        if docs_expected:
            if not cleaned.get("documents_drive_url"):
                self.add_error("documents_drive_url", "Registra el link del Drive donde están los documentos.")
            if cleaned.get("driver_license_ready") not in {"yes", "no"}:
                self.add_error("driver_license_ready", "Selecciona Sí o No para la licencia de conducir.")
        else:
            cleaned["documents_drive_url"] = ""
            cleaned["driver_license_ready"] = ""

        if not cleaned.get("founding_year"):
            self.add_error("founding_year", "Registra el año de fundación de la empresa.")

        if verification == "complete":
            if cleaned.get("weekly_cost") is None:
                self.add_error("weekly_cost", "Registra el costo por semana para completar la validación LSA.")
            if cleaned.get("leads_last_7_days") is None:
                self.add_error("leads_last_7_days", "Registra la cantidad de leads de los últimos 7 días.")

        if has_social == "yes":
            cleaned["followup_mode"] = "weekly"
            cleaned["custom_followup_date"] = None
            if not cleaned.get("followup_start_date"):
                self.add_error("followup_start_date", "Selecciona la primera fecha de revisión semanal.")
        elif has_social == "no":
            cleaned["followup_mode"] = "none"
            cleaned["followup_start_date"] = None
            cleaned["custom_followup_date"] = None
        else:
            cleaned["followup_mode"] = "none"
            cleaned["followup_start_date"] = None
            cleaned["custom_followup_date"] = None
            self.add_error("has_social_media", "Selecciona Sí o No para Social Media.")

        photo_enabled = cleaned.get("photo_reminder_enabled")
        if photo_enabled == "yes":
            if not cleaned.get("photo_reminder_start_date"):
                self.add_error(
                    "photo_reminder_start_date",
                    "Selecciona la primera fecha. El CRM repetirá el recordatorio cada 15 días.",
                )
        elif photo_enabled == "no":
            cleaned["photo_reminder_start_date"] = None
        else:
            self.add_error("photo_reminder_enabled", "Selecciona Sí o No para el recordatorio de fotos.")

        return cleaned


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = MarketingChecklistItem
        fields = ["status", "yes_no", "detail", "due_date"]
        widgets = {"detail": TEXTAREA_2, "due_date": DATE}


class MarketingDocumentForm(forms.ModelForm):
    class Meta:
        model = MarketingDocument
        fields = ["title", "document_type", "file", "drive_url", "notes"]
        widgets = {"notes": TEXTAREA_2}

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("file") and not cleaned.get("drive_url"):
            raise forms.ValidationError("Sube un PDF o registra un link de Drive.")
        return cleaned


class TraditionalAdvertisingForm(forms.ModelForm):
    """Control maestro que habilita Meta / Google / TikTok en Publicidad Digital."""

    class Meta:
        model = AdvertisingAccount
        fields = ["enabled", "notes"]
        widgets = {"notes": TEXTAREA_3}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["enabled"].label = "¿Activar Publicidad tradicional?"
        self.fields["notes"].label = "Notas de Publicidad tradicional"

    def clean_enabled(self):
        value = self.cleaned_data.get("enabled")
        if value not in {"yes", "no"}:
            raise forms.ValidationError("Selecciona Sí o No.")
        return value


class AdvertisingAccountForm(forms.ModelForm):
    DEPENDENT_FIELDS = [
        "profile_url",
        "account_verified",
        "account_id",
        "payment_method_ready",
        "terms_accepted",
        "campaigns_enabled",
        "portfolio_created",
        "portfolio_id",
        "ad_account_created",
        "fanpage_connected",
    ]

    class Meta:
        model = AdvertisingAccount
        fields = [
            "enabled",
            "profile_url",
            "account_verified",
            "account_id",
            "payment_method_ready",
            "terms_accepted",
            "campaigns_enabled",
            "portfolio_created",
            "portfolio_id",
            "ad_account_created",
            "fanpage_connected",
            "notes",
        ]
        widgets = {"notes": TEXTAREA_3}

    def __init__(self, *args, platform=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.platform = platform or getattr(self.instance, "platform", None)
        self.fields["enabled"].label = "¿Se trabajará esta plataforma?"

    def _require_choice(self, cleaned, field, message=None):
        if cleaned.get(field) not in {"yes", "no"}:
            self.add_error(field, message or "Selecciona Sí o No.")

    def clean(self):
        cleaned = super().clean()
        enabled = cleaned.get("enabled")

        if enabled not in {"yes", "no"}:
            self.add_error("enabled", "Selecciona Sí o No.")
            return cleaned

        if enabled == "no":
            for field in self.DEPENDENT_FIELDS:
                cleaned[field] = ""
            return cleaned

        if not cleaned.get("profile_url"):
            self.add_error("profile_url", "Registra el link de la plataforma.")

        self._require_choice(cleaned, "account_verified")
        self._require_choice(cleaned, "payment_method_ready")
        self._require_choice(cleaned, "campaigns_enabled")

        if self.platform == "meta":
            self._require_choice(cleaned, "portfolio_created")
            self._require_choice(cleaned, "ad_account_created")
            self._require_choice(cleaned, "fanpage_connected")
            if cleaned.get("portfolio_created") == "yes" and not (cleaned.get("portfolio_id") or "").strip():
                self.add_error("portfolio_id", "Si el portafolio está creado, registra su ID.")
            if cleaned.get("ad_account_created") == "yes" and not (cleaned.get("account_id") or "").strip():
                self.add_error("account_id", "Si la cuenta publicitaria está creada, registra su ID.")
            cleaned["terms_accepted"] = ""
        elif self.platform in {"google", "tiktok"}:
            self._require_choice(cleaned, "terms_accepted")
            if not (cleaned.get("account_id") or "").strip():
                self.add_error("account_id", "Registra el ID de la cuenta.")
            for field in ["portfolio_created", "portfolio_id", "ad_account_created", "fanpage_connected"]:
                cleaned[field] = ""

        return cleaned


class AdCampaignForm(forms.ModelForm):
    class Meta:
        model = AdCampaign
        fields = [
            "project",
            "platform",
            "name",
            "account_id",
            "objective",
            "campaign_type",
            "primary_keyword",
            "keyword_research",
            "creative_notes",
            "start_date",
            "end_date",
            "weekly_followup_enabled",
            "monthly_cost",
            "conversion_cost",
            "conversions",
            "status",
            "assigned_to",
            "notes",
        ]
        widgets = {
            "start_date": DATE,
            "end_date": DATE,
            "keyword_research": TEXTAREA_3,
            "creative_notes": TEXTAREA_3,
            "notes": TEXTAREA_3,
            "monthly_cost": NUMBER_MONEY,
            "conversion_cost": NUMBER_MONEY,
        }

    def __init__(self, *args, user=None, project=None, platform=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(
            role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True
        )
        if project:
            self.fields["project"].initial = project
            self.fields["project"].widget = forms.HiddenInput()
        elif user and not user.is_manager:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(
                assignments__user=user, assignments__area="marketing"
            ).distinct()
        if platform:
            self.fields["platform"].initial = platform
            self.fields["platform"].widget = forms.HiddenInput()

        approved = bool(getattr(self.instance, "manager_approved", False))
        current_status = getattr(self.instance, "status", "draft") or "draft"
        if not approved:
            allowed = {"draft", "manager_review", "changes_requested"}
            self.fields["status"].choices = [
                choice for choice in self.fields["status"].choices
                if choice[0] in allowed or choice[0] == current_status
            ]

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        status = cleaned.get("status")
        platform = cleaned.get("platform") or getattr(self.instance, "platform", None)

        if platform == "traditional" and not self.instance.pk:
            self.add_error("platform", "Publicidad tradicional ahora habilita Meta, Google y TikTok; crea la campaña dentro de una de esas plataformas.")

        if start and end and end < start:
            self.add_error("end_date", "La fecha final no puede ser anterior al inicio.")

        needs_review_data = status in {"manager_review", "approved", "scheduled", "launched", "completed"}
        if needs_review_data:
            for field, message in {
                "objective": "Define el objetivo antes de enviar a validación.",
                "campaign_type": "Define el tipo de campaña antes de enviar a validación.",
                "start_date": "Define cuándo se lanza la campaña.",
                "end_date": "Define cuándo finaliza la campaña.",
            }.items():
                if not cleaned.get(field):
                    self.add_error(field, message)

            if platform == "google":
                if not (cleaned.get("primary_keyword") or "").strip():
                    self.add_error("primary_keyword", "Google Ads requiere keyword principal antes de validación.")
                if not (cleaned.get("keyword_research") or "").strip():
                    self.add_error("keyword_research", "Registra las keywords a usar o el estudio realizado.")
                if cleaned.get("monthly_cost") is None:
                    self.add_error("monthly_cost", "Registra el costo mensual de la campaña Google Ads.")

        return cleaned


class CampaignManagerReviewForm(forms.ModelForm):
    decision = forms.ChoiceField(
        choices=[("approved", "Aprobar campaña"), ("changes_requested", "Solicitar correcciones")],
        widget=forms.RadioSelect,
        label="Decisión",
    )

    class Meta:
        model = AdCampaign
        fields = ["decision", "manager_review_notes"]
        widgets = {"manager_review_notes": TEXTAREA_4}


class CampaignWeeklyReportForm(forms.ModelForm):
    class Meta:
        model = CampaignWeeklyReport
        fields = ["review_date", "spend", "leads", "conversions", "conversion_cost", "notes"]
        widgets = {
            "review_date": DATE,
            "spend": NUMBER_MONEY,
            "conversion_cost": NUMBER_MONEY,
            "notes": TEXTAREA_4,
        }


class SocialMediaTrackingForm(forms.ModelForm):
    class Meta:
        model = SocialMediaTracking
        exclude = []
        widgets = {"last_post_gb": DATE, "gb_notes": TEXTAREA_2, "notes": TEXTAREA_2}


class SocialMediaPlanForm(forms.ModelForm):
    class Meta:
        model = SocialMediaPlan
        fields = ["client", "project", "assigned_to", "start_date", "end_date", "active", "next_report_date", "notes"]
        widgets = {"start_date": DATE, "end_date": DATE, "next_report_date": DATE, "notes": TEXTAREA_3}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(
            role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True
        )
        if user and not user.is_manager:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(
                assignments__user=user, assignments__area="marketing"
            ).distinct()
        self.fields["project"].help_text = "Vincula el plan con el mismo proyecto usado por Diseño para mantener seguimiento y publicaciones relacionados."

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get("client")
        project = cleaned.get("project")
        if client and project and project.client_id != client.pk:
            self.add_error("project", "El proyecto seleccionado debe pertenecer al mismo cliente del plan Social Media.")
        return cleaned


class SocialMediaDailyLogForm(forms.ModelForm):
    class Meta:
        model = SocialMediaDailyLog
        fields = ["date", "follow_up", "publication", "post_url", "notes"]
        widgets = {"date": DATE, "notes": TEXTAREA_2}


SOCIAL_MEDIA_NETWORK_CHOICES = [
    ("google_business", "Google"),
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("youtube", "YouTube"),
    ("tiktok", "TikTok"),
]

SOCIAL_MEDIA_CYCLE_CHOICES = [
    ("7", "7 días"),
    ("15", "15 días"),
    ("30", "30 días / mensual"),
]


class SocialMediaCatalogPlanForm(forms.ModelForm):
    """Editor Marketing del catálogo Social Media compartido con Diseño.

    No duplica planes: usa ``plans.ServicePlan`` y guarda redes/ciclo en el JSON
    ``rules`` ya existente del plan.
    """

    default_networks = forms.MultipleChoiceField(
        choices=SOCIAL_MEDIA_NETWORK_CHOICES,
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="Redes incluidas",
    )
    extra_platforms = forms.CharField(
        required=False,
        label="Plataformas extras",
        help_text="Ej.: LinkedIn, Pinterest u otra plataforma no listada.",
    )
    cycle_days = forms.ChoiceField(choices=SOCIAL_MEDIA_CYCLE_CHOICES, label="Duración del ciclo")

    class Meta:
        model = ServicePlan
        fields = ["name", "weekly_posts", "weekly_videos", "base_price", "currency", "description", "is_active"]
        widgets = {
            "weekly_posts": forms.NumberInput(attrs={"min": 0}),
            "weekly_videos": forms.NumberInput(attrs={"min": 0}),
            "base_price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "description": TEXTAREA_3,
        }
        labels = {
            "weekly_posts": "Posts por ciclo",
            "weekly_videos": "Videos por ciclo",
            "base_price": "Costo del plan",
            "is_active": "Plan activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rules = dict(getattr(self.instance, "rules", {}) or {}) if getattr(self.instance, "pk", None) else {}
        self.fields["default_networks"].initial = rules.get("social_networks", [])
        self.fields["extra_platforms"].initial = rules.get("extra_platforms", "")
        self.fields["cycle_days"].initial = str(rules.get("cycle_days", 15))

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get("weekly_posts") or cleaned.get("weekly_videos")):
            raise forms.ValidationError("El plan debe incluir al menos 1 post o 1 video por ciclo.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.department = PlanDepartment.DESIGN
        obj.service_type = ServiceType.SOCIAL_MEDIA
        obj.billing_cycle = BillingCycle.CUSTOM
        rules = dict(obj.rules or {})
        rules.update({
            "social_networks": self.cleaned_data.get("default_networks", []),
            "extra_platforms": (self.cleaned_data.get("extra_platforms") or "").strip(),
            "cycle_days": int(self.cleaned_data.get("cycle_days") or 15),
        })
        obj.rules = rules
        if commit:
            if not obj.code:
                from django.utils.text import slugify
                base = slugify(obj.name)[:65] or "social-media"
                code = base
                n = 2
                qs = ServicePlan.objects.exclude(pk=obj.pk) if obj.pk else ServicePlan.objects.all()
                while qs.filter(code=code).exists():
                    code = f"{base}-{n}"[:80]
                    n += 1
                obj.code = code
            obj.full_clean()
            obj.save()
        return obj


class SocialMediaSubscriptionV15Form(forms.ModelForm):
    project = forms.ModelChoiceField(queryset=Project.objects.none(), label="Proyecto")
    social_networks = forms.MultipleChoiceField(
        choices=SOCIAL_MEDIA_NETWORK_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Redes que se manejarán",
        help_text="Si no marcas ninguna, se usarán automáticamente las redes definidas en el plan.",
    )
    assigned_to = forms.ModelChoiceField(
        queryset=UserAccount.objects.none(),
        required=False,
        label="Responsable de Marketing",
    )
    needs_photos = forms.ChoiceField(choices=(("no", "No"), ("yes", "Sí")), label="¿Hace falta pedir fotos al cliente?")
    photo_request_status = forms.ChoiceField(choices=(("incomplete", "Pendiente"), ("complete", "Recibidas / completo")), label="Estado de fotos")
    photo_request_notes = forms.CharField(required=False, widget=TEXTAREA_2, label="Detalle de fotos solicitadas")
    extra_platforms = forms.CharField(required=False, label="Plataformas extras")

    class Meta:
        model = ClientPlan
        fields = ["client", "plan", "start_date", "end_date", "notes", "is_active"]
        widgets = {"start_date": DATE, "end_date": DATE, "notes": TEXTAREA_3}
        labels = {
            "client": "Empresa / cliente",
            "plan": "Plan Social Media",
            "start_date": "Desde cuándo",
            "end_date": "Hasta cuándo",
            "notes": "Notas de la suscripción",
            "is_active": "Suscripción activa",
        }

    def __init__(self, *args, user=None, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.profile = profile
        plan_qs = ServicePlan.objects.filter(
            department=PlanDepartment.DESIGN,
            service_type=ServiceType.SOCIAL_MEDIA,
        )
        if not (self.instance and self.instance.pk):
            plan_qs = plan_qs.filter(is_active=True)
        self.fields["plan"].queryset = plan_qs.order_by("-is_active", "name")
        projects = Project.objects.select_related("client").order_by("client__business_name", "project_code")
        if user and not user.is_manager:
            projects = projects.filter(assignments__user=user, assignments__area="marketing").distinct()
        self.fields["project"].queryset = projects
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(
            role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER],
            is_active=True,
        ).order_by("display_name", "email")

        if profile:
            self.fields["project"].initial = profile.project
            self.fields["assigned_to"].initial = profile.assigned_to
            self.fields["needs_photos"].initial = profile.needs_photos
            self.fields["photo_request_status"].initial = profile.photo_request_status
            self.fields["photo_request_notes"].initial = profile.photo_request_notes
            self.fields["extra_platforms"].initial = profile.extra_platforms
        else:
            self.fields["needs_photos"].initial = "no"
            self.fields["photo_request_status"].initial = "incomplete"
            self.fields["start_date"].initial = timezone.localdate()
            plan_id = self.initial.get("plan")
            if plan_id:
                plan = self.fields["plan"].queryset.filter(pk=plan_id).first()
                if plan:
                    self.fields["social_networks"].initial = list((plan.rules or {}).get("social_networks", []))
                    self.fields["extra_platforms"].initial = (plan.rules or {}).get("extra_platforms", "")

        if self.instance and self.instance.pk:
            self.fields["social_networks"].initial = self.instance.social_networks or []

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get("project")
        client = cleaned.get("client")
        plan = cleaned.get("plan")
        if project and client and project.client_id != client.pk:
            self.add_error("project", "El proyecto debe pertenecer a la misma empresa seleccionada.")
        if plan and (plan.department != PlanDepartment.DESIGN or plan.service_type != ServiceType.SOCIAL_MEDIA):
            self.add_error("plan", "Selecciona un plan válido de Social Media.")
        if plan and not cleaned.get("social_networks"):
            cleaned["social_networks"] = list((plan.rules or {}).get("social_networks", []))
        if not cleaned.get("social_networks"):
            self.add_error("social_networks", "Define al menos una red en la suscripción o en el plan seleccionado.")
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La fecha final no puede ser anterior a la fecha de inicio.")
        if cleaned.get("needs_photos") == "no":
            cleaned["photo_request_status"] = "complete"
            cleaned["photo_request_notes"] = ""
        return cleaned

    def save_client_plan(self):
        obj = super().save(commit=False)
        obj.social_networks = self.cleaned_data.get("social_networks", [])
        obj.purchase_date = obj.purchase_date or timezone.localdate()
        obj.status = ClientPlanStatus.ACTIVE if obj.is_active else ClientPlanStatus.PAUSED
        if obj.plan_id:
            obj.agreed_price = obj.plan.base_price
            obj.currency = obj.plan.currency
            cycle_days = int((obj.plan.rules or {}).get("cycle_days", 15))
            obj.renewal_frequency = {7: RenewalFrequency.WEEKLY, 15: RenewalFrequency.BIWEEKLY, 30: RenewalFrequency.MONTHLY}.get(cycle_days, RenewalFrequency.BIWEEKLY)
            _, obj.renewal_date = current_cycle_bounds(obj.start_date or timezone.localdate(), obj.renewal_frequency)
        obj.save()
        return obj


class SocialMediaContentRecordForm(forms.ModelForm):
    planning_month = forms.DateField(
        input_formats=["%Y-%m", "%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m", attrs={"type": "month"}),
        label="Mes de planificación",
    )

    class Meta:
        model = SocialMediaContentRecord
        fields = ["planning_month", "service_used", "topic", "objective", "summary", "adjustment_notes", "published_on", "post_url"]
        widgets = {
            "objective": TEXTAREA_2,
            "summary": TEXTAREA_3,
            "adjustment_notes": TEXTAREA_2,
            "published_on": DATE,
        }

    def clean_planning_month(self):
        value = self.cleaned_data["planning_month"]
        return value.replace(day=1)
