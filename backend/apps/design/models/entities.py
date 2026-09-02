import re
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import TimestampedModel
from .choices import (
    BackgroundStyle, LogoFormat, LogoStatus, PaletteColorRole, PhotoAvailability,
    StockUsage, StyleDirection, WebVisualStructure,
)


def validate_hex(value):
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value or ""):
        raise ValidationError("Usa un color HEX válido, por ejemplo #0055FF.")


class DesignBrief(TimestampedModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="design_brief")
    general_location = models.CharField(max_length=180, blank=True, verbose_name="Datos generales / ubicación")
    business_notes = models.CharField(max_length=255, blank=True, verbose_name="Business / observación comercial")
    social_notes = models.TextField(blank=True, verbose_name="Redes sociales / notas")
    meeting_attendees = models.TextField(blank=True, verbose_name="Encargados / participantes")

    logo_status = models.CharField(max_length=20, choices=LogoStatus.choices, default=LogoStatus.HAS_LOGO, verbose_name="Estado del logo")
    logo_change_notes = models.TextField(blank=True, verbose_name="Cambios solicitados para el logo")
    logo_format = models.CharField(max_length=20, choices=LogoFormat.choices, default=LogoFormat.UNKNOWN, verbose_name="Formato del logo")
    logo_file = models.ImageField(upload_to="design/logos/", null=True, blank=True, verbose_name="Logo para vista/PDF (opcional)")

    visual_structure = models.CharField(max_length=24, choices=WebVisualStructure.choices, default=WebVisualStructure.VISUAL, verbose_name="Estructura visual de la web")
    visual_structure_notes = models.TextField(blank=True, verbose_name="Detalle de estructura / animaciones")
    style_direction = models.CharField(max_length=30, choices=StyleDirection.choices, default=StyleDirection.MODERN, verbose_name="Dirección de estilo")

    color_base_notes = models.TextField(blank=True, verbose_name="Base del diseño / colores solicitados")
    background_style = models.CharField(max_length=20, choices=BackgroundStyle.choices, default=BackgroundStyle.MIXED, verbose_name="Estilo de color y fondo")

    photo_availability = models.CharField(max_length=20, choices=PhotoAvailability.choices, default=PhotoAvailability.PARTIAL, verbose_name="Imágenes del cliente")
    stock_usage = models.CharField(max_length=20, choices=StockUsage.choices, default=StockUsage.MIX, verbose_name="Uso de stock")
    services = models.TextField(blank=True, verbose_name="Servicios principales")

    page_style_notes = models.TextField(blank=True, verbose_name="Estilo esperado de la página")
    typography_direction = models.TextField(blank=True, verbose_name="Tipografía / dirección de texto")
    layout_preferences = models.TextField(blank=True, verbose_name="Distribución y composición")
    visual_references = models.TextField(blank=True, verbose_name="Referencias visuales / URLs")
    elements_to_avoid = models.TextField(blank=True, verbose_name="Elementos que no se deben usar")
    designer_notes = models.TextField(blank=True, verbose_name="Notas internas de diseño")

    completed = models.BooleanField(default=False, verbose_name="Asesoría visual completada")
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_design_briefs")

    def __str__(self):
        return f"Asesoría visual · {self.project}"


class ColorPalette(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="color_palettes")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    general_rules = models.TextField(blank=True, verbose_name="Reglas generales de uso")

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.project.project_code} · {self.name}"


class PaletteColor(TimestampedModel):
    palette = models.ForeignKey(ColorPalette, on_delete=models.CASCADE, related_name="colors")
    role = models.CharField(max_length=20, choices=PaletteColorRole.choices, default=PaletteColorRole.EXTRA)
    label = models.CharField(max_length=80, blank=True)
    hex_code = models.CharField(max_length=7, validators=[validate_hex])
    usage = models.CharField(max_length=200, blank=True, help_text="Ej.: botones, fondo, títulos.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.get_role_display()} · {self.hex_code}"


class PaletteGradient(TimestampedModel):
    palette = models.ForeignKey(ColorPalette, on_delete=models.CASCADE, related_name="gradients")
    name = models.CharField(max_length=80, default="Degradado")
    start_hex = models.CharField(max_length=7, validators=[validate_hex])
    end_hex = models.CharField(max_length=7, validators=[validate_hex])
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} · {self.start_hex} → {self.end_hex}"
