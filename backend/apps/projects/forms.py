from django import forms

from apps.plans.models import ServicePlan
from apps.plans.models.choices import PlanDepartment
from .models import Project, ProjectAssignment, ProjectNote, ProjectPlanAssignment

class PlanMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} · {obj.get_service_type_display()} · ${obj.base_price} {obj.currency}"


class ProjectForm(forms.ModelForm):
    administration_plans = PlanMultipleChoiceField(
        queryset=ServicePlan.objects.none(), required=False, label="Administración"
    )
    design_plans = PlanMultipleChoiceField(
        queryset=ServicePlan.objects.none(), required=False, label="Diseño"
    )
    marketing_plans = PlanMultipleChoiceField(
        queryset=ServicePlan.objects.none(), required=False, label="Marketing"
    )
    development_plans = PlanMultipleChoiceField(
        queryset=ServicePlan.objects.none(), required=False, label="Sitios web / Desarrollo"
    )

    PLAN_FIELDS = {
        "administration_plans": PlanDepartment.ADMINISTRATION,
        "design_plans": PlanDepartment.DESIGN,
        "marketing_plans": PlanDepartment.MARKETING,
        "development_plans": PlanDepartment.DEVELOPMENT,
    }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["status"].choices = [
            ("active", "Activo"),
            ("paused", "Pausado"),
            ("completed", "Completado"),
            ("cancelled", "Cancelado"),
        ]
        for field_name, department in self.PLAN_FIELDS.items():
            self.fields[field_name].queryset = ServicePlan.objects.filter(
                department=department, is_active=True
            ).order_by("service_type", "name")
            self.fields[field_name].widget = forms.CheckboxSelectMultiple()

        if self.instance and self.instance.pk:
            assignments = self.instance.contracted_plans.select_related("plan").filter(is_active=True)
            by_department = {}
            for assignment in assignments:
                by_department.setdefault(assignment.plan.department, []).append(assignment.plan_id)
            for field_name, department in self.PLAN_FIELDS.items():
                self.fields[field_name].initial = by_department.get(department, [])

    class Meta:
        model = Project
        fields = [
            "client", "name", "project_type", "status", "priority",
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
            "project_type": "Tipo principal",
            "start_date": "Fecha de inicio",
            "due_date": "Fecha objetivo",
        }

    def save(self, commit=True):
        project = super().save(commit=commit)
        if commit:
            self.save_plan_assignments(project)
        return project

    def save_plan_assignments(self, project):
        selected_ids = set()
        for field_name in self.PLAN_FIELDS:
            for plan in self.cleaned_data.get(field_name, []):
                selected_ids.add(plan.pk)
                ProjectPlanAssignment.objects.update_or_create(
                    project=project,
                    plan=plan,
                    defaults={
                        "agreed_price": plan.base_price,
                        "is_active": True,
                        "created_by": self.user if getattr(self.user, "is_authenticated", False) else None,
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
