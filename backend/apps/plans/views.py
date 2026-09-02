from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from apps.audit.services import log_activity
from apps.core.decorators import manager_required, role_required
from .forms import ClientPlanForm, ServicePlanForm
from .models import ClientPlan, ServicePlan

@login_required
def plan_list(request):
    return render(request, "plans/list.html", {"plans": ServicePlan.objects.all(), "purchases": ClientPlan.objects.select_related("client", "plan")[:30]})

@manager_required
def plan_create(request):
    form = ServicePlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(); log_activity(request.user, "plans", "create", obj); messages.success(request, "Plan creado."); return redirect("plans:list")
    return render(request, "shared/form.html", {"form": form, "title": "Crear plan", "subtitle": "Catálogo de servicios y planes."})

@manager_required
def plan_edit(request, pk):
    obj = get_object_or_404(ServicePlan, pk=pk)
    form = ServicePlanForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save(); log_activity(request.user, "plans", "update", obj); messages.success(request, "Plan actualizado."); return redirect("plans:list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar plan", "subtitle": obj.name})

@role_required("administration")
def purchase_create(request):
    form = ClientPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save(); log_activity(request.user, "plans", "purchase", obj); messages.success(request, "Compra de plan registrada."); return redirect("plans:list")
    return render(request, "shared/form.html", {"form": form, "title": "Registrar compra de plan", "subtitle": "Asocia un plan del catálogo a un cliente."})
