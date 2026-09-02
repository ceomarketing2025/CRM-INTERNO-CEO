from django import forms
from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "first_name", "last_name", "identity_document", "business_name", "email", "phone",
            "website", "industry", "country", "state_region", "city", "address", "source", "status", "notes"
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}
