from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimestampedModel
from .choices import (
    CompanyExpenseStatus,
    OperatingExpenseKind,
    PaymentStatus,
    RecurringPeriod,
    TransactionStatus,
    TransactionType,
)


class FinanceCategory(TimestampedModel):
    name = models.CharField(max_length=140)
    code = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FinancialTransaction(TimestampedModel):
    """Movimiento legado.

    Se conserva para no perder información de versiones anteriores. La V12 usa
    modelos especializados para evitar duplicar compras/pagos entre módulos.
    """

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

    def __str__(self):
        return f"{self.get_transaction_type_display()} · {self.concept}"


class OperatingExpense(TimestampedModel):
    """Gastos de empresa: Adobe, CapCut, Elementor, plugins, herramientas, etc."""

    code = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Código")
    date = models.DateField(verbose_name="Fecha")
    provider = models.CharField(max_length=160, verbose_name="Proveedor", help_text="Ej.: Adobe, Envato, CapCut, Elementor")
    detail = models.CharField(max_length=220, verbose_name="Nombre / detalle", help_text="Ej.: Creative Cloud Pro")
    kind = models.CharField(max_length=24, choices=OperatingExpenseKind.choices, default=OperatingExpenseKind.SUBSCRIPTION, verbose_name="Tipo")
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), verbose_name="Costo")
    currency = models.CharField(max_length=8, default="USD", verbose_name="Moneda")
    status = models.CharField(max_length=24, choices=CompanyExpenseStatus.choices, default=CompanyExpenseStatus.CEO_PAID, verbose_name="Estado")
    recurring_period = models.CharField(max_length=20, choices=RecurringPeriod.choices, default=RecurringPeriod.NONE, verbose_name="Renovación")
    next_due_date = models.DateField(null=True, blank=True, verbose_name="Próximo pago")
    receipt_drive_url = models.URLField(blank=True, verbose_name="Link recibo Drive")
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="operating_expenses", verbose_name="Responsable")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_operating_expenses")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_operating_expenses")

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["status"]), models.Index(fields=["next_due_date"])]

    def save(self, *args, **kwargs):
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta

        if self.date and not self.next_due_date:
            if self.recurring_period == RecurringPeriod.WEEKLY:
                self.next_due_date = self.date + timedelta(days=7)
            elif self.recurring_period == RecurringPeriod.BIWEEKLY:
                self.next_due_date = self.date + timedelta(days=15)
            elif self.recurring_period == RecurringPeriod.MONTHLY:
                self.next_due_date = self.date + relativedelta(months=1)
            elif self.recurring_period == RecurringPeriod.YEARLY:
                self.next_due_date = self.date + relativedelta(years=1)
        if self.recurring_period == RecurringPeriod.NONE:
            self.next_due_date = None

        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.code:
            self.code = f"GO-{self.pk:04d}"
            type(self).objects.filter(pk=self.pk).update(code=self.code)
            self.code = f"GO-{self.pk:04d}"

    @property
    def month_name(self):
        months = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return months[self.date.month] if self.date else ""

    @property
    def is_paid(self):
        return self.status in {CompanyExpenseStatus.CEO_PAID, CompanyExpenseStatus.PAID_OTHER}

    def __str__(self):
        return f"{self.code or 'GO'} · {self.provider} · {self.detail}"


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


class ProjectPayment(TimestampedModel):
    """Abono real recibido para el pago único de un proyecto."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="client_payments")
    payment_date = models.DateField(verbose_name="Fecha de pago")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto recibido")
    currency = models.CharField(max_length=8, default="USD")
    payment_method = models.CharField(max_length=120, blank=True, verbose_name="Forma de pago")
    receipt_drive_url = models.URLField(blank=True, verbose_name="Comprobante / recibo Drive")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_project_payments")

    class Meta:
        ordering = ["-payment_date", "-id"]
        indexes = [models.Index(fields=["payment_date"])]

    def __str__(self):
        return f"{self.project.project_code} · ${self.amount}"


class SubscriptionPayment(TimestampedModel):
    """Cobro real de una suscripción recurrente (Social Media u otro plan recurrente)."""

    client_plan = models.ForeignKey("plans.ClientPlan", on_delete=models.CASCADE, related_name="subscription_payments")
    payment_date = models.DateField(verbose_name="Fecha de pago")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto recibido")
    currency = models.CharField(max_length=8, default="USD")
    paid_until = models.DateField(null=True, blank=True, verbose_name="Pagado hasta")
    payment_method = models.CharField(max_length=120, blank=True, verbose_name="Forma de pago")
    receipt_drive_url = models.URLField(blank=True, verbose_name="Comprobante / recibo Drive")
    notes = models.TextField(blank=True, verbose_name="Notas")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_subscription_payments")

    class Meta:
        ordering = ["-payment_date", "-id"]
        indexes = [models.Index(fields=["payment_date"]), models.Index(fields=["paid_until"])]

    @property
    def project(self):
        link = self.client_plan.project_links.select_related("project").first()
        return link.project if link else None

    def __str__(self):
        return f"{self.client_plan.client.business_name} · {self.client_plan.plan.name} · ${self.amount}"
