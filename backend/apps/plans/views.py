from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_activity
from .forms import ROLE_TO_DEPARTMENT, ServicePlanForm
from .models import ServicePlan
from .models.choices import PlanDepartment, service_type_choices_for_department


def _department_for_user(user):
    if user.is_manager or user.is_superuser:
        return None
    return ROLE_TO_DEPARTMENT.get(getattr(user, "role", None))


def _can_create_plan(user):
    return bool(user.is_authenticated and (user.is_manager or user.is_superuser or _department_for_user(user)))


def _can_manage_plan(user, plan):
    if user.is_manager or user.is_superuser:
        return True
    return _department_for_user(user) == plan.department


@login_required
def plan_list(request):
    # IMPORTANTE: no filtrar las banderas del JSONField con ``exclude``.
    # En PostgreSQL una clave inexistente produce NULL y el NOT del exclude
    # también queda NULL, haciendo que desaparezcan del resultado planes sanos.
    # Filtramos área en SQL y ocultamos SOLO las banderas explícitamente True
    # en Python; así los planes nuevos/default siempre son visibles.
    plans_qs = ServicePlan.objects.select_related("created_by").all()
    department = _department_for_user(request.user)
    selected_department = request.GET.get("department", "")

    if department:
        plans_qs = plans_qs.filter(department=department)
        selected_department = department
    elif selected_department in {value for value, _ in PlanDepartment.choices}:
        plans_qs = plans_qs.filter(department=selected_department)
    else:
        selected_department = ""

    plans = [
        plan for plan in plans_qs
        if not (plan.rules or {}).get("obsolete_wrong_seed", False)
        and not (plan.rules or {}).get("retired_catalog_seed", False)
    ]

    grouped = []
    for value, label in PlanDepartment.choices:
        items = [plan for plan in plans if plan.department == value]
        if items:
            grouped.append({"value": value, "label": label, "plans": items})

    return render(request, "plans/list.html", {
        "grouped_plans": grouped,
        "plans": plans,
        "department": department,
        "selected_department": selected_department,
        "department_choices": PlanDepartment.choices,
        "department_label": dict(PlanDepartment.choices).get(department, "Todas las áreas") if department else "Todas las áreas",
        "can_create_plan": _can_create_plan(request.user),
    })


@login_required
def plan_create(request):
    if not _can_create_plan(request.user):
        raise PermissionDenied("Tu área no puede crear planes.")

    forced_department = _department_for_user(request.user)
    requested_department = request.GET.get("department")
    if request.user.is_manager and requested_department in {value for value, _ in PlanDepartment.choices}:
        forced_department = requested_department

    form = ServicePlanForm(request.POST or None, user=request.user, forced_department=forced_department)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        log_activity(request.user, "plans", "create", obj)
        messages.success(request, "Plan creado correctamente.")
        return redirect("plans:list")

    department_json = {
        value: [{"value": item_value, "label": item_label} for item_value, item_label in service_type_choices_for_department(value)]
        for value, _ in PlanDepartment.choices
    }
    return render(request, "plans/form.html", {
        "form": form,
        "title": "Crear plan",
        "subtitle": "Crea el producto de tu área. La renovación se configura al asignarlo al cliente.",
        "created_date": None,
        "department_service_types": department_json,
    })


@login_required
def plan_edit(request, pk):
    obj = get_object_or_404(ServicePlan, pk=pk)
    if not _can_manage_plan(request.user, obj):
        raise PermissionDenied("Solo el área creadora o Gerencia puede editar este plan.")

    form = ServicePlanForm(request.POST or None, instance=obj, user=request.user, forced_department=obj.department)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "plans", "update", obj)
        messages.success(request, "Plan actualizado.")
        return redirect("plans:list")

    department_json = {
        value: [{"value": item_value, "label": item_label} for item_value, item_label in service_type_choices_for_department(value)]
        for value, _ in PlanDepartment.choices
    }
    return render(request, "plans/form.html", {
        "form": form,
        "title": "Editar plan",
        "subtitle": obj.name,
        "created_date": obj.created_at,
        "plan": obj,
        "department_service_types": department_json,
    })


@login_required
def purchase_create(request):
    messages.info(request, "Las suscripciones recurrentes se configuran desde el módulo correspondiente, por ejemplo Diseño · Social Media.")
    return redirect("plans:list")
