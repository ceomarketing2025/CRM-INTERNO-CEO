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
