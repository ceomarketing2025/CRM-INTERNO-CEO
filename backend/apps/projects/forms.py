from django import forms
from .models import Project, ProjectAssignment, ProjectNote


class ProjectForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        client = cleaned.get("client")
        purchased_plan = cleaned.get("purchased_plan")
        if client and purchased_plan and purchased_plan.client_id != client.pk:
            self.add_error("purchased_plan", "El plan comprado debe pertenecer al mismo cliente del proyecto.")
        return cleaned

    class Meta:
        model = Project
        fields = ["client", "purchased_plan", "name", "project_type", "status", "priority", "progress", "start_date", "due_date", "summary", "internal_notes"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}), "due_date": forms.DateInput(attrs={"type": "date"}), "summary": forms.Textarea(attrs={"rows": 4}), "internal_notes": forms.Textarea(attrs={"rows": 4})}


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
