from django import forms

from apps.plans.models import ServicePlan
from apps.plans.models.choices import ServiceType
from .models import Project, ProjectAssignment, ProjectNote, ProjectPlanAssignment


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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["status"].choices = [
            ("active", "Activo"),
            ("paused", "Pausado"),
            ("completed", "Completado"),
            ("cancelled", "Cancelado"),
        ]
        self.fields["service_plans"].queryset = ServicePlan.objects.filter(
            is_active=True
        ).order_by("department", "service_type", "name")

        if self.instance and self.instance.pk:
            self.fields["service_plans"].initial = list(
                self.instance.contracted_plans.filter(is_active=True).values_list("plan_id", flat=True)
            )

    class Meta:
        model = Project
        fields = [
            "client", "name", "status", "priority",
            "start_date", "due_date", "summary", "internal_notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 3, "placeholder": "Resumen general del proyecto..."}),
            "internal_notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Notas internas..."}),
        }
        labels = {
            "name": "Nombre del proyecto",
            "start_date": "Fecha de inicio",
            "due_date": "Fecha objetivo",
        }

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
