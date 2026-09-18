from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampedModel


class Lead(TimestampedModel):
    class Status(models.TextChoices):
        NEW = "new", "Nuevo"
        PENDING = "pending", "Pendiente de contacto"
        CONTACTED = "contacted", "Contactado"
        FOLLOW_UP = "follow_up", "Seguimiento"
        MEETING_PROPOSED = "meeting_proposed", "Meet propuesto"
        MEETING_DONE = "meeting_done", "Meet realizado"
        POTENTIAL = "potential", "Cliente potencial"
        WON = "won", "Venta cerrada"
        NO_RESPONSE = "no_response", "No responde"
        UNQUALIFIED = "unqualified", "No calificado"
        LOST = "lost", "Perdido"

    class Quality(models.TextChoices):
        UNDEFINED = "undefined", "Sin definir"
        LOW = "low", "Baja"
        MEDIUM = "medium", "Media"
        HIGH = "high", "Alta"

    class LossReason(models.TextChoices):
        NO_RESPONSE = "no_response", "No respondió"
        FAKE_NUMBER = "fake_number", "Número falso"
        DUPLICATE = "duplicate", "Duplicado"
        NOT_INTERESTED = "not_interested", "No interesado"
        PRICE = "price", "Precio"
        NO_BUDGET = "no_budget", "Sin presupuesto"
        SERVICE_UNAVAILABLE = "service_unavailable", "Servicio no disponible"
        OUT_OF_AREA = "out_of_area", "Fuera de zona"
        OTHER_COMPANY = "other_company", "Contrató otra empresa"
        RESEARCHING = "researching", "Solo averiguaba"
        SPAM = "spam", "Spam"
        OTHER = "other", "Otro"

    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Apellido")
    phone = models.CharField(max_length=40, blank=True, db_index=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, db_index=True)
    city = models.CharField(max_length=100, blank=True, verbose_name="Ciudad")
    state_region = models.CharField(max_length=100, blank=True, verbose_name="Estado / Provincia")
    zip_code = models.CharField(max_length=20, blank=True, verbose_name="ZIP")
    country = models.CharField(max_length=100, blank=True, verbose_name="País")
    company = models.CharField(max_length=180, blank=True, verbose_name="Empresa")
    interested_service = models.CharField(max_length=180, blank=True, verbose_name="Servicio interesado")
    source = models.CharField(max_length=120, blank=True, verbose_name="Fuente")
    campaign = models.CharField(max_length=180, blank=True, verbose_name="Campaña")
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Presupuesto")
    comments = models.TextField(blank=True, verbose_name="Comentarios")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
        verbose_name="Vendedora asignada",
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEW, db_index=True, verbose_name="Estado")
    quality = models.CharField(max_length=20, choices=Quality.choices, default=Quality.UNDEFINED, verbose_name="Calidad")
    loss_reason = models.CharField(max_length=40, choices=LossReason.choices, blank=True, verbose_name="Motivo de pérdida")
    last_contact_at = models.DateTimeField(null=True, blank=True, verbose_name="Último contacto")
    next_follow_up_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="Próximo seguimiento")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_sales_leads")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "assigned_to"]), models.Index(fields=["next_follow_up_at", "assigned_to"])]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name or self.email or self.phone or f"Lead #{self.pk}"


class LeadAssignmentHistory(TimestampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="assignment_history")
    previous_assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_assignments_from")
    new_assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_assignments_to")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_assignment_changes")

    class Meta:
        ordering = ["-created_at"]


class ContactAttempt(TimestampedModel):
    class Result(models.TextChoices):
        ANSWERED = "answered", "Contestó"
        NO_ANSWER = "no_answer", "No contestó"
        WHATSAPP = "whatsapp", "Respondió por WhatsApp"
        EMAIL = "email", "Respondió por email"
        WRONG_NUMBER = "wrong_number", "Número incorrecto"
        NOT_INTERESTED = "not_interested", "No interesado"
        OUT_OF_BUDGET = "out_of_budget", "Fuera de presupuesto"
        CONTACT_LATER = "contact_later", "Solicita contacto después"
        ACCEPTS_MEETING = "accepts_meeting", "Acepta meet"

    class Channel(models.TextChoices):
        PHONE = "phone", "Llamada"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        OTHER = "other", "Otro"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="contact_attempts")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_contact_attempts")
    result = models.CharField(max_length=30, choices=Result.choices)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.PHONE)
    notes = models.TextField(blank=True)
    contacted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-contacted_at", "-created_at"]


class FollowUp(TimestampedModel):
    class ContactType(models.TextChoices):
        PHONE = "phone", "Llamada"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meet"
        OTHER = "other", "Otro"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        COMPLETED = "completed", "Completado"
        CANCELLED = "cancelled", "Cancelado"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="follow_ups")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_follow_ups")
    due_at = models.DateTimeField(db_index=True, verbose_name="Fecha y hora")
    contact_type = models.CharField(max_length=20, choices=ContactType.choices, default=ContactType.PHONE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_sales_follow_ups", verbose_name="Creado por",
    )

    class Meta:
        ordering = ["due_at"]
        indexes = [models.Index(fields=["status", "due_at", "assigned_to"])]


class SalesMeeting(TimestampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Programado"
        COMPLETED = "completed", "Realizado"
        NO_SHOW = "no_show", "No asistió"
        CANCELLED = "cancelled", "Cancelado"
        RESCHEDULED = "rescheduled", "Reprogramado"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="sales_meetings")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sales_meetings")
    scheduled_at = models.DateTimeField(db_index=True)
    meeting_type = models.CharField(max_length=80, blank=True, verbose_name="Tipo de reunión")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    result = models.TextField(blank=True, verbose_name="Resultado")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_sales_meetings", verbose_name="Agendado por",
    )

    class Meta:
        ordering = ["scheduled_at"]
