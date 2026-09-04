from django import forms
from .models import Meeting, Reminder


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ["client", "project", "title", "scheduled_at", "meet_url", "attendees", "external_attendees", "agenda", "reminder_minutes", "status", "notes"]
        widgets = {"scheduled_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"), "attendees": forms.SelectMultiple(attrs={"size": 6}), "agenda": forms.Textarea(attrs={"rows": 4}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_at"].input_formats = ["%Y-%m-%dT%H:%M"]


class ReminderForm(forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ["title", "category", "due_at", "client", "project", "assigned_to", "notes"]
        widgets = {"due_at": DateTimeLocalInput(format="%Y-%m-%dT%H:%M"), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_at"].input_formats = ["%Y-%m-%dT%H:%M"]
