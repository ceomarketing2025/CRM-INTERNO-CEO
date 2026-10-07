"""Lógica de planes y renovaciones."""

import calendar
from datetime import timedelta

from django.utils import timezone

from .models.choices import RenewalFrequency


def add_months(value, months=1):
    index = value.year * 12 + (value.month - 1) + months
    year, month_zero = divmod(index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def next_renewal_after(value, frequency):
    if frequency == RenewalFrequency.WEEKLY:
        return value + timedelta(days=7)
    if frequency == RenewalFrequency.BIWEEKLY:
        return value + timedelta(days=15)
    if frequency == RenewalFrequency.MONTHLY:
        return add_months(value, 1)
    if frequency == RenewalFrequency.EVERY_MONDAY:
        # La renovación siempre cae en el siguiente lunes.
        days = (7 - value.weekday()) % 7
        if days == 0:
            days = 7
        return value + timedelta(days=days)
    return None


def current_cycle_bounds(start_date, frequency, today=None):
    """Devuelve (inicio, próxima renovación) del ciclo que contiene hoy.

    Si el plan aún no inicia, devuelve start_date y su primera renovación.
    """
    today = today or timezone.localdate()
    start = start_date or today

    if frequency == RenewalFrequency.NONE:
        return start, None

    if frequency == RenewalFrequency.EVERY_MONDAY:
        if today < start:
            cycle_start = start
        else:
            days_since_monday = today.weekday()
            cycle_start = today - timedelta(days=days_since_monday)
            if cycle_start < start:
                cycle_start = start
        return cycle_start, next_renewal_after(cycle_start, frequency)

    cycle_start = start
    due = next_renewal_after(cycle_start, frequency)
    guard = 0
    while due and due <= today and guard < 600:
        cycle_start = due
        due = next_renewal_after(cycle_start, frequency)
        guard += 1
    return cycle_start, due


def renewal_urgency(renewal_date, today=None):
    today = today or timezone.localdate()
    if not renewal_date:
        return {"days": None, "label": "Sin renovación", "class": "neutral"}
    days = (renewal_date - today).days
    if days < 0:
        return {"days": days, "label": f"Vencido hace {abs(days)} día(s)", "class": "overdue"}
    if days <= 1:
        label = "Hoy" if days == 0 else "Mañana"
        return {"days": days, "label": label, "class": "red"}
    if days == 2:
        return {"days": days, "label": "En 2 días", "class": "yellow"}
    return {"days": days, "label": f"En {days} días", "class": "green"}
