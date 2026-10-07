from django import forms
from .models import Client


class ClientForm(forms.ModelForm):
    """Ficha básica del cliente.

    Los servicios contratados ya no viven aquí; se asignan dentro de Proyectos.
    """

    class Meta:
        model = Client
        fields = [
            "first_name",
            "last_name",
            "identity_document",
            "phone",
            "business_name",
            "email",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Nota administrativa opcional..."}),
        }
        labels = {
            "identity_document": "ID / identificación (opcional)",
            "phone": "Número de teléfono",
            "business_name": "Nombre de la empresa",
            "email": "Correo (opcional)",
            "notes": "Notas internas",
        }
