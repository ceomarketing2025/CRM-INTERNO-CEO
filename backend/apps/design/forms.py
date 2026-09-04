from django import forms
from .models import ColorPalette, DesignBrief, DesignTask, PaletteColor, PaletteGradient


class DesignBriefForm(forms.ModelForm):
    class Meta:
        model = DesignBrief
        exclude = ["project", "completed", "completed_at", "completed_by"]
        widgets = {
            "social_notes": forms.Textarea(attrs={"rows": 2}),
            "meeting_attendees": forms.Textarea(attrs={"rows": 2, "placeholder": "Ej.: Dakmar, Oscar..."}),
            "logo_change_notes": forms.Textarea(attrs={"rows": 3}),
            "visual_structure_notes": forms.Textarea(attrs={"rows": 3}),
            "color_base_notes": forms.Textarea(attrs={"rows": 2}),
            "services": forms.Textarea(attrs={"rows": 3}),
            "page_style_notes": forms.Textarea(attrs={"rows": 3}),
            "typography_direction": forms.Textarea(attrs={"rows": 2}),
            "layout_preferences": forms.Textarea(attrs={"rows": 3}),
            "visual_references": forms.Textarea(attrs={"rows": 3}),
            "elements_to_avoid": forms.Textarea(attrs={"rows": 2}),
            "designer_notes": forms.Textarea(attrs={"rows": 3}),
        }


class PaletteForm(forms.ModelForm):
    class Meta:
        model = ColorPalette
        fields = ["name", "description", "is_primary", "general_rules"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2}), "general_rules": forms.Textarea(attrs={"rows": 5})}


class PaletteColorForm(forms.ModelForm):
    class Meta:
        model = PaletteColor
        fields = ["role", "label", "hex_code", "usage", "order"]
        widgets = {"hex_code": forms.TextInput(attrs={"type": "color", "class": "color-input"})}


class PaletteGradientForm(forms.ModelForm):
    class Meta:
        model = PaletteGradient
        fields = ["name", "start_hex", "end_hex", "order"]
        widgets = {
            "start_hex": forms.TextInput(attrs={"type": "color", "class": "color-input"}),
            "end_hex": forms.TextInput(attrs={"type": "color", "class": "color-input"}),
        }


class PaletteQuickForm(forms.Form):
    text_hex = forms.CharField(label="Texto", initial="#000000", widget=forms.TextInput(attrs={"type": "color", "class": "palette-picker"}))
    background_hex = forms.CharField(label="Fondo", initial="#FFFFFF", widget=forms.TextInput(attrs={"type": "color", "class": "palette-picker"}))
    primary_hex = forms.CharField(label="Primario", initial="#0C3168", widget=forms.TextInput(attrs={"type": "color", "class": "palette-picker"}))
    secondary_hex = forms.CharField(label="Secundario", initial="#C9CBD1", widget=forms.TextInput(attrs={"type": "color", "class": "palette-picker"}))
    accent_hex = forms.CharField(label="Acento", initial="#2571B7", widget=forms.TextInput(attrs={"type": "color", "class": "palette-picker"}))
    general_rules = forms.CharField(label="Reglas generales", required=False, widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Una regla por línea. Si lo dejas vacío, el PDF usa las reglas estándar."}))


class DesignTaskForm(forms.ModelForm):
    class Meta:
        model = DesignTask
        fields = [
            "project_plan", "title", "description", "task_type",
            "recurrence_frequency", "recurrence_start_date",
            "status", "due_date", "assigned_to", "order",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "recurrence_start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "recurrence_frequency": "Control / renovación de contenido",
            "recurrence_start_date": "Fecha desde la que inicia el ciclo",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import UserAccount
        from apps.plans.models.choices import PlanDepartment
        from apps.projects.models import ProjectPlanAssignment
        from apps.projects.selectors import projects_for_area

        qs = ProjectPlanAssignment.objects.select_related("project__client", "plan").filter(
            is_active=True,
            plan__department=PlanDepartment.DESIGN,
        )
        if user is not None and not getattr(user, "is_manager", False) and not getattr(user, "is_superuser", False):
            visible_ids = projects_for_area("design").values_list("pk", flat=True)
            qs = qs.filter(project_id__in=visible_ids)
        self.fields["project_plan"].queryset = qs.order_by("project__client__business_name", "plan__name")
        self.fields["project_plan"].label_from_instance = lambda obj: f"{obj.project.project_code} · {obj.project.client.business_name} · {obj.plan.name}"
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(
            is_active=True,
            role__in=[UserAccount.Role.DESIGN, UserAccount.Role.MANAGER],
        ).order_by("first_name", "last_name", "email")

        self.fields["task_type"].help_text = "Usa Contenido / publicación cuando necesites controlar Creado + Publicado por semana, quincena o mes."
        self.fields["recurrence_frequency"].help_text = "Solo aplica a Contenido / publicación. Si queda sin renovación, la tarea mostrará una alerta de configuración."

    def clean(self):
        cleaned = super().clean()
        task_type = cleaned.get("task_type")
        recurrence = cleaned.get("recurrence_frequency")
        start = cleaned.get("recurrence_start_date")
        if task_type == DesignTask.TaskType.CONTENT:
            if recurrence and recurrence != DesignTask.Recurrence.NONE and not start:
                self.add_error("recurrence_start_date", "Indica la fecha desde la que empiezan los periodos.")
        else:
            cleaned["recurrence_frequency"] = DesignTask.Recurrence.NONE
            cleaned["recurrence_start_date"] = None
        return cleaned
