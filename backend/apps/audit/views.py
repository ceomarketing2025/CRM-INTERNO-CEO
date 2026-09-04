from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from apps.core.decorators import manager_required
from .models import ActivityLog


@manager_required
def log_list(request):
    """Bitácora central de cambios para Gerencia/Configuración."""
    records = ActivityLog.objects.select_related("user").all()
    q = (request.GET.get("q") or "").strip()
    module = (request.GET.get("module") or "").strip()

    if q:
        records = records.filter(
            Q(description__icontains=q)
            | Q(action__icontains=q)
            | Q(module__icontains=q)
            | Q(entity_type__icontains=q)
            | Q(user__email__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )
    if module:
        records = records.filter(module=module)

    modules = list(
        ActivityLog.objects.exclude(module="")
        .order_by("module")
        .values_list("module", flat=True)
        .distinct()
    )
    page = Paginator(records, 80).get_page(request.GET.get("page"))
    return render(request, "audit/log_list.html", {
        "page": page,
        "modules": modules,
        "q": q,
        "selected_module": module,
    })
