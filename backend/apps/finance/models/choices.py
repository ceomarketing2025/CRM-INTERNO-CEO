from django.db import models


class TransactionType(models.TextChoices):
    EXPENSE = "expense", "Egreso"
    INCOME = "income", "Ingreso"


class TransactionStatus(models.TextChoices):
    PLANNED = "planned", "Planificado"
    PENDING = "pending", "Pendiente"
    PAID = "paid", "Pagado"
    CANCELLED = "cancelled", "Cancelado"


class RecurringPeriod(models.TextChoices):
    NONE = "none", "No recurrente"
    WEEKLY = "weekly", "Semanal"
    BIWEEKLY = "biweekly", "Cada 15 días"
    MONTHLY = "monthly", "Mensual"
    YEARLY = "yearly", "Anual"
    CUSTOM = "custom", "Personalizado"


class OperatingExpenseKind(models.TextChoices):
    SUBSCRIPTION = "subscription", "Mensualidad / suscripción"
    TOOL = "tool", "Herramienta / software"
    PLUGIN = "plugin", "Plugin / licencia"
    SERVICE = "service", "Servicio operativo"
    ADVERTISING = "advertising", "Publicidad / plataforma"
    OTHER = "other", "Otro"


class CompanyExpenseStatus(models.TextChoices):
    CEO_PAID = "ceo_paid", "Pagado por CEO"
    PENDING = "pending", "Pendiente"
    REIMBURSEMENT = "reimbursement", "Pendiente reembolso"
    PAID_OTHER = "paid_other", "Pagado por tercero"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    PARTIAL = "partial", "Parcial"
    PAID = "paid", "Pagado"
