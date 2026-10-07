from django import forms
from apps.clients.models import Client
from apps.projects.models import Project
from .models import Domain


class DomainForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and not user.is_manager:
            projects = Project.objects.filter(assignments__user=user, assignments__area="development").distinct()
            self.fields["project"].queryset = projects
            self.fields["client"].queryset = Client.objects.filter(projects__in=projects).distinct()

    def clean(self):
        cleaned = super().clean()
        client, project = cleaned.get("client"), cleaned.get("project")
        if client and project and project.client_id != client.pk:
            self.add_error("project", "El proyecto debe pertenecer al cliente seleccionado.")
        return cleaned

    class Meta:
        model = Domain
        fields = ["client", "project", "domain_name", "registrar", "provider_url", "account_email", "purchase_date", "expiry_date", "renewal_date", "annual_cost", "currency", "auto_renew", "status", "notes"]
        widgets = {k: forms.DateInput(attrs={"type": "date"}) for k in ["purchase_date", "expiry_date", "renewal_date"]} | {"notes": forms.Textarea(attrs={"rows": 3})}
