from django.contrib import messages
from django.shortcuts import redirect, render
from apps.core.decorators import role_required
from apps.projects.models import Project
from .forms import WebsiteClientIntakeForm
from .services import register_website_client


@role_required("administration")
def dashboard(request):
    recent = Project.objects.select_related("client", "purchased_plan__plan").filter(project_type="website")[:12]
    return render(request, "administration/dashboard.html", {"recent_projects": recent})


@role_required("administration")
def website_intake(request):
    form = WebsiteClientIntakeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client, client_plan, project = register_website_client(user=request.user, cleaned_data=form.cleaned_data)
        messages.success(request, f"Cliente creado y enviado a Diseño: {client.business_name} · {client_plan.plan.name}.")
        return redirect("projects:detail", pk=project.pk)
    return render(request, "administration/intake.html", {"form": form})
