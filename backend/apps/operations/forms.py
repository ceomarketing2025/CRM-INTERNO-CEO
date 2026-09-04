from django import forms
from apps.accounts.models import UserAccount
from .models import CredentialPurchase, GeneralManagementRecord, ProductionRecord


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
