from django import forms

from apps.accounts.models import UserAccount
from apps.clients.models import Client
from apps.projects.models import Project

from .models import ManagementTask


AREA_ROLE_MAP = {
    ManagementTask.Area.DESIGN: UserAccount.Role.DESIGN,
    ManagementTask.Area.MARKETING: UserAccount.Role.MARKETING,
    ManagementTask.Area.DEVELOPMENT: UserAccount.Role.DEVELOPER,
    ManagementTask.Area.SALES: UserAccount.Role.SALES,
    ManagementTask.Area.ADMINISTRATION: UserAccount.Role.ADMINISTRATION,
}


class ManagementTaskForm(forms.ModelForm):
    class Meta:
        model = ManagementTask
        fields = [
            "area", "assigned_to", "title", "description", "priority",
            "due_date", "client", "project",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe de forma breve qué debe realizar el responsable…"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "area": "Área correspondiente",
            "assigned_to": "Responsable",
            "client": "Cliente (opcional)",
            "project": "Proyecto (opcional)",
        }
        help_texts = {
            "client": "Déjalo vacío si la tarea no pertenece a un cliente específico.",
            "project": "Solo aparecen proyectos del cliente seleccionado.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.order_by("business_name")

        selected_area = self.data.get("area") or getattr(self.instance, "area", None)
        role = AREA_ROLE_MAP.get(selected_area)
        users = UserAccount.objects.filter(is_active=True)
        if role:
            users = users.filter(role=role)
        else:
            users = users.none()
        self.fields["assigned_to"].queryset = users.order_by("first_name", "last_name", "email")
        self.fields["assigned_to"].label_from_instance = lambda user: f"{user.display_name} · {user.get_role_display()}"

        selected_client = self.data.get("client") or getattr(self.instance, "client_id", None)
        projects = Project.objects.select_related("client")
        if selected_client:
            projects = projects.filter(client_id=selected_client)
        else:
            projects = projects.none()
        self.fields["project"].queryset = projects.order_by("client__business_name", "name")
        self.fields["project"].label_from_instance = lambda project: f"{project.project_code} · {project.name}"

    def clean(self):
        cleaned = super().clean()
        area = cleaned.get("area")
        assigned_to = cleaned.get("assigned_to")
        client = cleaned.get("client")
        project = cleaned.get("project")

        expected_role = AREA_ROLE_MAP.get(area)
        if assigned_to and expected_role and assigned_to.role != expected_role:
            self.add_error("assigned_to", "El responsable debe pertenecer al área seleccionada.")

        if project:
            if client and project.client_id != client.pk:
                self.add_error("project", "El proyecto no pertenece al cliente seleccionado.")
            elif not client:
                cleaned["client"] = project.client

        return cleaned
