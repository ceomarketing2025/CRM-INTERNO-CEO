"""Consultas y composición de la billetera financiera."""

from decimal import Decimal

from django.utils import timezone

from apps.operations.models import CredentialPurchase, DomainHostingRecord
from apps.plans.models import ClientPlan
from .models import OperatingExpense, PersonnelPayment, ProjectPayment, SubscriptionPayment
from .services import subscription_financial_status


def _money(value):
    return value or Decimal("0.00")


def wallet_entries(limit=250):
    rows = []

    # Compras de dominio/hosting: una fila por cada costo real para no mezclar recibos.
    for item in DomainHostingRecord.objects.select_related("client", "project").all():
        if _money(item.domain_cost) > 0:
            rows.append({
                "date": item.start_date,
                "direction": "expense",
                "source": "Dominio",
                "concept": item.domain_name or item.get_operation_type_display(),
                "party": item.client.business_name,
                "project": item.project,
                "amount": _money(item.domain_cost),
                "currency": item.currency,
                "status": item.project_domain_label,
                "status_class": "success" if item.is_domain_complete else "warning",
                "receipt_url": item.domain_receipt_drive_url or item.receipt_drive_url,
            })
        if _money(item.server_cost) > 0:
            rows.append({
                "date": item.start_date,
                "direction": "expense",
                "source": "Hosting",
                "concept": item.provider_label,
                "party": item.client.business_name,
                "project": item.project,
                "amount": _money(item.server_cost),
                "currency": item.currency,
                "status": "Registrado",
                "status_class": "success",
                "receipt_url": item.server_receipt_drive_url or item.receipt_drive_url,
            })

    # Compras de credenciales históricas, si existen.
    for item in CredentialPurchase.objects.select_related("client", "project").filter(cost__gt=0):
        rows.append({
            "date": item.purchase_date,
            "direction": "expense",
            "source": "Credencial",
            "concept": item.credential_name,
            "party": item.client.business_name,
            "project": item.project,
            "amount": _money(item.cost),
            "currency": item.currency,
            "status": "Activo" if item.active else "Inactivo",
            "status_class": "success" if item.active else "neutral",
            "receipt_url": item.receipt_drive_url,
        })

    for item in OperatingExpense.objects.select_related("responsible").all():
        rows.append({
            "date": item.date,
            "direction": "expense",
            "source": "Gasto operativo",
            "concept": f"{item.provider} · {item.detail}",
            "party": item.responsible.display_name if item.responsible_id else "Empresa",
            "project": None,
            "amount": _money(item.cost),
            "currency": item.currency,
            "status": item.get_status_display(),
            "status_class": "success" if item.is_paid else "warning",
            "receipt_url": item.receipt_drive_url,
        })

    for item in PersonnelPayment.objects.select_related("employee").all():
        rows.append({
            "date": item.payment_date or item.created_at.date(),
            "direction": "expense",
            "source": "Nómina",
            "concept": f"{item.employee.display_name} · {item.period}",
            "party": item.role_name or item.employee.get_role_display(),
            "project": None,
            "amount": _money(item.total),
            "currency": item.currency,
            "status": item.get_status_display(),
            "status_class": "success" if item.status == "paid" else "warning",
            "receipt_url": item.payroll_receipt_url,
        })

    for item in ProjectPayment.objects.select_related("project__client").all():
        rows.append({
            "date": item.payment_date,
            "direction": "income",
            "source": "Pago proyecto",
            "concept": item.project.name,
            "party": item.project.client.business_name,
            "project": item.project,
            "amount": _money(item.amount),
            "currency": item.currency,
            "status": "Recibido",
            "status_class": "success",
            "receipt_url": item.receipt_drive_url,
        })

    for item in SubscriptionPayment.objects.select_related("client_plan__client", "client_plan__plan").all():
        link = item.client_plan.project_links.select_related("project").first()
        rows.append({
            "date": item.payment_date,
            "direction": "income",
            "source": "Suscripción",
            "concept": item.client_plan.plan.name,
            "party": item.client_plan.client.business_name,
            "project": link.project if link else None,
            "amount": _money(item.amount),
            "currency": item.currency,
            "status": "Recibido",
            "status_class": "success",
            "receipt_url": item.receipt_drive_url,
        })

    rows.sort(key=lambda row: (row["date"] or timezone.localdate()), reverse=True)
    return rows[:limit]


def wallet_totals(rows=None):
    rows = rows if rows is not None else wallet_entries(limit=100000)
    today = timezone.localdate()
    month_start = today.replace(day=1)

    def is_actual(row):
        # Pendientes de gastos/no pagados se muestran en la billetera, pero no se
        # descuentan del saldo realizado hasta que estén pagados.
        if row["direction"] == "income":
            return True
        return row["status_class"] == "success"

    income_total = sum((_money(r["amount"]) for r in rows if r["direction"] == "income" and is_actual(r)), Decimal("0.00"))
    expense_total = sum((_money(r["amount"]) for r in rows if r["direction"] == "expense" and is_actual(r)), Decimal("0.00"))
    month_income = sum((_money(r["amount"]) for r in rows if r["direction"] == "income" and r["date"] and r["date"] >= month_start and is_actual(r)), Decimal("0.00"))
    month_expense = sum((_money(r["amount"]) for r in rows if r["direction"] == "expense" and r["date"] and r["date"] >= month_start and is_actual(r)), Decimal("0.00"))
    return {
        "income_total": income_total,
        "expense_total": expense_total,
        "balance": income_total - expense_total,
        "month_income": month_income,
        "month_expense": month_expense,
        "month_balance": month_income - month_expense,
    }


def subscription_rows():
    today = timezone.localdate()
    rows = []
    qs = ClientPlan.objects.select_related("client", "plan").filter(is_active=True).order_by("renewal_date", "client__business_name")
    for item in qs:
        if not item.plan.is_subscription_product:
            continue
        link = item.project_links.select_related("project").first()
        rows.append({
            "subscription": item,
            "project": link.project if link else None,
            "financial_status": subscription_financial_status(item, today=today),
        })
    return rows
