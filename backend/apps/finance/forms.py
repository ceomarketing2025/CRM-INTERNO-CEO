from django import forms
from apps.accounts.models import UserAccount
from .models import FinancialTransaction, PersonnelPayment
class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = ["transaction_type", "category", "client", "project", "client_plan", "domain", "concept", "vendor_payee", "amount", "currency", "transaction_date", "due_date", "status", "recurring_period", "next_due_date", "notes", "attachment"]
        widgets = {k: forms.DateInput(attrs={"type": "date"}) for k in ["transaction_date", "due_date", "next_due_date"]} | {"notes": forms.Textarea(attrs={"rows": 3})}


class PersonnelPaymentForm(forms.ModelForm):
    class Meta:
        model = PersonnelPayment
        fields = [
            "employee", "role_name", "period", "payment_date", "base_amount", "extras",
            "deductions", "currency", "status", "payment_method", "payroll_receipt_url", "notes",
        ]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = UserAccount.objects.filter(is_active=True).order_by("first_name", "last_name", "email")
