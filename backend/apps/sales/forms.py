from django import forms
from django.db.models import Q

from apps.accounts.models import UserAccount
from .models import Lead


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "first_name", "last_name", "phone", "email", "city", "state_region", "zip_code", "country",
            "company", "interested_service", "source", "campaign", "budget", "comments", "assigned_to", "status", "quality",
        ]
        widgets = {"comments": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(Q(role="sales") | Q(role="manager"), is_active=True).order_by("first_name", "last_name", "email")
        if user and getattr(user, "role", None) == "sales":
            self.fields["assigned_to"].initial = user
            self.fields["assigned_to"].disabled = True

    def clean(self):
        cleaned = super().clean()
        phone = (cleaned.get("phone") or "").strip()
        email = (cleaned.get("email") or "").strip()
        if not phone and not email:
            raise forms.ValidationError("Ingresa al menos un teléfono o un email.")
        duplicates = Lead.objects.none()
        if phone and email:
            duplicates = Lead.objects.filter(Q(phone__iexact=phone) | Q(email__iexact=email))
        elif phone:
            duplicates = Lead.objects.filter(phone__iexact=phone)
        elif email:
            duplicates = Lead.objects.filter(email__iexact=email)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError("Ya existe un lead con ese teléfono o email. Revisa el registro antes de crear un duplicado.")
        return cleaned
