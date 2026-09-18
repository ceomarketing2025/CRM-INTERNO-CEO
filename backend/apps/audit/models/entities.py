from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="activity_logs_v2")
    module = models.CharField(max_length=80)
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.module} · {self.action}"


class GeneralAuditCheck(models.Model):
    """Decisión de Gerencia sobre trabajo que vive en otra área.

    No duplica el estado operativo. `source_key` identifica la fuente viva y
    `decision` conserva la conclusión de la última revisión de Gerencia.
    `is_ready` se mantiene por compatibilidad: solo es True cuando la decisión
    actual es APROBADO, por lo que una tarea rechazada nunca queda bloqueada.
    """

    class Decision(models.TextChoices):
        PENDING = "pending", "Por revisar"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="general_audit_checks")
    source_key = models.CharField(max_length=190, unique=True)
    area = models.CharField(max_length=24)
    category = models.CharField(max_length=180, blank=True)
    label = models.CharField(max_length=240, blank=True)
    decision = models.CharField(max_length=16, choices=Decision.choices, default=Decision.PENDING)
    is_ready = models.BooleanField(default=False, verbose_name="Aprobado")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="general_audit_reviews",
    )
    note = models.TextField(blank=True, verbose_name="Observaciones de auditoría")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__client__business_name", "area", "category", "label"]
        indexes = [models.Index(fields=["area", "is_ready"]), models.Index(fields=["project", "area"])]

    def __str__(self):
        return f"Auditoría · {self.project.project_code} · {self.label or self.source_key}"


class ManagementTask(models.Model):
    """Tarea transversal creada por Gerencia y mostrada dentro del área destino."""

    class Area(models.TextChoices):
        DESIGN = "design", "Diseño"
        MARKETING = "marketing", "Marketing"
        DEVELOPMENT = "development", "Desarrollo"
        SALES = "sales", "Vendedores"
        ADMINISTRATION = "administration", "Administración"

    class Status(models.TextChoices):
        TODO = "todo", "Pendiente"
        DOING = "doing", "En proceso"
        REVIEW = "review", "Para revisión"
        DONE = "done", "Completada"

    class Priority(models.TextChoices):
        LOW = "low", "Baja"
        MEDIUM = "medium", "Media"
        HIGH = "high", "Alta"
        URGENT = "urgent", "Urgente"

    area = models.CharField(max_length=24, choices=Area.choices)
    title = models.CharField(max_length=180, verbose_name="Título")
    description = models.TextField(blank=True, verbose_name="Descripción de la actividad")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_tasks_assigned",
        verbose_name="Responsable",
    )
    client = models.ForeignKey(
        "clients.Client",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_tasks",
        verbose_name="Cliente",
    )
    project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_tasks",
        verbose_name="Proyecto",
    )
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.MEDIUM, verbose_name="Prioridad")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TODO, verbose_name="Estado")
    due_date = models.DateField(null=True, blank=True, verbose_name="Fecha límite")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_tasks_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="management_tasks_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]
        indexes = [
            models.Index(fields=["area", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["project", "area"]),
        ]

    @property
    def progress_percent(self):
        return {
            self.Status.TODO: 0,
            self.Status.DOING: 55,
            self.Status.REVIEW: 85,
            self.Status.DONE: 100,
        }.get(self.status, 0)

    def __str__(self):
        owner = self.assigned_to.display_name if self.assigned_to_id else "Sin responsable"
        return f"{self.get_area_display()} · {self.title} · {owner}"
