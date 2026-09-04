from django.conf import settings


def _navigation_context(request):
    match = getattr(request, "resolver_match", None)
    namespace = getattr(match, "namespace", "") or ""
    url_name = getattr(match, "url_name", "") or ""

    group = "dashboard"
    module = "Dashboard"
    page = "Inicio"

    # Rutas especiales primero: algunas viven técnicamente en Marketing u Operations,
    # pero conceptualmente pertenecen a Control o Desarrollo.
    if namespace == "marketing" and url_name in {
        "general_audit", "general_audit_check", "social_tracking", "social_tracking_audit"
    }:
        group, module, page = "control", "Control / Auditoría", "Auditoría General"
    elif namespace == "operations" and url_name in {
        "web_production_sheet", "web_production_quick_toggle"
    }:
        group, module, page = "development", "Desarrollo", "Resumen de tareas"
    elif namespace == "dashboard":
        group, module, page = "dashboard", "Dashboard", "Inicio"
    elif namespace == "design":
        group, module = "design", "Diseño"
        page = "Tareas de Diseño" if url_name in {
            "tasks", "social_media", "task_create", "task_edit", "task_toggle",
            "task_cycle_update", "social_media_assign", "social_media_detail",
            "social_media_assignment_edit",
        } else "Información Diseño"
    elif namespace == "marketing":
        group, module = "marketing", "Marketing"
        if url_name in {"tasks", "task_create"}:
            page = "Tareas de Marketing"
        elif url_name.startswith("campaign") or url_name == "digital_ads":
            page = "Campañas Ads"
        elif url_name.startswith("social_plan") or url_name.startswith("social_daily"):
            page = "Operación Social Media"
        else:
            page = "Información Marketing"
    elif namespace == "questionnaires":
        group, module = "development", "Desarrollo"
        if url_name in {"seo_status", "seo_status_import"}:
            page = "Estado SEO"
        elif url_name == "development_dashboard":
            page = "Resumen de tareas"
        else:
            page = "Información Desarrollo"
    elif namespace in {"clients", "finance"}:
        group, module = "administration", "Administración"
        page = {
            "clients": "Clientes",
            "finance": "Billetera / Finanzas",
        }.get(namespace, "Administración")
        if namespace == "finance" and url_name.startswith("operating"):
            page = "Gastos operativos"
    elif namespace == "operations":
        group, module = "administration", "Administración"
        if url_name.startswith("credential"):
            page = "Credenciales"
        elif url_name.startswith("general"):
            page = "Dominios y Hosting"
        elif url_name.startswith("production"):
            page = "Producción comercial"
        else:
            page = "Administración"
    elif namespace in {"plans", "projects", "reminders"}:
        group, module = "control", "Control / Auditoría"
        if namespace == "plans":
            page = "Planes"
        elif namespace == "projects":
            page = "Proyectos"
        elif url_name.startswith("meeting"):
            page = "Reuniones"
        else:
            page = "Recordatorios"
    elif namespace == "accounts" and url_name.startswith("user"):
        group, module, page = "configuration", "Configuración", "Usuarios"
    elif namespace == "audit" and url_name == "logs":
        group, module, page = "configuration", "Configuración", "Logs del sistema"
    elif namespace == "handoff":
        group, module, page = "control", "Control / Auditoría", "Resumen del proyecto"
    elif namespace == "domains":
        # La app histórica continúa disponible, pero ya no se muestra dentro de Desarrollo.
        group, module, page = "administration", "Administración", "Dominios"

    return {
        "active_nav_group": group,
        "current_module_label": module,
        "current_page_label": page,
        "current_namespace": namespace,
        "current_url_name": url_name,
    }


def global_ui(request):
    user = getattr(request, "user", None)
    role = getattr(user, "role", "") if user and getattr(user, "is_authenticated", False) else ""
    context = {
        "PROJECT_NAME": settings.PROJECT_NAME,
        "current_role": role,
    }
    context.update(_navigation_context(request))
    return context
