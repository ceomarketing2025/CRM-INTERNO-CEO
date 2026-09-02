from django import forms
from .models import FinancialTransaction
class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = ["transaction_type", "category", "client", "project", "client_plan", "domain", "concept", "vendor_payee", "amount", "currency", "transaction_date", "due_date", "status", "recurring_period", "next_due_date", "notes", "attachment"]
        widgets = {k: forms.DateInput(attrs={"type": "date"}) for k in ["transaction_date", "due_date", "next_due_date"]} | {"notes": forms.Textarea(attrs={"rows": 3})}
