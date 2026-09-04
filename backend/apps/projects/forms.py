from django import forms
from django.contrib.auth import get_user_model

from apps.plans.models import ServicePlan
from apps.plans.models.choices import BillingCycle, ServiceType
from .models import Project, ProjectAssignment, ProjectNote, ProjectPlanAssignment
from .models.choices import AssignmentArea, AssignmentStatus


class PlanMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} · {obj.get_service_type_display()} · ${obj.base_price} {obj.currency}"


class ProjectForm(forms.ModelForm):
    """Proyecto + servicios contratados en una sola selección multiárea.

    `project_type` se conserva en el modelo únicamente por compatibilidad histórica;
    la interfaz ya no obliga a escoger un único tipo. El tipo legado se infiere de
    los productos contratados para que los módulos antiguos sigan funcionando.
    """

    service_plans = PlanMultipleChoiceField(
        queryset=ServicePlan.objects.none(),
        required=False,
        label="Servicios contratados",
        widget=forms.CheckboxSelectMultiple(),
    )
    design_responsible = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Responsable de Diseño",
        empty_label="Sin asignar",
    )
    marketing_responsible = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Responsable de Marketing",
        empty_label="Sin asignar",
    )
    development_responsible = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Responsable de Desarrollo",
        empty_label="Sin asignar",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["status"].choices = [
            ("in_development", "En desarrollo"),
            ("active", "Activo"),
            ("completed", "Completado"),
            ("paused", "Pausado"),
            ("cancelled", "Cancelado"),
        ]
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.fields["status"].initial = "in_development"
        self.fields["client"].widget.attrs.update({"class": "project-control-v11"})
        self.fields["name"].widget.attrs.update({
            "class": "project-control-v11",
            "placeholder": "Ej. Rediseño web + Social Media · Cliente",
            "autocomplete": "off",
        })
        self.fields["start_date"].widget.attrs.update({"class": "project-control-v11"})
        self.fields["internal_notes"].widget.attrs.update({"class": "project-control-v11"})
        self.fields["service_plans"].queryset = ServicePlan.objects.filter(
            is_active=True
        ).order_by("department", "service_type", "name")

        User = get_user_model()
        responsible_config = {
            "design_responsible": ("design", "Diseño"),
            "marketing_responsible": ("marketing", "Marketing"),
            "development_responsible": ("developer", "Desarrollo"),
        }
        for field_name, (role, area_label) in responsible_config.items():
            field = self.fields[field_name]
            field.queryset = User.objects.filter(
                is_active=True, role__in=[role, "manager"]
            ).order_by("first_name", "last_name", "email")
            field.widget.attrs.update({
                "class": "project-control-v11 responsible-select-v12",
                "data-area-label": area_label,
            })

        if self.instance and self.instance.pk:
            self.fields["service_plans"].initial = list(
                self.instance.contracted_plans.filter(is_active=True).values_list("plan_id", flat=True)
            )
            assignment_fields = {
                AssignmentArea.DESIGN: "design_responsible",
                AssignmentArea.MARKETING: "marketing_responsible",
                AssignmentArea.DEVELOPMENT: "development_responsible",
            }
            for area, field_name in assignment_fields.items():
                assignment = self.instance.assignments.filter(area=area).select_related("user").order_by("-updated_at").first()
                if assignment:
                    self.fields[field_name].initial = assignment.user_id

    class Meta:
        model = Project
        fields = [
            "client", "name", "status", "start_date", "internal_notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "internal_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "Notas internas, acuerdos, contexto o indicaciones para el equipo..."}),
        }
        labels = {
            "name": "Nombre del proyecto",
            "start_date": "Fecha de inicio",
        }

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        selected_plans = list(cleaned.get("service_plans") or [])
        has_subscription = any(
            plan.service_type == ServiceType.SOCIAL_MEDIA
            or plan.billing_cycle in {BillingCycle.MONTHLY, BillingCycle.YEARLY, BillingCycle.CUSTOM}
            for plan in selected_plans
        )
        if status == "active" and not has_subscription:
            self.add_error(
                "status",
                "Activo se usa para proyectos con una suscripción o servicio recurrente. Para trabajos de pago único usa En desarrollo y luego Completado.",
            )
        return cleaned

    def selected_service_plan_ids(self):
        """IDs seleccionados tanto en GET inicial como después de un POST inválido."""
        if self.is_bound:
            values = self.data.getlist("service_plans")
            return {int(value) for value in values if str(value).isdigit()}
        initial = self.fields["service_plans"].initial or []
        return {int(getattr(value, "pk", value)) for value in initial}

    def _infer_project_type(self, selected_plans):
        service_types = {plan.service_type for plan in selected_plans}
        if ServiceType.SOFTWARE in service_types:
            return "software"
        if service_types.intersection({ServiceType.WEBSITE, ServiceType.LANDING_PAGE, ServiceType.ECOMMERCE, ServiceType.WEBSITE_MAINTENANCE}):
            return "website"
        if ServiceType.SEO in service_types:
            return "seo"
        if ServiceType.SOCIAL_MEDIA in service_types:
            return "social_media"
        if service_types.intersection({ServiceType.BRANDING, ServiceType.GRAPHIC_DESIGN, ServiceType.JACKETS, ServiceType.CAPS, ServiceType.OTHER_DESIGN}):
            return "branding"
        return self.instance.project_type if self.instance and self.instance.pk else "other"

    def save(self, commit=True):
        project = super().save(commit=False)
        selected_plans = list(self.cleaned_data.get("service_plans", []))
        project.project_type = self._infer_project_type(selected_plans)
        if commit:
            project.save()
            self.save_plan_assignments(project, selected_plans=selected_plans)
            self.save_responsible_assignments(project)
        return project

    def save_plan_assignments(self, project, selected_plans=None):
        selected_plans = list(selected_plans if selected_plans is not None else self.cleaned_data.get("service_plans", []))
        selected_ids = {plan.pk for plan in selected_plans}
        actor = self.user if getattr(self.user, "is_authenticated", False) else None
        for plan in selected_plans:
            ProjectPlanAssignment.objects.update_or_create(
                project=project,
                plan=plan,
                defaults={
                    "agreed_price": plan.base_price,
                    "is_active": True,
                    "created_by": actor,
                },
            )
        project.contracted_plans.exclude(plan_id__in=selected_ids).update(is_active=False)

    def save_responsible_assignments(self, project):
        """Mantiene un único responsable principal por cada área operativa."""
        assignment_map = {
            AssignmentArea.DESIGN: ("design_responsible", "Responsable principal de Diseño"),
            AssignmentArea.MARKETING: ("marketing_responsible", "Responsable principal de Marketing"),
            AssignmentArea.DEVELOPMENT: ("development_responsible", "Responsable principal de Desarrollo"),
        }
        for area, (field_name, responsibility) in assignment_map.items():
            selected_user = self.cleaned_data.get(field_name)
            area_assignments = ProjectAssignment.objects.filter(project=project, area=area)
            if not selected_user:
                area_assignments.delete()
                continue

            # El modelo histórico permitía más de una persona por área. La nueva
            # regla conserva exactamente un responsable principal por área.
            area_assignments.exclude(user=selected_user).delete()
            assignment, _ = ProjectAssignment.objects.update_or_create(
                project=project,
                user=selected_user,
                area=area,
                defaults={
                    "status": AssignmentStatus.ASSIGNED,
                    "responsibility": responsibility,
                },
            )
            # Si existían duplicados históricos del mismo usuario/área, la constraint
            # ya los impide; esta asignación queda como la única vigente.
            assignment.status = AssignmentStatus.ASSIGNED
            assignment.responsibility = responsibility
            assignment.save(update_fields=["status", "responsibility", "updated_at"])


class ProjectAssignmentForm(forms.ModelForm):
    class Meta:
        model = ProjectAssignment
        fields = ["user", "area", "status", "responsibility"]

    def clean(self):
        cleaned = super().clean()
        user, area = cleaned.get("user"), cleaned.get("area")
        expected = {
            "administration": "administration",
            "marketing": "marketing",
            "design": "design",
            "development": "developer",
        }.get(area)
        if user and expected and user.role not in {expected, "manager"}:
            self.add_error("user", f"El usuario seleccionado no pertenece al área {area}.")
        return cleaned


class ProjectNoteForm(forms.ModelForm):
    class Meta:
        model = ProjectNote
        fields = ["note", "is_internal"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3, "placeholder": "Añadir nota al proyecto..."})}
