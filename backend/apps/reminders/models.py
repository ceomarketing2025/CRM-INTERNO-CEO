from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel


class ReminderCategory(models.TextChoices):
    SIX_WEEKS = "six_weeks", "Cumplimiento 6 semanas"
    CREDENTIAL_RENEWAL = "credential_renewal", "Renovación de credenciales"
    CREDENTIAL_PURCHASE = "credential_purchase", "Comprar credenciales"
    FOLLOWUP_15 = "followup_15", "Seguimiento 15 días"
    SOCIAL_OFFER = "social_offer", "Ofrecer Social Media"
    SOCIAL_MONTHLY = "social_monthly", "Informe mensual Social Media"
    SOCIAL_DAILY = "social_daily", "Seguimiento diario Social Media"
    CAMPAIGN_MANAGER_REVIEW = "campaign_manager_review", "Revisión Gerencia campaña"
    CAMPAIGN_WEEKLY = "campaign_weekly", "Seguimiento semanal campaña"
    MEETING = "meeting", "Reunión"
    GOOGLE_REVIEWS = "google_reviews", "Seguimiento reviews / Guarantee"
    CUSTOM = "custom", "Personalizado"


class ReminderStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    DONE = "done", "Completado"
    CANCELLED = "cancelled", "Cancelado"


class Reminder(TimestampedModel):
    title = models.CharField(max_length=220)
    category = models.CharField(max_length=40, choices=ReminderCategory.choices, default=ReminderCategory.CUSTOM)
    due_at = models.DateTimeField()
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.CASCADE, related_name="reminders")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="reminders")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_reminders")
    status = models.CharField(max_length=20, choices=ReminderStatus.choices, default=ReminderStatus.PENDING)
    notes = models.TextField(blank=True)
    source_key = models.CharField(max_length=140, blank=True, db_index=True, help_text="Clave idempotente para recordatorios automáticos.")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_reminders")

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [models.Index(fields=["status", "due_at"]), models.Index(fields=["category"])]

    def __str__(self):
        return self.title


class MeetingStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Programada"
    COMPLETED = "completed", "Completada"
    CANCELLED = "cancelled", "Cancelada"


class Meeting(TimestampedModel):
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="meetings")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="meetings")
    title = models.CharField(max_length=200, default="Reunión con cliente")
    scheduled_at = models.DateTimeField()
    meet_url = models.URLField(blank=True, help_text="Pega aquí el enlace de Google Meet. El módulo queda preparado para OAuth/Calendar futuro.")
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="meetings")
    external_attendees = models.TextField(blank=True, help_text="Correos externos, uno por línea.")
    agenda = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    reminder_minutes = models.PositiveIntegerField(default=60)
    status = models.CharField(max_length=20, choices=MeetingStatus.choices, default=MeetingStatus.SCHEDULED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_meetings")

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.client.business_name} · {self.scheduled_at:%Y-%m-%d %H:%M}"
