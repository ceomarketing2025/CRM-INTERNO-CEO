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
    MONTHLY = "monthly", "Mensual"
    YEARLY = "yearly", "Anual"
    CUSTOM = "custom", "Personalizado"
