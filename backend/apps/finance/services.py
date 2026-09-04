"""Cálculos financieros centralizados V12.

La regla principal es no duplicar dinero: dominio/hosting se lee de Operaciones,
gastos de empresa de OperatingExpense y los ingresos se registran como pagos
reales de proyecto o de suscripción.
"""

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.plans.models.choices import PaymentStatus


def money(value):
    return value or Decimal("0.00")


def project_contract_total(project):
    total = Decimal("0.00")
    assignments = project.contracted_plans.select_related("plan").filter(is_active=True)
    for item in assignments:
        if item.plan.is_subscription_product:
            continue
        total += money(item.agreed_price)
    return total


def project_payment_summary(project):
    total = project_contract_total(project)
    paid = money(project.client_payments.aggregate(total=Sum("amount"))["total"])
    pending = max(total - paid, Decimal("0.00"))
    if total <= 0:
        status = PaymentStatus.PENDING
        label = "Sin pago único definido"
    elif paid <= 0:
        status = PaymentStatus.PENDING
        label = "Pendiente"
    elif paid < total:
        status = PaymentStatus.PARTIAL
        label = "Parcial"
    else:
        status = PaymentStatus.PAID
        label = "Pagado"
    return {
        "total": total,
        "paid": paid,
        "pending": pending,
        "status": status,
        "status_label": label,
        "percent": min(round((paid * 100 / total), 0), 100) if total > 0 else 0,
    }


def sync_subscription_after_payment(payment):
    """Actualiza el estado de pago de la suscripción sin alterar su ciclo operativo."""
    plan = payment.client_plan
    plan.payment_status = PaymentStatus.PAID
    if payment.paid_until:
        if not plan.paid_until or payment.paid_until > plan.paid_until:
            plan.paid_until = payment.paid_until
    plan.save(update_fields=["payment_status", "paid_until", "updated_at"])
    return plan


def subscription_financial_status(client_plan, today=None):
    today = today or timezone.localdate()
    if client_plan.paid_until and client_plan.paid_until >= today:
        return {"code": "paid", "label": "Al día", "class": "success"}
    if client_plan.renewal_date and client_plan.renewal_date < today:
        return {"code": "overdue", "label": "Vencido", "class": "danger"}
    if client_plan.payment_status == PaymentStatus.PARTIAL:
        return {"code": "partial", "label": "Parcial", "class": "warning"}
    return {"code": "pending", "label": "Pendiente", "class": "warning"}
