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


class GoogleSyncStatus(models.TextChoices):
    NOT_SYNCED = "not_synced", "Sin sincronizar"
    PENDING = "pending", "Pendiente"
    SYNCED = "synced", "Sincronizado"
    ERROR = "error", "Error"
    SKIPPED = "skipped", "No aplica"


class GoogleConnectionStatus(models.TextChoices):
    DISCONNECTED = "disconnected", "Desconectado"
    CONNECTED = "connected", "Conectado"
    ERROR = "error", "Error"


class GoogleCalendarConnection(TimestampedModel):
    """Conexión OAuth central usada por Recordatorios/Meet.

    Solo se espera una fila activa. Los tokens se guardan cifrados; nunca se
    almacena la contraseña de Google.
    """

    account_email = models.EmailField(blank=True)
    calendar_id = models.CharField(max_length=255, default="primary")
    encrypted_credentials = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=GoogleConnectionStatus.choices,
        default=GoogleConnectionStatus.DISCONNECTED,
    )
    last_error = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="google_calendar_connections",
    )

    class Meta:
        verbose_name = "Conexión Google Calendar"
        verbose_name_plural = "Conexiones Google Calendar"

    def __str__(self):
        return self.account_email or "Google Calendar"


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

    # Google Calendar
    sync_to_google = models.BooleanField(default=True, verbose_name="Sincronizar con Google Calendar")
    google_event_id = models.CharField(max_length=255, blank=True, db_index=True)
    google_event_url = models.URLField(blank=True)
    google_sync_status = models.CharField(max_length=20, choices=GoogleSyncStatus.choices, default=GoogleSyncStatus.PENDING)
    google_sync_error = models.TextField(blank=True)
    google_last_synced_at = models.DateTimeField(null=True, blank=True)

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
    duration_minutes = models.PositiveIntegerField(default=60, verbose_name="Duración (minutos)")
    meet_url = models.URLField(blank=True, help_text="Se genera automáticamente cuando Google Meet está activado.")
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="meetings")
    external_attendees = models.TextField(blank=True, help_text="Correos externos, uno por línea, coma o punto y coma.")
    agenda = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    reminder_minutes = models.PositiveIntegerField(default=60)
    status = models.CharField(max_length=20, choices=MeetingStatus.choices, default=MeetingStatus.SCHEDULED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_meetings")

    # Google Calendar / Meet
    create_google_event = models.BooleanField(default=True, verbose_name="Crear evento en Google Calendar")
    create_google_meet = models.BooleanField(default=True, verbose_name="Crear Google Meet")
    google_event_id = models.CharField(max_length=255, blank=True, db_index=True)
    google_event_url = models.URLField(blank=True)
    google_sync_status = models.CharField(max_length=20, choices=GoogleSyncStatus.choices, default=GoogleSyncStatus.PENDING)
    google_sync_error = models.TextField(blank=True)
    google_last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.client.business_name} · {self.scheduled_at:%Y-%m-%d %H:%M}"
