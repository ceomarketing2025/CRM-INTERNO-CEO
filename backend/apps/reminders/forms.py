import re

from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from apps.projects.models import Project
from .models import Meeting, Reminder


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = [
            "client",
            "project",
            "title",
            "scheduled_at",
            "duration_minutes",
            "attendees",
            "external_attendees",
            "agenda",
            "reminder_minutes",
            "create_google_event",
            "create_google_meet",
            "status",
            "notes",
        ]
        widgets = {
            "scheduled_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "attendees": forms.SelectMultiple(attrs={"size": 7}),
            "external_attendees": forms.Textarea(attrs={"rows": 3, "placeholder": "cliente@correo.com\notro@correo.com"}),
            "agenda": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "create_google_event": forms.CheckboxInput(),
            "create_google_meet": forms.CheckboxInput(),
        }
        labels = {
            "scheduled_at": "Fecha y hora",
            "duration_minutes": "Duración (minutos)",
            "attendees": "Participantes internos",
            "external_attendees": "Invitados externos",
            "reminder_minutes": "Avisar con anticipación (minutos)",
            "create_google_event": "Sincronizar reunión con Google Calendar",
            "create_google_meet": "Generar enlace Google Meet",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["duration_minutes"].widget.attrs.update({"min": 5, "step": 5})
        self.fields["reminder_minutes"].widget.attrs.update({"min": 0, "step": 5})
        self.fields["project"].required = False
        if self.instance and self.instance.pk and self.instance.client_id:
            self.fields["project"].queryset = Project.objects.filter(client_id=self.instance.client_id).order_by("-created_at")
        else:
            self.fields["project"].queryset = Project.objects.select_related("client").order_by("client__business_name", "-created_at")

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
        create_event = cleaned.get("create_google_event")
        create_meet = cleaned.get("create_google_meet")
        if project and client and project.client_id != client.pk:
            self.add_error("project", "El proyecto seleccionado no pertenece a este cliente.")
        if create_meet and not create_event:
            self.add_error("create_google_meet", "Para crear Google Meet debes sincronizar primero la reunión con Google Calendar.")
        if (cleaned.get("duration_minutes") or 0) < 5:
            self.add_error("duration_minutes", "La reunión debe durar al menos 5 minutos.")
        return cleaned


class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ["title", "category", "due_at", "client", "project", "assigned_to", "sync_to_google", "notes"]
        widgets = {
            "due_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "sync_to_google": forms.CheckboxInput(),
        }
        labels = {"sync_to_google": "Sincronizar con Google Calendar"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["project"].required = False

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get("client")
        project = cleaned.get("project")
        if project and client and project.client_id != client.pk:
            self.add_error("project", "El proyecto seleccionado no pertenece a este cliente.")
        return cleaned
