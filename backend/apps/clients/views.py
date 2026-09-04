from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.services import log_activity
from apps.core.decorators import role_required
from .forms import ClientForm
from .models import Client


@login_required
def client_list(request):
    q = request.GET.get("q", "").strip()
    clients = Client.objects.all()
    if q:
        clients = clients.filter(
            Q(business_name__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
        )
    return render(request, "clients/list.html", {"clients": clients, "q": q})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(
        Client.objects.prefetch_related("projects__contracted_plans__plan", "purchased_plans", "domains"),
        pk=pk,
    )
    return render(request, "clients/detail.html", {"client": client})


@role_required("administration")
def client_create(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.created_by = request.user
        client.save()
        log_activity(request.user, "clients", "create", client, f"Cliente {client.business_name} creado")
        messages.success(request, "Cliente creado. Ahora puedes crear uno o varios proyectos para este cliente.")
        return redirect("clients:detail", pk=client.pk)
    return render(request, "shared/form.html", {
        "form": form,
        "title": "Nuevo cliente",
        "subtitle": "Solo datos del cliente. Los planes y servicios se asignan dentro del proyecto.",
    })


@role_required("administration")
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request.user, "clients", "update", client)
        messages.success(request, "Cliente actualizado.")
        return redirect("clients:detail", pk=client.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Editar cliente", "subtitle": client.business_name})
