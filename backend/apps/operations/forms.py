from django import forms
from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.projects.models import Project
from .models import (
    CredentialPurchase,
    CredentialType,
    DomainHostingRecord,
    DomainOperationType,
    DomainRecordStatus,
    GeneralManagementRecord,
    HostingProvider,
    ProductionRecord,
    ProjectCredential,
)


class ClientProjectChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        person = obj.full_name or "Sin nombre"
        return f"{person} · {obj.business_name}"


class DateInput(forms.DateInput):
    input_type = "date"


class GeneralManagementRecordForm(forms.ModelForm):
    class Meta:
        model = GeneralManagementRecord
        fields = ["date", "client", "detail_name", "service_type", "provider", "cost", "currency", "status", "receipt_drive_url", "responsible", "notes"]
        widgets = {"date": DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].required = True
        self.fields["client"].empty_label = "Selecciona un cliente"


class CredentialPurchaseForm(forms.ModelForm):
    class Meta:
        model = CredentialPurchase
        fields = ["client", "project", "credential_name", "provider", "purchase_date", "renewal_date", "cost", "currency", "account_email", "secure_reference_url", "receipt_drive_url", "active", "notes"]
        widgets = {"purchase_date": DateInput(), "renewal_date": DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}


class DomainHostingRecordForm(forms.ModelForm):
    client = ClientProjectChoiceField(queryset=Client.objects.none(), label="Cliente")

    class Meta:
        model = DomainHostingRecord
        fields = [
            "operation_type", "client", "project", "domain_name", "start_date",
            "domain_expiry_date", "domain_status", "domain_cost", "domain_receipt_drive_url",
            "server_provider", "server_provider_other", "server_cost",
            "server_receipt_drive_url", "currency", "notes",
        ]
        widgets = {
            "start_date": DateInput(),
            "domain_expiry_date": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.order_by("first_name", "last_name", "business_name")
        self.fields["client"].empty_label = "Selecciona un cliente"
        self.fields["project"].empty_label = "Selecciona un proyecto"
        client_id = self.data.get("client") or getattr(self.instance, "client_id", None) or self.initial.get("client")
        projects = Project.objects.none()
        if str(client_id or "").isdigit():
            projects = Project.objects.filter(client_id=int(client_id)).order_by("-created_at")
        self.fields["project"].queryset = projects

        operation = self.data.get("operation_type") or getattr(self.instance, "operation_type", None) or self.initial.get("operation_type") or DomainOperationType.NEW
        current_status = self.data.get("domain_status") or getattr(self.instance, "domain_status", None) or self.initial.get("domain_status")
        if operation == DomainOperationType.MIGRATION:
            choices = [
                (DomainRecordStatus.PENDING_MIGRATION, "Pendiente de migración"),
                (DomainRecordStatus.MIGRATED, "Migrado"),
            ]
            if current_status in {DomainRecordStatus.LEGACY_PENDING, DomainRecordStatus.PENDING_PURCHASE}:
                self.initial["domain_status"] = DomainRecordStatus.PENDING_MIGRATION
            elif current_status in {DomainRecordStatus.LEGACY_READY, DomainRecordStatus.PURCHASED}:
                self.initial["domain_status"] = DomainRecordStatus.MIGRATED
        elif operation == DomainOperationType.EXISTING:
            choices = [(DomainRecordStatus.PURCHASED, "Comprado y registrado")]
            self.initial["domain_status"] = DomainRecordStatus.PURCHASED
        else:
            choices = [
                (DomainRecordStatus.PENDING_PURCHASE, "Pendiente de compra"),
                (DomainRecordStatus.PURCHASED, "Comprado y registrado"),
            ]
            if current_status == DomainRecordStatus.LEGACY_PENDING:
                self.initial["domain_status"] = DomainRecordStatus.PENDING_PURCHASE
            elif current_status in {DomainRecordStatus.LEGACY_READY, DomainRecordStatus.MIGRATED}:
                self.initial["domain_status"] = DomainRecordStatus.PURCHASED
        self.fields["domain_status"].choices = choices

        self.fields["server_provider_other"].help_text = "Solo si seleccionas Otro."
        self.fields["domain_receipt_drive_url"].help_text = "Recibo/factura de compra o renovación del dominio."
        self.fields["server_receipt_drive_url"].help_text = "Recibo/factura del hosting o servidor."

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get("client")
        project = cleaned.get("project")
        operation = cleaned.get("operation_type")
        status = cleaned.get("domain_status")
        provider = cleaned.get("server_provider")
        other = (cleaned.get("server_provider_other") or "").strip()
        if client and project and project.client_id != client.pk:
            self.add_error("project", "Solo puedes seleccionar proyectos del cliente elegido.")
        if provider == HostingProvider.OTHER and not other:
            self.add_error("server_provider_other", "Ingresa el nombre del proveedor.")

        allowed = {
            DomainOperationType.NEW: {DomainRecordStatus.PENDING_PURCHASE, DomainRecordStatus.PURCHASED},
            DomainOperationType.EXISTING: {DomainRecordStatus.PURCHASED},
            DomainOperationType.MIGRATION: {DomainRecordStatus.PENDING_MIGRATION, DomainRecordStatus.MIGRATED},
        }.get(operation, set())
        if status and status not in allowed:
            self.add_error("domain_status", "Selecciona un estado válido para el tipo de registro.")
        return cleaned


class ProjectCredentialForm(forms.ModelForm):
    client = ClientProjectChoiceField(queryset=Client.objects.none(), label="Cliente")
    password = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Se cifra antes de guardarse. Si editas y la dejas vacía, se conserva la actual.",
    )

    class Meta:
        model = ProjectCredential
        fields = [
            "client", "project", "credential_type", "custom_name", "account_email",
            "login_url", "enabled", "visible_to_team", "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.order_by("first_name", "last_name", "business_name")
        self.fields["client"].empty_label = "Selecciona un cliente"
        self.fields["project"].empty_label = "Selecciona un proyecto"
        main_types = [CredentialType.GOOGLE, CredentialType.SERVER, CredentialType.WORDPRESS, CredentialType.META, CredentialType.YOUTUBE, CredentialType.TIKTOK, CredentialType.OTHER]
        choices = [(value, dict(CredentialType.choices)[value]) for value in main_types]
        if self.instance.pk and self.instance.credential_type not in main_types:
            choices.append((self.instance.credential_type, self.instance.get_credential_type_display()))
        self.fields["credential_type"].choices = choices
        client_id = self.data.get("client") or getattr(self.instance, "client_id", None) or self.initial.get("client")
        projects = Project.objects.none()
        if str(client_id or "").isdigit():
            projects = Project.objects.filter(client_id=int(client_id)).order_by("-created_at")
        self.fields["project"].queryset = projects
        if not getattr(user, "is_manager", False):
            self.fields["visible_to_team"].disabled = True
            self.fields["visible_to_team"].help_text = "Solo Gerencia puede habilitar la visibilidad de credenciales en el resumen del proyecto."
        else:
            self.fields["visible_to_team"].help_text = "Al activarlo, las áreas con acceso al proyecto podrán ver esta credencial en el Resumen."
        self.fields["password"].required = False
        self.fields["password"].help_text = "Opcional mientras se completa el acceso. Si editas y la dejas vacía, se conserva la actual."

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get("client")
        project = cleaned.get("project")
        if client and project and project.client_id != client.pk:
            self.add_error("project", "Solo puedes seleccionar proyectos del cliente elegido.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        raw_password = self.cleaned_data.get("password")
        if raw_password:
            obj.set_password(raw_password)
        if not getattr(self.user, "is_manager", False) and obj.pk:
            previous = ProjectCredential.objects.filter(pk=obj.pk).values_list("visible_to_team", flat=True).first()
            if previous is not None:
                obj.visible_to_team = previous
        elif not getattr(self.user, "is_manager", False):
            obj.visible_to_team = False
        if commit:
            obj.save()
        return obj


class ProductionRecordForm(forms.ModelForm):
    class Meta:
        model = ProductionRecord
        fields = ["client", "reference", "project", "project_site", "plan_start", "design_status", "tech_status", "status", "collaborator", "notes", "cost", "advance", "website_url"]
        widgets = {"plan_start": DateInput(), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["collaborator"].queryset = UserAccount.objects.filter(role__in=[UserAccount.Role.DEVELOPER, UserAccount.Role.MANAGER], is_active=True).order_by("first_name", "last_name", "email")

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get("project")
        client = cleaned.get("client")
        if project and client and project.client_id != client.pk:
            self.add_error("project", "El proyecto seleccionado debe pertenecer al cliente.")
        return cleaned


class WebProductionStructureForm(forms.Form):
    main_page_target = forms.IntegerField(
        min_value=0,
        max_value=100,
        label="Páginas principales",
        initial=8,
        help_text="Por defecto se preparan 8. Si aumentas el número se crean los espacios faltantes.",
    )
    county_target = forms.IntegerField(
        min_value=0,
        max_value=100,
        label="Condados",
        initial=0,
        help_text="Ej.: 7 crea siete bloques de condado.",
    )
    services_per_county_target = forms.IntegerField(
        min_value=0,
        max_value=50,
        label="Servicios por condado",
        initial=0,
        help_text="Ej.: 3 crea tres espacios de servicio debajo de cada condado.",
    )
    cities_per_county_target = forms.IntegerField(
        min_value=0,
        max_value=100,
        label="Ciudades por condado",
        initial=0,
        help_text="Ej.: 5 crea cinco espacios de ciudad dentro de cada condado.",
    )
