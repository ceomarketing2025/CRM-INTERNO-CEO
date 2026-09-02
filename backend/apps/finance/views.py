from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.audit.services import log_activity
from apps.core.decorators import manager_required
from .forms import FinancialTransactionForm
from .models import FinanceCategory, FinancialTransaction

@manager_required
def finance_dashboard(request):
    transactions = FinancialTransaction.objects.select_related("category", "client", "project", "domain")[:80]
    current_month = timezone.localdate().replace(day=1)
    month_qs = FinancialTransaction.objects.filter(transaction_date__gte=current_month, status="paid")
    expenses = month_qs.filter(transaction_type="expense").aggregate(total=Sum("amount"))["total"] or 0
    income = month_qs.filter(transaction_type="income").aggregate(total=Sum("amount"))["total"] or 0
    by_category = month_qs.filter(transaction_type="expense").values("category__name").annotate(total=Sum("amount")).order_by("-total")
    return render(request, "finance/dashboard.html", {"transactions": transactions, "expenses": expenses, "income": income, "by_category": by_category, "categories": FinanceCategory.objects.filter(is_active=True)})

@manager_required
def transaction_create(request):
    form = FinancialTransactionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save(); log_activity(request.user, "finance", "create", obj); messages.success(request, "Movimiento financiero registrado."); return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo movimiento financiero", "subtitle": "Estructura financiera: credenciales, dominios, renovaciones, sueldos, web, social media y otros costos."})

@manager_required
def transaction_edit(request, pk):
    obj = get_object_or_404(FinancialTransaction, pk=pk)
    form = FinancialTransactionForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); log_activity(request.user, "finance", "update", obj); messages.success(request, "Movimiento actualizado."); return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Editar movimiento", "subtitle": obj.concept})
