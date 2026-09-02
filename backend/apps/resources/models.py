from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel


class ProjectResourceLink(TimestampedModel):
    class Area(models.TextChoices):
        ADMINISTRATION = "administration", "Administración"
        DESIGN = "design", "Diseño"
        DEVELOPMENT = "development", "Desarrollo"
        MARKETING = "marketing", "Marketing"
        GLOBAL = "global", "Global"

    class Kind(models.TextChoices):
        PALETTE_DRIVE = "palette_drive", "Drive - paleta"
        SUMMARY_BACKUP = "summary_backup", "Drive - resumen / respaldo"
        LOGO = "logo", "Logo / identidad"
        PHOTOS = "photos", "Banco de fotos"
        DOCUMENT = "document", "Documento"
        OTHER = "other", "Otro"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="resource_links")
    area = models.CharField(max_length=24, choices=Area.choices, default=Area.DESIGN)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.OTHER)
    label = models.CharField(max_length=160)
    url = models.URLField(max_length=1000)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="project_resource_links")

    class Meta:
        ordering = ["area", "kind", "label"]

    def __str__(self):
        return f"{self.project.project_code} · {self.label}"


class ImageReference(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="image_references")
    category = models.CharField(max_length=140, help_text="Ej.: Roofing, Siding, Gutters")
    image_url = models.URLField(max_length=1000, verbose_name="URL de foto / carpeta")
    source = models.CharField(max_length=120, blank=True, help_text="Drive, Shutterstock, cliente, etc.")
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="image_references")

    class Meta:
        ordering = ["order", "category", "id"]

    def __str__(self):
        return f"{self.project.project_code} · {self.category}"
