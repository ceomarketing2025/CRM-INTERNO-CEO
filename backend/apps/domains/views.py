from datetime import timedelta
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from .forms import DomainForm
from .models import Domain

@role_required("developer")
def domain_list(request):
    today = timezone.localdate()
    domains = Domain.objects.select_related("client", "project")
    if not request.user.is_manager:
        domains = domains.filter(project__assignments__user=request.user, project__assignments__area="development").distinct()
    return render(request, "domains/list.html", {"domains": domains, "renewal_limit": today + timedelta(days=45)})

@role_required("developer")
def domain_create(request):
    form = DomainForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save(); log_activity(request.user, "domains", "create", obj); messages.success(request, "Dominio registrado."); return redirect("domains:list")
    return render(request, "shared/form.html", {"form": form, "title": "Registrar dominio", "subtitle": "Control de compra, proveedor, vencimiento y renovación. No guardes contraseñas aquí."})

@role_required("developer")
def domain_edit(request, pk):
    obj = get_object_or_404(Domain, pk=pk)
    if not request.user.is_manager and not (obj.project and obj.project.assignments.filter(user=request.user, area="development").exists()):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Este dominio no pertenece a un proyecto asignado a Desarrollo.")
    form = DomainForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save(); log_activity(request.user, "domains", "update", obj); messages.success(request, "Dominio actualizado."); return redirect("domains:list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar dominio", "subtitle": obj.domain_name})
