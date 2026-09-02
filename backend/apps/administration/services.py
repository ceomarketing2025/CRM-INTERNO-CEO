from django.db import transaction
from django.utils import timezone
from apps.audit.services import log_activity
from apps.clients.models import Client
from apps.plans.models import ClientPlan
from apps.projects.models import Project


@transaction.atomic
def register_website_client(*, user, cleaned_data):
    client = Client.objects.create(
        first_name=cleaned_data["first_name"],
        last_name=cleaned_data["last_name"],
        identity_document=cleaned_data.get("identity_document", ""),
        business_name=cleaned_data["business_name"],
        phone=cleaned_data["phone"],
        email=cleaned_data.get("email", ""),
        status="active",
        notes=cleaned_data.get("notes", ""),
        created_by=user,
    )
    plan = cleaned_data["plan"]
    client_plan = ClientPlan.objects.create(
        client=client,
        plan=plan,
        agreed_price=plan.base_price,
        currency=plan.currency,
        purchase_date=timezone.localdate(),
        start_date=timezone.localdate(),
        status="active",
        payment_status="pending",
        notes="Plan seleccionado durante el alta administrativa.",
        created_by=user,
    )
    project = Project.objects.create(
        client=client,
        purchased_plan=client_plan,
        name=f"Sitio web - {client.business_name}",
        project_type="website",
        status="design_intake",
        progress=10,
        summary="Alta administrativa completada. Pendiente reunión de asesoría visual.",
        created_by=user,
    )
    log_activity(user, "administration", "website_intake", project, f"Alta de {client.business_name} con {plan.name}")
    return client, client_plan, project
