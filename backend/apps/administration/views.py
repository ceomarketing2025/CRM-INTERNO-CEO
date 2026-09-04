from django.shortcuts import redirect, render

from apps.core.decorators import role_required
from apps.projects.models import Project


@role_required("administration")
def dashboard(request):
    recent = Project.objects.select_related("client").prefetch_related("contracted_plans__plan")[:12]
    return render(request, "administration/dashboard.html", {"recent_projects": recent})


@role_required("administration")
def website_intake(request):
    """Compatibilidad con la ruta histórica.

    Desde V9 el alta combinada desaparece: Cliente y Proyecto son procesos separados.
    """
    return redirect("clients:create")
