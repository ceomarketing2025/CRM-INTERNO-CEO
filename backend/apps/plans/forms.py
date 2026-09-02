from django import forms
from .models import ClientPlan, ServicePlan
class ServicePlanForm(forms.ModelForm):
    class Meta:
        model = ServicePlan
        fields = ["name", "code", "service_type", "description", "base_price", "currency", "billing_cycle", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
class ClientPlanForm(forms.ModelForm):
    class Meta:
        model = ClientPlan
        fields = ["client", "plan", "agreed_price", "currency", "purchase_date", "start_date", "renewal_date", "end_date", "status", "payment_status", "notes"]
        widgets = {k: forms.DateInput(attrs={"type": "date"}) for k in ["purchase_date", "start_date", "renewal_date", "end_date"]} | {"notes": forms.Textarea(attrs={"rows": 3})}
