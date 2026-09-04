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


class SocialMediaCycle(TimestampedModel):
    """Ciclo operativo generado desde el plan Social Media asignado al cliente."""

    client_plan = models.ForeignKey(
        "plans.ClientPlan",
        on_delete=models.CASCADE,
        related_name="social_media_cycles",
        verbose_name="Plan Social Media del cliente",
    )
    period_start = models.DateField(verbose_name="Inicio del ciclo")
    due_date = models.DateField(null=True, blank=True, verbose_name="Próxima renovación")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_social_media_cycles",
    )

    class Meta:
        ordering = ["-period_start", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["client_plan", "period_start"], name="unique_social_cycle_start")
        ]

    @property
    def progress_percent(self):
        items = list(self.items.all())
        if not items:
            return 0
        done = sum(1 for item in items if item.is_complete)
        return round(done * 100 / len(items))

    @property
    def completed(self):
        items = list(self.items.all())
        return bool(items) and all(item.is_complete for item in items)

    @property
    def total_items(self):
        return self.items.count()

    @property
    def completed_items(self):
        return sum(1 for item in self.items.all() if item.is_complete)

    def __str__(self):
        return f"{self.client_plan.client.business_name} · {self.period_start}"


class SocialMediaContentItem(TimestampedModel):
    class ContentType(models.TextChoices):
        POST = "post", "Post"
        VIDEO = "video", "Video"

    cycle = models.ForeignKey(SocialMediaCycle, on_delete=models.CASCADE, related_name="items")
    content_type = models.CharField(max_length=12, choices=ContentType.choices)
    sequence = models.PositiveSmallIntegerField(default=1)
    ready = models.BooleanField(default=False, verbose_name="Contenido listo")
    published_networks = models.JSONField(default=list, blank=True, verbose_name="Publicado en")
    notes = models.CharField(max_length=300, blank=True, verbose_name="Notas")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_social_media_items",
    )

    class Meta:
        ordering = ["content_type", "sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cycle", "content_type", "sequence"], name="unique_social_content_item")
        ]

    @property
    def required_networks(self):
        return list(self.cycle.client_plan.social_networks or [])

    @property
    def is_complete(self):
        if not self.ready:
            return False
        required = set(self.required_networks)
        published = set(self.published_networks or [])
        return required.issubset(published)

    @property
    def label(self):
        return f"{self.get_content_type_display()} {self.sequence}"

    def __str__(self):
        return f"{self.cycle} · {self.label}"


class DesignTask(TimestampedModel):
    """Actividad operativa para cualquier producto contratado del área de Diseño.

    Las tareas normales se completan una vez. Las tareas de contenido pueden ser
    recurrentes (semanales, quincenales o mensuales) y generan ciclos históricos
    independientes para saber si el contenido fue creado y si realmente se publicó.
    """

    class Status(models.TextChoices):
        TODO = "todo", "Pendiente"
        DOING = "doing", "En proceso"
        REVIEW = "review", "En revisión"
        DONE = "done", "Lista"

    class TaskType(models.TextChoices):
        STANDARD = "standard", "Tarea única"
        CONTENT = "content", "Contenido / publicación"

    class Recurrence(models.TextChoices):
        NONE = "none", "Sin renovación"
        WEEKLY = "weekly", "Semanal"
        BIWEEKLY = "biweekly", "Quincenal"
        MONTHLY = "monthly", "Mensual"

    project_plan = models.ForeignKey(
        "projects.ProjectPlanAssignment",
        on_delete=models.CASCADE,
        related_name="design_tasks",
        verbose_name="Proyecto / producto de Diseño",
    )
    title = models.CharField(max_length=180, verbose_name="Actividad")
    description = models.TextField(blank=True, verbose_name="Detalle")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO, verbose_name="Estado")
    due_date = models.DateField(null=True, blank=True, verbose_name="Fecha límite")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="design_operational_tasks",
        verbose_name="Responsable",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        default=TaskType.STANDARD,
        verbose_name="Tipo de actividad",
    )
    recurrence_frequency = models.CharField(
        max_length=20,
        choices=Recurrence.choices,
        default=Recurrence.NONE,
        verbose_name="Frecuencia de control",
        help_text="Para publicaciones: semanal, quincenal o mensual. Cada periodo crea un control nuevo.",
    )
    recurrence_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Inicio de la renovación",
    )
    auto_generated = models.BooleanField(default=False, verbose_name="Creada automáticamente")
    configuration_required = models.BooleanField(
        default=False,
        verbose_name="Requiere configurar renovación",
        help_text="Se usa para tareas Social Media creadas automáticamente al contratar el servicio.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_design_operational_tasks",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_design_operational_tasks",
    )

    class Meta:
        ordering = ["project_plan__project__client__business_name", "project_plan__plan__name", "order", "id"]

    @property
    def is_complete(self):
        return self.status == self.Status.DONE

    @property
    def is_recurring(self):
        return self.task_type == self.TaskType.CONTENT and self.recurrence_frequency != self.Recurrence.NONE

    @property
    def needs_configuration(self):
        return bool(
            self.task_type == self.TaskType.CONTENT
            and (
                self.configuration_required
                or self.recurrence_frequency == self.Recurrence.NONE
                or not self.recurrence_start_date
            )
        )

    @property
    def standard_progress_percent(self):
        return {
            self.Status.TODO: 0,
            self.Status.DOING: 60,
            self.Status.REVIEW: 80,
            self.Status.DONE: 100,
        }.get(self.status, 0)

    @property
    def project(self):
        return self.project_plan.project

    @property
    def plan(self):
        return self.project_plan.plan

    def save(self, *args, **kwargs):
        if self.task_type == self.TaskType.STANDARD:
            self.recurrence_frequency = self.Recurrence.NONE
            self.recurrence_start_date = None
            self.configuration_required = False
        elif self.recurrence_frequency != self.Recurrence.NONE and self.recurrence_start_date:
            self.configuration_required = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.project_plan} · {self.title}"


class DesignTaskCycle(TimestampedModel):
    """Periodo de una tarea recurrente de contenido.

    Mantiene el historial por semana/quincena/mes. El estado operativo tiene dos
    pasos simples: contenido creado y contenido publicado.
    """

    task = models.ForeignKey(DesignTask, on_delete=models.CASCADE, related_name="cycles")
    period_start = models.DateField(verbose_name="Inicio del periodo")
    period_end = models.DateField(verbose_name="Fin del periodo")
    label = models.CharField(max_length=120, verbose_name="Periodo")
    content_created = models.BooleanField(default=False, verbose_name="Creado")
    content_published = models.BooleanField(default=False, verbose_name="Publicado")
    notes = models.CharField(max_length=300, blank=True, verbose_name="Notas")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_design_task_cycles",
    )

    class Meta:
        ordering = ["-period_start", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["task", "period_start"], name="unique_design_task_cycle_start")
        ]
        indexes = [models.Index(fields=["task", "period_start"], name="design_desi_task_id_0b1698_idx")]

    @property
    def progress_percent(self):
        if self.content_published:
            return 100
        if self.content_created:
            return 60
        return 0

    @property
    def state_label(self):
        if self.content_published:
            return "Publicado"
        if self.content_created:
            return "Creado · pendiente publicar"
        return "Pendiente de crear"

    @property
    def state_code(self):
        if self.content_published:
            return "green"
        if self.content_created:
            return "yellow"
        return "red"

    @property
    def is_complete(self):
        return self.content_published

    def save(self, *args, **kwargs):
        if self.content_published:
            self.content_created = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.task} · {self.label}"
