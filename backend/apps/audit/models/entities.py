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
    def __str__(self): return f"{self.module} · {self.action}"


class GeneralAuditCheck(models.Model):
    """Confirmación de auditoría sobre una tarea que vive en otra área.

    No duplica el estado operativo: solo registra que Gerencia/Auditoría revisó
    una tarea concreta. `source_key` identifica la fuente dinámica.
    """

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="general_audit_checks")
    source_key = models.CharField(max_length=190, unique=True)
    area = models.CharField(max_length=24)
    category = models.CharField(max_length=180, blank=True)
    label = models.CharField(max_length=240, blank=True)
    is_ready = models.BooleanField(default=False, verbose_name="Revisado")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="general_audit_reviews",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__client__business_name", "area", "category", "label"]
        indexes = [models.Index(fields=["area", "is_ready"]), models.Index(fields=["project", "area"])]

    def __str__(self):
        return f"Auditoría · {self.project.project_code} · {self.label or self.source_key}"
