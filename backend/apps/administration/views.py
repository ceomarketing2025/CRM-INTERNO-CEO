from django.shortcuts import redirect, render

from apps.core.decorators import manager_required
from apps.projects.models import Project


@manager_required
def dashboard(request):
    recent = Project.objects.select_related("client").prefetch_related("contracted_plans__plan")[:12]
    return render(request, "administration/dashboard.html", {"recent_projects": recent})


@manager_required
def website_intake(request):
    """Compatibilidad con la ruta histórica.

    Desde V9 el alta combinada desaparece: Cliente y Proyecto son procesos separados.
    """
    return redirect("clients:create")
