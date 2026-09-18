
from django.conf import settings


def _navigation_context(request):
    match = getattr(request, "resolver_match", None)
    namespace = getattr(match, "namespace", "") or ""
    url_name = getattr(match, "url_name", "") or ""

    group = "dashboard"
    module = "Dashboard"
    page = "Inicio"

    if namespace == "marketing" and url_name in {
        "general_audit",
        "general_audit_check",
        "social_tracking",
        "social_tracking_audit",
    }:
        group, module, page = "audit", "Auditoría", "Auditoría Proyectos"

    elif namespace == "operations" and url_name == "development_tasks":
        group, module, page = "development", "Desarrollo", "Tareas"

    elif namespace == "operations" and url_name in {
        "web_production_sheet",
        "web_production_quick_toggle",
    }:
        group, module, page = "development", "Desarrollo", "Ficha de producción"

    elif namespace == "dashboard":
        user = getattr(request, "user", None)

        if (
            user
            and getattr(user, "is_authenticated", False)
            and (
                getattr(user, "is_manager", False)
                or getattr(user, "is_superuser", False)
            )
        ):
            group, module, page = (
                "dashboard",
                "Dashboard Gerencia",
                "Resumen ejecutivo",
            )
        else:
            group, module, page = (
                "dashboard",
                "Dashboard Empleados",
                "Resumen operativo",
            )

    elif namespace == "socialmedia":
        group, module = "social_media", "Social Media"

        page = (
            "Suscripciones"
            if url_name == "dashboard"
            else (
                "Nueva suscripción"
                if url_name == "create"
                else "Control por etapas"
            )
        )

    elif namespace == "sales":
        group, module, page = (
            "sales",
            "Vendedores",
            "Panel comercial",
        )

    elif namespace == "design":
        group, module = "design", "Diseño"

        page = (
            "Tareas de Diseño"
            if url_name
            in {
                "tasks",
                "task_create",
                "task_edit",
                "task_toggle",
                "task_cycle_update",
                "project_tasks",
            }
            else "Información Diseño"
        )

    elif namespace == "marketing":
        group, module = "marketing", "Marketing"

        if url_name in {
            "tasks",
            "task_create",
            "task_edit",
            "task_toggle",
        }:
            page = "Tareas de Marketing"

        elif (
            url_name.startswith("campaign")
            or url_name == "digital_ads"
        ):
            page = "Campañas Ads"

        elif (
            url_name.startswith("social_plan")
            or url_name.startswith("social_daily")
        ):
            page = "Operación Social Media"

        else:
            page = "Información Marketing"

    elif namespace == "questionnaires":
        group, module = "development", "Desarrollo"

        if url_name in {
            "seo_status",
            "seo_status_import",
            "seo_status_detail",
        }:
            page = "Matriz SEO"

        elif url_name == "development_dashboard":
            page = "Tareas"

        else:
            page = "Información"

    elif namespace == "projects" or namespace == "handoff":
        group, module = "projects", "Proyectos"

        page = (
            "Resumen del proyecto"
            if namespace == "handoff"
            else "Proyectos"
        )

    elif namespace == "plans":
        group, module, page = (
            "plans",
            "Planes",
            "Catálogo",
        )

    elif namespace == "reminders":
        group, module = "agenda", "Agenda"

        page = (
            "Reuniones"
            if url_name.startswith("meeting")
            else "Recordatorios"
        )

        if "calendar" in url_name:
            page = "Calendario"

    elif namespace in {
        "clients",
        "finance",
        "administration",
    }:
        group, module = (
            "administration",
            "Administración",
        )

        page = {
            "clients": "Clientes",
            "finance": "Billetera / Finanzas",
            "administration": "Administración",
        }.get(
            namespace,
            "Administración",
        )

        if (
            namespace == "finance"
            and url_name.startswith("operating")
        ):
            page = "Gastos operativos"

    elif namespace == "operations":
        if (
            url_name == "credential_detail"
            and not getattr(
                getattr(
                    request,
                    "user",
                    None,
                ),
                "is_manager",
                False,
            )
        ):
            group, module, page = (
                "projects",
                "Proyectos",
                "Credencial compartida",
            )

        else:
            group, module = (
                "administration",
                "Administración",
            )

            if url_name.startswith("credential"):
                page = "Credenciales"

            elif url_name.startswith("general"):
                page = "Dominios y Hosting"

            elif url_name.startswith("production"):
                page = "Producción comercial"

            else:
                page = "Administración"

    elif namespace == "audit":
        if url_name in {
            "management_tasks",
            "management_task_create",
            "management_task_edit",
            "management_task_options",
            "management_task_status",
        }:
            group, module, page = (
                "management_tasks",
                "Gerencia",
                "Tareas del equipo",
            )

        else:
            group, module = (
                "audit",
                "Auditoría",
            )

            if url_name in {
                "projects",
                "project_check",
            }:

