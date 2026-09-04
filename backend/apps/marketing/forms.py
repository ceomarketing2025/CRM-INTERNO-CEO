from django import forms
from apps.accounts.models import UserAccount
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
    SocialMediaTracking,
)


TEXTAREA_2 = forms.Textarea(attrs={"rows": 2})
TEXTAREA_3 = forms.Textarea(attrs={"rows": 3})
TEXTAREA_4 = forms.Textarea(attrs={"rows": 4})
DATE = forms.DateInput(attrs={"type": "date"})
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
        fields = ["project", "title", "description", "assigned_to", "status", "due_date"]
        widgets = {"description": TEXTAREA_3, "due_date": DATE}


class MarketingIntakeForm(forms.ModelForm):
    """Pantalla 1: datos de reunión y checks que habilitan el flujo.

    Horario, Servicios y Áreas se excluyen porque ya se solicitan en otra etapa del CRM.
    """

    class Meta:
        model = MarketingWorkspace
        fields = [
            "intake_status",
            "meeting_summary",
            "owner_name",
            "legal_business_name",
            "founding_date",
            "social_links",
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
            "founding_date": DATE,
            "meeting_summary": TEXTAREA_4,
            "social_links": TEXTAREA_3,
            "company_description": TEXTAREA_4,
            "notes": TEXTAREA_3,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(
            role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True
        )
        self.fields["gmail_email"].label = "Correo / Gmail utilizado"
        self.fields["notes"].label = "Notas generales"
        self.fields["intake_status"].help_text = "Marca Completo cuando los checks obligatorios de la reunión estén definidos."
        self.fields["email_account_mode"].help_text = "Indica si el correo ya existe o si Marketing lo crea. No se solicitan contraseñas aquí."
        self.fields["lsa_documents_available"].help_text = "Selecciona Sí o No. La respuesta condiciona los campos documentales dentro de Google LSA."

    def clean(self):
        cleaned = super().clean()
        email_mode = cleaned.get("email_account_mode")
        gmail_email = (cleaned.get("gmail_email") or "").strip()
        contact_email = (cleaned.get("contact_email") or "").strip()
        intake_status = cleaned.get("intake_status")
        business_profile_mode = cleaned.get("business_profile_mode")
        lsa_documents_available = cleaned.get("lsa_documents_available")

        # El correo operativo puede venir del campo Correo electrónico o del
        # campo Correo/Gmail utilizado. Antes el formulario exigía únicamente
        # gmail_email mientras el checklist aceptaba cualquiera de los dos,
        # provocando que la reunión pareciera completa pero nunca se guardara.
        if email_mode in {"existing", "create"}:
            operational_email = gmail_email or contact_email
            if not operational_email:
                self.add_error(
                    "contact_email",
                    "Registra el correo electrónico que ya existe o que Marketing creó.",
                )
                self.add_error(
                    "gmail_email",
                    "Registra el correo utilizado. Puedes usar el mismo correo electrónico del cliente.",
                )
            elif not gmail_email:
                # Evita pedir el mismo dato dos veces: si ya se registró arriba,
                # se reutiliza como Gmail/correo operativo.
                cleaned["gmail_email"] = operational_email
        elif email_mode == "pending":
            cleaned["gmail_email"] = ""

        if intake_status == "complete":
            if not (cleaned.get("meeting_summary") or "").strip():
                self.add_error(
                    "meeting_summary",
                    "Para completar esta etapa registra la información levantada en la reunión.",
                )

            if email_mode not in {"existing", "create"}:
                self.add_error(
                    "email_account_mode",
                    "Define si el correo ya existe o si Marketing lo creará.",
                )

            if business_profile_mode not in {"existing", "create", "no"}:
                self.add_error(
                    "business_profile_mode",
                    "Define la situación de Google Business.",
                )

            if lsa_documents_available not in {"yes", "no"}:
                self.add_error(
                    "lsa_documents_available",
                    "Selecciona Sí o No para la disponibilidad de documentos de LSA.",
                )

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

        # Cuando el perfil entra a verificación o queda aprobado, sus datos base
        # ya deben estar registrados. Esto evita estados verdes con campos vacíos.
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

        # El QR es parte del cierre del perfil aprobado.
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
            "custom_followup_date": DATE,
            "photo_reminder_start_date": DATE,
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
        self.fields["has_social_media"].label = "¿Tiene Social Media?"
        self.fields["followup_start_date"].label = "Primera revisión semanal"
        self.fields["custom_followup_date"].label = "Fecha del recordatorio personalizado"
        self.fields["photo_reminder_enabled"].label = "¿Activar recordatorio para subir fotos cada 15 días?"
        self.fields["photo_reminder_start_date"].label = "Primera fecha para subir fotos"
        self.fields["notes"].label = "Notas"

    def clean(self):
        cleaned = super().clean()
        docs_expected = bool(self.workspace and self.workspace.lsa_documents_available == "yes")
        has_social = cleaned.get("has_social_media")
        verification = cleaned.get("verification_status")

        # Documentos dependientes de la respuesta de la reunión.
        if docs_expected:
            if not cleaned.get("documents_drive_url"):
                self.add_error("documents_drive_url", "Registra el link del Drive donde están los documentos.")
            if cleaned.get("driver_license_ready") not in {"yes", "no"}:
                self.add_error("driver_license_ready", "Selecciona Sí o No para la licencia de conducir.")
        else:
            # Si en la reunión se indicó que no hay documentos, los campos quedan
            # deshabilitados en UI y se limpian también en backend.
            cleaned["documents_drive_url"] = ""
            cleaned["driver_license_ready"] = ""

        # El año de fundación pertenece a LSA independientemente de los documentos.
        if not cleaned.get("founding_year"):
            self.add_error("founding_year", "Registra el año de fundación de la empresa.")

        # Cuando LSA se marca completo, las métricas de control también deben existir.
        if verification == "complete":
            if cleaned.get("weekly_cost") is None:
                self.add_error("weekly_cost", "Registra el costo por semana para completar la validación LSA.")
            if cleaned.get("leads_last_7_days") is None:
                self.add_error("leads_last_7_days", "Registra la cantidad de leads de los últimos 7 días.")

        # Social Media controla directamente el tipo de seguimiento.
        if has_social == "yes":
            cleaned["followup_mode"] = "weekly"
            cleaned["custom_followup_date"] = None
            if not cleaned.get("followup_start_date"):
                self.add_error("followup_start_date", "Selecciona la primera fecha de revisión semanal.")
        elif has_social == "no":
            cleaned["followup_mode"] = "custom"
            cleaned["followup_start_date"] = None
            if not cleaned.get("custom_followup_date"):
                self.add_error("custom_followup_date", "Selecciona la fecha del recordatorio personalizado.")
        else:
            cleaned["followup_mode"] = "none"
            cleaned["followup_start_date"] = None
            cleaned["custom_followup_date"] = None
            self.add_error("has_social_media", "Selecciona Sí o No para Social Media.")

        # Fotos LSA cada 15 días.
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
            # Cuando la plataforma no se trabaja, todo lo dependiente queda limpio y cerrado.
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
            # Meta no usa el check de Términos en este flujo.
            cleaned["terms_accepted"] = ""
        elif self.platform in {"google", "tiktok"}:
            self._require_choice(cleaned, "terms_accepted")
            if not (cleaned.get("account_id") or "").strip():
                self.add_error("account_id", "Registra el ID de la cuenta.")
            # Campos exclusivos de Meta no deben quedar activos en Google/TikTok.
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


class SocialMediaDailyLogForm(forms.ModelForm):
    class Meta:
        model = SocialMediaDailyLog
        fields = ["date", "follow_up", "publication", "post_url", "notes"]
        widgets = {"date": DATE, "notes": TEXTAREA_2}
