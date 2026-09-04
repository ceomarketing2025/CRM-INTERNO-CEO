from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel
from .choices import RecurringPeriod, TransactionStatus, TransactionType

class FinanceCategory(TimestampedModel):
    name = models.CharField(max_length=140)
    code = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["name"]
    def __str__(self): return self.name

class FinancialTransaction(TimestampedModel):
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, default=TransactionType.EXPENSE)
    category = models.ForeignKey(FinanceCategory, on_delete=models.PROTECT, related_name="transactions")
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.SET_NULL, related_name="financial_transactions")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="financial_transactions")
    client_plan = models.ForeignKey("plans.ClientPlan", null=True, blank=True, on_delete=models.SET_NULL, related_name="financial_transactions")
    domain = models.ForeignKey("domains.Domain", null=True, blank=True, on_delete=models.SET_NULL, related_name="financial_transactions")
    concept = models.CharField(max_length=200)
    vendor_payee = models.CharField(max_length=180, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="USD")
    transaction_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PLANNED)
    recurring_period = models.CharField(max_length=20, choices=RecurringPeriod.choices, default=RecurringPeriod.NONE)
    next_due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    attachment = models.FileField(upload_to="finance/", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_finance_transactions")

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["due_date"])]

    def __str__(self): return f"{self.get_transaction_type_display()} · {self.concept}"


class PersonnelPayment(TimestampedModel):
    """Manager-only payroll/control record for internal staff payments."""
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="personnel_payments",
        verbose_name="Colaborador",
    )
    role_name = models.CharField(max_length=140, blank=True, verbose_name="Rol / cargo")
    period = models.CharField(max_length=80, verbose_name="Periodo", help_text="Ej.: Septiembre 2026")
    payment_date = models.DateField(null=True, blank=True, verbose_name="Fecha de pago")
    base_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Sueldo / base")
    extras = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Bonos / extras")
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Descuentos")
    currency = models.CharField(max_length=8, default="USD")
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PENDING)
    payment_method = models.CharField(max_length=120, blank=True, verbose_name="Forma de pago")
    payroll_receipt_url = models.URLField(blank=True, verbose_name="Rol de pago / recibo Drive")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_personnel_payments",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_personnel_payments",
    )

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["payment_date"])]

    @property
    def total(self):
        return max((self.base_amount or Decimal("0.00")) + (self.extras or Decimal("0.00")) - (self.deductions or Decimal("0.00")), Decimal("0.00"))

    def save(self, *args, **kwargs):
        if self.employee_id and not self.role_name:
            self.role_name = self.employee.job_title or self.employee.get_role_display()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.display_name} · {self.period}"
