from django import forms
from apps.plans.models import ServicePlan


class WebsiteClientIntakeForm(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=100)
    last_name = forms.CharField(label="Apellido", max_length=100)
    identity_document = forms.CharField(label="ID / identificación (opcional)", max_length=80, required=False)
    phone = forms.CharField(label="Número de teléfono", max_length=40)
    email = forms.EmailField(label="Correo (opcional)", required=False)
    business_name = forms.CharField(label="Nombre de la empresa", max_length=180)
    plan = forms.ModelChoiceField(label="Plan de página web", queryset=ServicePlan.objects.none(), empty_label=None)
    notes = forms.CharField(label="Nota administrativa", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = ServicePlan.objects.filter(service_type="website", is_active=True).order_by("base_price")
        self.fields["plan"].label_from_instance = lambda obj: f"{obj.name} - ${obj.base_price:,.0f}"
