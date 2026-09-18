from django import forms
from django.db.models import Q

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.plans.models import ServicePlan
from .models import ContactAttempt, FollowUp, Lead, SalesMeeting


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


class ContactAttemptForm(forms.ModelForm):
    create_follow_up = forms.BooleanField(required=False, label="Crear próximo seguimiento")
    follow_up_at = forms.DateTimeField(required=False, label="Fecha y hora", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    follow_up_type = forms.ChoiceField(required=False, choices=FollowUp.ContactType.choices, label="Tipo de seguimiento")

    class Meta:
        model = ContactAttempt
        fields = ["channel", "result", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Qué ocurrió en este contacto..."})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("create_follow_up") and not cleaned.get("follow_up_at"):
            self.add_error("follow_up_at", "Selecciona cuándo debe realizarse el próximo seguimiento.")
        return cleaned


class FollowUpForm(forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = ["due_at", "contact_type", "notes"]
        widgets = {
            "due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Objetivo o contexto del seguimiento..."}),
        }


class SalesMeetingForm(forms.ModelForm):
    class Meta:
        model = SalesMeeting
        fields = ["scheduled_at", "meeting_type", "result"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "meeting_type": forms.TextInput(attrs={"placeholder": "Google Meet, Zoom, llamada..."}),
            "result": forms.Textarea(attrs={"rows": 3, "placeholder": "Notas opcionales para preparar el meet..."}),
        }


class AgendaFollowUpForm(FollowUpForm):
    lead = forms.ModelChoiceField(queryset=Lead.objects.none(), label="Lead")
    assigned_to = forms.ModelChoiceField(queryset=UserAccount.objects.none(), label="Responsable")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        leads = Lead.objects.select_related("assigned_to")
        if user and not (user.is_manager or user.is_superuser):
            leads = leads.filter(assigned_to=user)
        self.fields["lead"].queryset = leads.order_by("first_name", "last_name")
        sellers = UserAccount.objects.filter(Q(role="sales") | Q(role="manager"), is_active=True).order_by("first_name", "last_name", "email")
        self.fields["assigned_to"].queryset = sellers
        if user and getattr(user, "role", None) == "sales":
            self.fields["assigned_to"].initial = user
            self.fields["assigned_to"].disabled = True


class AgendaMeetingForm(SalesMeetingForm):
    lead = forms.ModelChoiceField(queryset=Lead.objects.none(), label="Lead")
    seller = forms.ModelChoiceField(queryset=UserAccount.objects.none(), label="Responsable")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        leads = Lead.objects.select_related("assigned_to")
        if user and not (user.is_manager or user.is_superuser):
            leads = leads.filter(assigned_to=user)
        self.fields["lead"].queryset = leads.order_by("first_name", "last_name")
        sellers = UserAccount.objects.filter(Q(role="sales") | Q(role="manager"), is_active=True).order_by("first_name", "last_name", "email")
        self.fields["seller"].queryset = sellers
        if user and getattr(user, "role", None) == "sales":
            self.fields["seller"].initial = user
            self.fields["seller"].disabled = True


class LeadConversionForm(forms.Form):
    CLIENT_MODE_NEW = "new"
    CLIENT_MODE_EXISTING = "existing"
    CLIENT_MODE_CHOICES = (
        (CLIENT_MODE_EXISTING, "Usar cliente existente"),
        (CLIENT_MODE_NEW, "Crear cliente nuevo"),
    )

    client_mode = forms.ChoiceField(
        choices=CLIENT_MODE_CHOICES,
        widget=forms.RadioSelect,
        label="Cliente",
        initial=CLIENT_MODE_NEW,
    )
    existing_client = forms.ModelChoiceField(
        queryset=Client.objects.none(), required=False, label="Cliente existente", empty_label="Selecciona un cliente"
    )
    business_name = forms.CharField(max_length=180, label="Nombre de la empresa / cliente")
    project_name = forms.CharField(max_length=180, label="Nombre del proyecto")
    service_plans = forms.ModelMultipleChoiceField(
        queryset=ServicePlan.objects.none(), required=True, label="Servicios vendidos",
        widget=forms.CheckboxSelectMultiple(),
    )
    sale_value = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        min_value=0,
        label="Valor total vendido",
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
    )

    def __init__(self, *args, lead=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.lead = lead
        matches = Client.objects.none()
        if lead:
            query = Q()
            if lead.email:
                query |= Q(email__iexact=lead.email)
            if lead.phone:
                query |= Q(phone__iexact=lead.phone)
            if query:
                matches = Client.objects.filter(query).distinct().order_by("business_name")
            base_name = lead.company or lead.full_name or f"Lead {lead.pk}"
            self.fields["business_name"].initial = base_name
            self.fields["project_name"].initial = f"{base_name} · Venta"
        self.fields["existing_client"].queryset = matches
        self.fields["service_plans"].queryset = ServicePlan.objects.filter(is_active=True).order_by("department", "service_type", "name")
        if matches.exists():
            self.fields["client_mode"].initial = self.CLIENT_MODE_EXISTING
            self.fields["existing_client"].initial = matches.first()
        else:
            self.fields["client_mode"].choices = ((self.CLIENT_MODE_NEW, "Crear cliente nuevo"),)
            self.fields["client_mode"].initial = self.CLIENT_MODE_NEW

    @property
    def service_groups(self):
        groups = []
        current_key = None
        current = None
        for plan in self.fields["service_plans"].queryset:
            if plan.department != current_key:
                current_key = plan.department
                current = {"key": plan.department, "label": plan.get_department_display(), "plans": []}
                groups.append(current)
            current["plans"].append(plan)
        return groups

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("client_mode") or self.CLIENT_MODE_NEW
        existing = cleaned.get("existing_client")
        business_name = (cleaned.get("business_name") or "").strip()

        if mode == self.CLIENT_MODE_EXISTING:
            if not existing:
                self.add_error("existing_client", "Selecciona el cliente existente que deseas reutilizar.")
            else:
                cleaned["business_name"] = existing.business_name
        else:
            cleaned["existing_client"] = None
            if not business_name:
                self.add_error("business_name", "Ingresa el nombre de la empresa o cliente.")

        if not cleaned.get("service_plans"):
            self.add_error("service_plans", "Selecciona al menos un servicio vendido.")
        return cleaned
