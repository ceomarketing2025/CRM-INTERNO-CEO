from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.services import log_activity
from apps.core.decorators import manager_required, role_required
from apps.plans.models import ClientPlan
from apps.projects.models import Project
from .forms import (
    FinancialTransactionForm,
    OperatingExpenseForm,
    PersonnelPaymentForm,
    ProjectPaymentForm,
    SubscriptionPaymentForm,
)
from .models import FinancialTransaction, OperatingExpense, PersonnelPayment, ProjectPayment, SubscriptionPayment
from .selectors import subscription_rows, wallet_entries, wallet_totals
from .services import project_payment_summary, sync_subscription_after_payment


@manager_required
def finance_dashboard(request):
    entries = wallet_entries(limit=300)
    totals = wallet_totals(entries)
    operating_expenses = OperatingExpense.objects.select_related("responsible", "created_by", "updated_by")[:12]
    personnel_payments = PersonnelPayment.objects.select_related("employee", "created_by", "updated_by")[:12]
    project_payments = ProjectPayment.objects.select_related("project__client", "created_by")[:15]
    subscription_payments = SubscriptionPayment.objects.select_related("client_plan__client", "client_plan__plan", "created_by")[:15]
    subscriptions = subscription_rows()
    return render(request, "finance/dashboard.html", {
        "entries": entries,
        "totals": totals,
        "operating_expenses": operating_expenses,
        "personnel_payments": personnel_payments,
        "project_payments": project_payments,
        "subscription_payments": subscription_payments,
        "subscriptions": subscriptions,
        "today": timezone.localdate(),
    })


# ---------------------------------------------------------------------------
# Gastos operativos / empresa
# ---------------------------------------------------------------------------

@manager_required
def operating_list(request):
    expenses = OperatingExpense.objects.select_related("responsible", "created_by", "updated_by")
    return render(request, "finance/operating_expenses.html", {"expenses": expenses})


@manager_required
def operating_create(request):
    form = OperatingExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        log_activity(request.user, "finance", "operating_expense_create", obj)
        messages.success(request, "Gasto operativo registrado.")
        return redirect("finance:operating_list")
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Nuevo gasto operativo",
        "subtitle": "Herramientas, licencias, plugins, software, plataformas y gastos de empresa.",
    })


@manager_required
def operating_edit(request, pk):
    obj = get_object_or_404(OperatingExpense, pk=pk)
    form = OperatingExpenseForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        saved = form.save(commit=False)
        saved.updated_by = request.user
        saved.save()
        log_activity(request.user, "finance", "operating_expense_update", saved)
        messages.success(request, "Gasto operativo actualizado.")
        return redirect("finance:operating_list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar gasto operativo", "subtitle": str(obj)})


@manager_required
def operating_delete(request, pk):
    obj = get_object_or_404(OperatingExpense, pk=pk)
    if request.method == "POST":
        label = str(obj)
        log_activity(request.user, "finance", "operating_expense_delete", obj, description=label)
        obj.delete()
        messages.success(request, "Gasto operativo eliminado.")
    return redirect("finance:operating_list")


# ---------------------------------------------------------------------------
# Pagos del cliente: pago único de proyecto + suscripciones
# ---------------------------------------------------------------------------

@role_required("administration")
def project_payment_create(request, project_pk):
    project = get_object_or_404(Project.objects.select_related("client").prefetch_related("contracted_plans__plan", "client_payments"), pk=project_pk)
    summary = project_payment_summary(project)
    form = ProjectPaymentForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.project = project
        obj.created_by = request.user
        obj.save()
        log_activity(request.user, "finance", "project_payment_create", obj, description=f"Pago cliente · {project.project_code}")
        messages.success(request, "Pago del proyecto registrado y enviado a la billetera.")
        return redirect("projects:detail", pk=project.pk)
    return render(request, "finance/project_payment_form.html", {
        "form": form,
        "project": project,
        "summary": summary,
    })


@manager_required
def project_payment_delete(request, pk):
    obj = get_object_or_404(ProjectPayment.objects.select_related("project"), pk=pk)
    project_pk = obj.project_id
    if request.method == "POST":
        label = str(obj)
        log_activity(request.user, "finance", "project_payment_delete", obj, description=label)
        obj.delete()
        messages.success(request, "Pago del proyecto eliminado.")
    return redirect("projects:detail", pk=project_pk)


@manager_required
def subscription_payment_create(request, client_plan_pk):
    client_plan = get_object_or_404(ClientPlan.objects.select_related("client", "plan"), pk=client_plan_pk)
    form = SubscriptionPaymentForm(request.POST or None, client_plan=client_plan)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.client_plan = client_plan
        obj.created_by = request.user
        obj.save()
        sync_subscription_after_payment(obj)
        log_activity(request.user, "finance", "subscription_payment_create", obj, description=f"Suscripción · {client_plan.plan.name}")
        messages.success(request, "Pago de suscripción registrado en la billetera.")
        return redirect("finance:dashboard")
    project_link = client_plan.project_links.select_related("project").first()
    return render(request, "finance/subscription_payment_form.html", {
        "form": form,
        "subscription": client_plan,
        "project": project_link.project if project_link else None,
    })


@manager_required
def subscription_payment_delete(request, pk):
    obj = get_object_or_404(SubscriptionPayment.objects.select_related("client_plan"), pk=pk)
    if request.method == "POST":
        plan = obj.client_plan
        label = str(obj)
        log_activity(request.user, "finance", "subscription_payment_delete", obj, description=label)
        obj.delete()
        latest = plan.subscription_payments.order_by("-payment_date", "-id").first()
        if latest:
            plan.payment_status = "paid"
            plan.paid_until = latest.paid_until
        else:
            plan.payment_status = "pending"
            plan.paid_until = None
        plan.save(update_fields=["payment_status", "paid_until", "updated_at"])
        messages.success(request, "Pago de suscripción eliminado.")
    return redirect("finance:dashboard")


# ---------------------------------------------------------------------------
# Nómina existente
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Movimientos legacy: se conservan rutas para no romper enlaces anteriores.
# ---------------------------------------------------------------------------

@manager_required
def transaction_create(request):
    form = FinancialTransactionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        log_activity(request.user, "finance", "legacy_transaction_create", obj)
        messages.success(request, "Movimiento anterior registrado.")
        return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Movimiento financiero anterior", "subtitle": "Compatibilidad con registros de versiones anteriores."})


@manager_required
def transaction_edit(request, pk):
    obj = get_object_or_404(FinancialTransaction, pk=pk)
    form = FinancialTransactionForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "finance", "legacy_transaction_update", obj)
        messages.success(request, "Movimiento actualizado.")
        return redirect("finance:dashboard")
    return render(request, "shared/form.html", {"form": form, "title": "Editar movimiento anterior", "subtitle": obj.concept})
