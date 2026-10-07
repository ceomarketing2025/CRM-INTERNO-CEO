import re

from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from apps.projects.models import Project
from .models import Meeting, Reminder


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class ProjectSelect(forms.Select):
    """Select con datos para filtros Cliente -> Proyecto -> Responsable."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-client-id"] = str(instance.client_id or "")
            assignee_ids = [
                str(assignment.user_id)
                for assignment in instance.assignments.all()
                if assignment.user_id and assignment.status in {"assigned", "active"}
            ]
            option["attrs"]["data-assignee-ids"] = ",".join(assignee_ids)
        return option


class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = [
            "client",
            "project",
            "area",
            "title",
            "scheduled_at",
            "duration_minutes",
            "attendees",
            "external_attendees",
            "agenda",
            "reminder_minutes",
            "status",
            "notes",
        ]
        widgets = {
            "project": ProjectSelect(),
            "scheduled_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "attendees": forms.SelectMultiple(attrs={"size": 7}),
            "external_attendees": forms.Textarea(attrs={"rows": 3, "placeholder": "cliente@correo.com\notro@correo.com"}),
            "agenda": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "scheduled_at": "Fecha y hora",
            "duration_minutes": "Duración (minutos)",
            "attendees": "Participantes internos",
            "external_attendees": "Invitados externos",
            "reminder_minutes": "Avisar con anticipación (minutos)",
            "area": "Área / módulo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["duration_minutes"].widget.attrs.update({"min": 5, "step": 5})
        self.fields["reminder_minutes"].widget.attrs.update({"min": 0, "step": 5})
        self.fields["project"].required = False
        # Se cargan todos los proyectos únicamente para construir el selector
        # dependiente en frontend. El usuario solo ve los del cliente elegido.
        self.fields["project"].queryset = Project.objects.select_related("client").prefetch_related("assignments").order_by(
            "client__business_name", "-created_at"
        )

    def clean_external_attendees(self):
        raw = self.cleaned_data.get("external_attendees", "")
        emails = []
        for token in re.split(r"[\n,;]+", raw):
            email = token.strip()
            if not email:
                continue
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError(f"Correo de invitado inválido: {email}")
            normalized = email.lower()
            if normalized not in emails:
                emails.append(normalized)
        return "\n".join(emails)

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get("client")
        project = cleaned.get("project")
        if project and client and project.client_id != client.pk:
            self.add_error("project", "El proyecto seleccionado no pertenece a este cliente.")
        if (cleaned.get("duration_minutes") or 0) < 5:
            self.add_error("duration_minutes", "La reunión debe durar al menos 5 minutos.")
        return cleaned


class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ["title", "category", "area", "due_at", "client", "project", "assigned_to", "sync_to_google", "notes"]
        widgets = {
            "project": ProjectSelect(),
            "due_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "sync_to_google": forms.CheckboxInput(),
        }
        labels = {"sync_to_google": "Sincronizar con Google Calendar", "area": "Área / módulo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["project"].required = False
        # El HTML recibe la relación con cada cliente para filtrar el selector
        # sin mostrar proyectos de otras empresas.
        self.fields["project"].queryset = Project.objects.select_related("client").prefetch_related("assignments").order_by(
            "client__business_name", "-created_at"
        )
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].help_text = "Al elegir un proyecto solo aparecen responsables vinculados a ese proyecto."

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get("client")
        project = cleaned.get("project")
        if project and client and project.client_id != client.pk:
            self.add_error("project", "El proyecto seleccionado no pertenece a este cliente.")
        assigned_to = cleaned.get("assigned_to")
        if project and assigned_to and not project.assignments.filter(
            user=assigned_to, status__in=["assigned", "active"]
        ).exists():
            self.add_error("assigned_to", "El responsable seleccionado no está vinculado a este proyecto.")
        return cleaned
