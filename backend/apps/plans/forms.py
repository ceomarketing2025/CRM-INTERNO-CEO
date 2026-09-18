from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import UserAccount
from apps.projects.models import Project
from .models import ClientPlan, ServicePlan
from .models.choices import (
    ClientPlanStatus,
    PlanDepartment,
    RenewalFrequency,
    ServiceType,
    service_type_choices_for_department,
)
from .services import current_cycle_bounds


SOCIAL_NETWORK_CHOICES = [
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("youtube", "YouTube"),
    ("x", "X / Twitter"),
    ("linkedin", "LinkedIn"),
    ("google_business", "Google Business"),
    ("pinterest", "Pinterest"),
]

ROLE_TO_DEPARTMENT = {
    UserAccount.Role.ADMINISTRATION: PlanDepartment.ADMINISTRATION,
    UserAccount.Role.DESIGN: PlanDepartment.DESIGN,
    UserAccount.Role.MARKETING: PlanDepartment.MARKETING,
    UserAccount.Role.DEVELOPER: PlanDepartment.DEVELOPMENT,
}


class ServicePlanForm(forms.ModelForm):
    class Meta:
        model = ServicePlan
        fields = [
            "name", "department", "service_type", "weekly_posts", "weekly_videos",
            "website_pages", "branding_pages", "scope_range", "base_price", "currency",
            "billing_cycle", "description", "is_active",
        ]
        widgets = {
            "weekly_posts": forms.NumberInput(attrs={"min": 0}),
            "weekly_videos": forms.NumberInput(attrs={"min": 0}),
            "website_pages": forms.NumberInput(attrs={"min": 0}),
            "branding_pages": forms.NumberInput(attrs={"min": 0}),
            "base_price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Notas o alcance del producto..."}),
            "scope_range": forms.TextInput(attrs={"placeholder": "Ej.: 8 a 12 páginas / alcance personalizado"}),
        }
        labels = {
            "weekly_posts": "Cantidad de posts",
            "weekly_videos": "Cantidad de videos",
            "website_pages": "Cantidad de páginas",
            "branding_pages": "Cantidad de branding pages",
            "scope_range": "Rango / alcance",
            "base_price": "Costo",
            "is_active": "Plan activo",
        }

    def __init__(self, *args, user=None, forced_department=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.forced_department = forced_department
        role = getattr(user, "role", None)

        department = forced_department
        if not department and user and not (user.is_manager or user.is_superuser):
            department = ROLE_TO_DEPARTMENT.get(role)

        if department:
            self.fields["department"].initial = department
            self.fields["department"].widget = forms.HiddenInput()
            self.fields["service_type"].choices = service_type_choices_for_department(department)
        elif self.instance and self.instance.pk:
            self.fields["service_type"].choices = service_type_choices_for_department(self.instance.department)
        else:
            # Gerencia puede seleccionar cualquier área. El template filtra visualmente las categorías.
            self.fields["service_type"].choices = ServiceType.choices

        if self.instance and self.instance.pk:
            self.fields["service_type"].initial = self.instance.service_type

    def clean(self):
        cleaned = super().clean()
        department = cleaned.get("department")
        if self.forced_department:
            department = self.forced_department
            cleaned["department"] = department
        elif self.user and not (self.user.is_manager or self.user.is_superuser):
            department = ROLE_TO_DEPARTMENT.get(getattr(self.user, "role", None))
            cleaned["department"] = department

        service_type = cleaned.get("service_type")
        allowed_values = {value for value, _ in service_type_choices_for_department(department)} if department else set()
        if department and service_type not in allowed_values:
            self.add_error("service_type", "Esta categoría no pertenece al área seleccionada.")

        if service_type == ServiceType.SOCIAL_MEDIA:
            if not (cleaned.get("weekly_posts") or cleaned.get("weekly_videos")):
                raise forms.ValidationError("Un plan Social Media debe incluir al menos 1 post o 1 video.")
        else:
            cleaned["weekly_posts"] = 0
            cleaned["weekly_videos"] = 0

        web_types = {
            ServiceType.WEBSITE,
            ServiceType.LANDING_PAGE,
            ServiceType.ECOMMERCE,
            ServiceType.WEBSITE_MAINTENANCE,
            ServiceType.SEO,
            ServiceType.SOFTWARE,
            ServiceType.OTHER_WEB,
        }
        if service_type not in web_types:
            cleaned["website_pages"] = 0
            cleaned["branding_pages"] = 0
            cleaned["scope_range"] = ""
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.code:
            base = slugify(instance.name)[:65] or "plan"
            code = base
            counter = 2
            qs = ServicePlan.objects.exclude(pk=instance.pk) if instance.pk else ServicePlan.objects.all()
            while qs.filter(code=code).exists():
                code = f"{base}-{counter}"[:80]
                counter += 1
            instance.code = code
        if commit:
            instance.full_clean()
            instance.save()
        return instance


class SocialMediaAssignmentForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        required=True,
        label="Proyecto",
        help_text="Selecciona el proyecto al que pertenece esta suscripción.",
    )
    social_networks = forms.MultipleChoiceField(
        choices=SOCIAL_NETWORK_CHOICES,
        required=True,
        widget=forms.CheckboxSelectMultiple,
        label="Redes sociales donde se publicará",
    )

    class Meta:
        model = ClientPlan
        fields = [
            "client", "plan", "start_date", "renewal_frequency", "renewal_date", "social_networks",
            "notes", "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "renewal_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Notas internas del plan, acuerdos o detalles importantes..."}),
        }
        labels = {
            "client": "Cliente",
            "plan": "Plan de Social Media",
            "start_date": "Fecha de inicio",
            "renewal_frequency": "¿Cada cuánto se renueva?",
            "renewal_date": "Fecha de renovación",
            "is_active": "Suscripción activa",
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.bound_project = project

        # Social Media NO crea cantidades aquí. El catálogo de Planes es la
        # única fuente de verdad para posts/videos por ciclo.
        self.fields["plan"].queryset = ServicePlan.objects.filter(
            service_type=ServiceType.SOCIAL_MEDIA,
            department=PlanDepartment.DESIGN,
            is_active=True,
        ).order_by("name")
        self.fields["plan"].label_from_instance = (
            lambda obj: f"{obj.name} · {obj.content_goal_label}"
        )
        self.fields["plan"].help_text = (
            "La cantidad de posts y videos se toma del plan creado en Planes; no se define en esta pantalla."
        )

        # Proyecto depende SIEMPRE del cliente seleccionado. En un GET nuevo no
        # cargamos todos los proyectos; en POST filtramos el queryset antes de
        # validar para impedir asociaciones cruzadas también desde backend.
        selected_client_id = None
        if project:
            selected_client_id = project.client_id
        elif self.is_bound:
            raw_client_id = self.data.get(self.add_prefix("client")) or self.data.get("client")
            if str(raw_client_id or "").isdigit():
                selected_client_id = int(raw_client_id)
        elif self.instance and self.instance.pk:
            selected_client_id = self.instance.client_id
        else:
            initial_client = self.initial.get("client")
            selected_client_id = getattr(initial_client, "pk", initial_client)
            if not str(selected_client_id or "").isdigit():
                selected_client_id = None

        project_qs = Project.objects.select_related("client")
        if selected_client_id:
            project_qs = project_qs.filter(client_id=selected_client_id).order_by("-created_at")
        else:
            project_qs = Project.objects.none()
        self.fields["project"].queryset = project_qs
        self.fields["project"].empty_label = (
            "Selecciona un proyecto" if selected_client_id else "Selecciona primero un cliente"
        )

        if project:
            self.fields["project"].initial = project
            self.fields["project"].widget = forms.HiddenInput()
            self.fields["client"].initial = project.client
            self.fields["client"].widget = forms.HiddenInput()
            # Si el proyecto ya tiene un plan Social Media contratado, priorizar
            # esos planes sin fabricar uno nuevo desde esta pantalla.
            contracted_ids = project.contracted_plans.filter(
                plan__department=PlanDepartment.DESIGN,
                plan__service_type=ServiceType.SOCIAL_MEDIA,
                is_active=True,
            ).values_list("plan_id", flat=True)
            contracted_qs = self.fields["plan"].queryset.filter(pk__in=contracted_ids)
            if contracted_qs.exists():
                self.fields["plan"].queryset = contracted_qs
        elif self.instance and self.instance.pk:
            linked = self.instance.project_links.select_related("project").first()
            if linked:
                self.fields["project"].initial = linked.project

        if self.instance and self.instance.pk:
            self.fields["social_networks"].initial = self.instance.social_networks or []
        else:
            self.fields["start_date"].initial = timezone.localdate()
            self.fields["renewal_frequency"].initial = RenewalFrequency.MONTHLY
            self.fields["is_active"].initial = True

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get("project") or self.bound_project
        client = cleaned.get("client")
        start_date = cleaned.get("start_date")
        renewal_date = cleaned.get("renewal_date")
        if project and client and project.client_id != client.pk:
            self.add_error("project", "El proyecto seleccionado pertenece a otro cliente.")
        if start_date and renewal_date and renewal_date <= start_date:
            self.add_error("renewal_date", "La fecha de renovación debe ser posterior a la fecha de inicio.")
        return cleaned

    def clean_plan(self):
        plan = self.cleaned_data["plan"]
        if plan.service_type != ServiceType.SOCIAL_MEDIA or plan.department != PlanDepartment.DESIGN:
            raise forms.ValidationError("Selecciona un plan Social Media del área de Diseño.")
        return plan

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.bound_project:
            instance.client = self.bound_project.client
        instance.social_networks = self.cleaned_data.get("social_networks", [])
        instance.status = ClientPlanStatus.ACTIVE if instance.is_active else ClientPlanStatus.PAUSED
        instance.purchase_date = instance.purchase_date or timezone.localdate()
        if instance.plan_id:
            instance.agreed_price = instance.plan.base_price
            instance.currency = instance.plan.currency
        configured_renewal = self.cleaned_data.get("renewal_date")
        if configured_renewal:
            instance.renewal_date = configured_renewal
        else:
            _, due = current_cycle_bounds(instance.start_date or timezone.localdate(), instance.renewal_frequency)
            instance.renewal_date = due
        if commit:
            instance.save()
        return instance


class ClientPlanForm(SocialMediaAssignmentForm):
    pass
