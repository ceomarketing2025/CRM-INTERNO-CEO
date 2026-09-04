from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.plans.models import ClientPlan
from .models import (
    FinancialTransaction,
    OperatingExpense,
    PersonnelPayment,
    ProjectPayment,
    SubscriptionPayment,
)
from .services import project_payment_summary


class DateInput(forms.DateInput):
    input_type = "date"


class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = ["transaction_type", "category", "client", "project", "client_plan", "domain", "concept", "vendor_payee", "amount", "currency", "transaction_date", "due_date", "status", "recurring_period", "next_due_date", "notes", "attachment"]
        widgets = {k: DateInput() for k in ["transaction_date", "due_date", "next_due_date"]} | {"notes": forms.Textarea(attrs={"rows": 3})}


class OperatingExpenseForm(forms.ModelForm):
    class Meta:
        model = OperatingExpense
        fields = [
            "date", "provider", "detail", "kind", "cost", "currency", "status",
            "recurring_period", "next_due_date", "receipt_drive_url", "responsible", "notes",
        ]
        widgets = {
            "date": DateInput(),
            "next_due_date": DateInput(),
            "cost": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()
        self.fields["responsible"].queryset = UserAccount.objects.filter(is_active=True).order_by("first_name", "last_name", "email")


class PersonnelPaymentForm(forms.ModelForm):
    class Meta:
        model = PersonnelPayment
        fields = [
            "employee", "role_name", "period", "payment_date", "base_amount", "extras",
            "deductions", "currency", "status", "payment_method", "payroll_receipt_url", "notes",
        ]
        widgets = {
            "payment_date": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = UserAccount.objects.filter(is_active=True).order_by("first_name", "last_name", "email")


class ProjectPaymentForm(forms.ModelForm):
    class Meta:
        model = ProjectPayment
        fields = ["payment_date", "amount", "currency", "payment_method", "receipt_drive_url", "notes"]
        widgets = {
            "payment_date": DateInput(),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.fields["payment_date"].initial = timezone.localdate()
            if project:
                pending = project_payment_summary(project)["pending"]
                if pending > 0:
                    self.fields["amount"].initial = pending

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= Decimal("0.00"):
            raise forms.ValidationError("El monto debe ser mayor que cero.")
        if self.project:
            pending = project_payment_summary(self.project)["pending"]
            if pending <= 0:
                raise forms.ValidationError("Este proyecto no tiene saldo pendiente de pago único.")
            if amount > pending:
                raise forms.ValidationError(f"El saldo pendiente es ${pending:.2f}. No registres un valor mayor.")
        return amount


class SubscriptionPaymentForm(forms.ModelForm):
    client_plan = forms.ModelChoiceField(
        queryset=ClientPlan.objects.none(),
        label="Suscripción",
        help_text="Cliente · proyecto/plan recurrente.",
    )

    class Meta:
        model = SubscriptionPayment
        fields = ["client_plan", "payment_date", "amount", "currency", "paid_until", "payment_method", "receipt_drive_url", "notes"]
        widgets = {
            "payment_date": DateInput(),
            "paid_until": DateInput(),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, client_plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client_plan"].queryset = ClientPlan.objects.select_related("client", "plan").filter(is_active=True).order_by("client__business_name", "plan__name")
        if client_plan:
            self.fields["client_plan"].initial = client_plan
            self.fields["client_plan"].widget = forms.HiddenInput()
            if not self.is_bound:
                self.fields["amount"].initial = client_plan.agreed_price
                self.fields["currency"].initial = client_plan.currency
                self.fields["paid_until"].initial = client_plan.renewal_date
        if not self.is_bound and not self.instance.pk:
            self.fields["payment_date"].initial = timezone.localdate()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= Decimal("0.00"):
            raise forms.ValidationError("El monto debe ser mayor que cero.")
        return amount
