from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.services import log_activity
from apps.core.decorators import manager_required
from .forms import FinancialTransactionForm, PersonnelPaymentForm
from .models import FinanceCategory, FinancialTransaction, PersonnelPayment


@manager_required
def finance_dashboard(request):
    transactions = FinancialTransaction.objects.select_related("category", "client", "project", "domain")[:100]
    personnel_payments = PersonnelPayment.objects.select_related("employee", "created_by", "updated_by")[:100]
    current_month = timezone.localdate().replace(day=1)
    month_qs = FinancialTransaction.objects.filter(transaction_date__gte=current_month, status="paid")
    expenses = month_qs.filter(transaction_type="expense").aggregate(total=Sum("amount"))["total"] or 0
    income = month_qs.filter(transaction_type="income").aggregate(total=Sum("amount"))["total"] or 0
    payroll_paid = PersonnelPayment.objects.filter(payment_date__gte=current_month, status="paid").aggregate(
        base=Sum("base_amount"), extras=Sum("extras"), deductions=Sum("deductions")
    )
    payroll_total = (payroll_paid["base"] or 0) + (payroll_paid["extras"] or 0) - (payroll_paid["deductions"] or 0)
    payroll_pending_count = PersonnelPayment.objects.filter(status__in=["planned", "pending"]).count()
    by_category = month_qs.filter(transaction_type="expense").values("category__name").annotate(total=Sum("amount")).order_by("-total")
    return render(request, "finance/dashboard.html", {
        "transactions": transactions,
        "personnel_payments": personnel_payments,
        "expenses": expenses,
        "income": income,
        "payroll_total": payroll_total,
        "payroll_pending_count": payroll_pending_count,
        "by_category": by_category,
        "categories": FinanceCategory.objects.filter(is_active=True),
    })


@manager_required
def transaction_create(request):
    form = FinancialTransactionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        log_activity(request.user, "finance", "create", obj)
        messages.success(request, "Movimiento financiero registrado.")
        return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo gasto / movimiento", "subtitle": "Gastos generales, proveedores, suscripciones, costos de proyectos e ingresos."})


@manager_required
def transaction_edit(request, pk):
    obj = get_object_or_404(FinancialTransaction, pk=pk)
    form = FinancialTransactionForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "finance", "update", obj)
        messages.success(request, "Movimiento actualizado.")
        return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Editar movimiento", "subtitle": obj.concept})


@manager_required
def personnel_create(request):
    form = PersonnelPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        log_activity(request.user, "finance", "personnel_payment_create", obj)
        messages.success(request, "Pago de personal registrado.")
        return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo pago de personal", "subtitle": "Rol de pago, periodo, sueldo, extras, descuentos y recibo."})


@manager_required
def personnel_edit(request, pk):
    obj = get_object_or_404(PersonnelPayment, pk=pk)
    form = PersonnelPaymentForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.updated_by = request.user
        saved.save()
        log_activity(request.user, "finance", "personnel_payment_update", saved)
        messages.success(request, "Pago de personal actualizado.")
        return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Editar pago de personal", "subtitle": f"{obj.employee.display_name} · {obj.period}"})


@manager_required
def personnel_delete(request, pk):
    obj = get_object_or_404(PersonnelPayment, pk=pk)
    if request.method == "POST":
        label = str(obj)
        log_activity(request.user, "finance", "personnel_payment_delete", obj, description=label)
        obj.delete()
        messages.success(request, "Pago de personal eliminado.")
    return redirect("finance:dashboard")
