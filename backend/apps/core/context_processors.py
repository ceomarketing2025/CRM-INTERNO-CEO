from django.conf import settings


def _navigation_context(request):
    match = getattr(request, "resolver_match", None)
    namespace = getattr(match, "namespace", "") or ""
    url_name = getattr(match, "url_name", "") or ""

    group = "dashboard"
    module = "Dashboard"
    page = "Inicio"

    if namespace == "marketing" and url_name in {
        "general_audit", "general_audit_check", "social_tracking", "social_tracking_audit"
    }:
        group, module, page = "audit", "Auditor├¡a", "Auditor├¡a Proyectos"
    elif namespace == "operations" and url_name == "development_project_styles":
        group, module, page = "development", "Desarrollo", "Estilos"
    elif namespace == "operations" and url_name in {
        "web_production_sheet", "web_production_quick_toggle"
    }:
        group, module, page = "development", "Desarrollo", "Ficha de producción"
    elif namespace == "dashboard":
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False) and (getattr(user, "is_manager", False) or getattr(user, "is_superuser", False)):
            group, module, page = "dashboard", "Dashboard Gerencia", "Resumen ejecutivo"
        else:
            group, module, page = "dashboard", "Dashboard Empleados", "Resumen operativo"
    elif namespace == "socialmedia":
        group, module = "social_media", "Social Media"
        page = "Suscripciones" if url_name == "dashboard" else ("Nueva suscripci├│n" if url_name == "create" else "Control por etapas")
    elif namespace == "sales":
        group, module, page = "sales", "Vendedores", "Panel comercial"
    elif namespace == "design":
        group, module = "design", "Dise├▒o"
        page = "Tareas de Dise├▒o" if url_name in {
            "tasks", "task_create", "task_edit", "task_toggle", "task_cycle_update", "project_tasks",
        } else "Informaci├│n Dise├▒o"
    elif namespace == "marketing":
        group, module = "marketing", "Marketing"
        if url_name in {"tasks", "task_create", "task_edit", "task_toggle"}:
            page = "Tareas de Marketing"
        elif url_name.startswith("campaign") or url_name == "digital_ads":
            page = "Campa├▒as Ads"
        elif url_name.startswith("social_plan") or url_name.startswith("social_daily"):
            page = "Operaci├│n Social Media"
        else:
            page = "Informaci├│n Marketing"
    elif namespace == "questionnaires":
        group, module = "development", "Desarrollo"
        if url_name in {"seo_status", "seo_status_import", "seo_status_detail"}:
            page = "Estado SEO"
        elif url_name == "development_dashboard":
            page = "Resumen de tareas"
        else:
            page = "Informaci├│n Desarrollo"
    elif namespace == "projects" or namespace == "handoff":
        group, module = "projects", "Proyectos"
        page = "Resumen del proyecto" if namespace == "handoff" else "Proyectos"
    elif namespace == "plans":
        group, module, page = "plans", "Planes", "Cat├ílogo"
    elif namespace == "reminders":
        group, module = "agenda", "Agenda"
        page = "Reuniones" if url_name.startswith("meeting") else "Recordatorios"
        if "calendar" in url_name:
            page = "Calendario"
    elif namespace in {"clients", "finance", "administration"}:
        group, module = "administration", "Administraci├│n"
        page = {
            "clients": "Clientes",
            "finance": "Billetera / Finanzas",
            "administration": "Administraci├│n",
        }.get(namespace, "Administraci├│n")
        if namespace == "finance" and url_name.startswith("operating"):
            page = "Gastos operativos"
    elif namespace == "operations":
        if url_name == "credential_detail" and not getattr(getattr(request, "user", None), "is_manager", False):
            group, module, page = "projects", "Proyectos", "Credencial compartida"
        else:
            group, module = "administration", "Administraci├│n"
            if url_name.startswith("credential"):
                page = "Credenciales"
            elif url_name.startswith("general"):
                page = "Dominios y Hosting"
            elif url_name.startswith("production"):
                page = "Producci├│n comercial"
            else:
                page = "Administraci├│n"
    elif namespace == "audit":
        if url_name in {"management_tasks", "management_task_create", "management_task_edit", "management_task_options", "management_task_status"}:
            group, module, page = "management_tasks", "Gerencia", "Tareas del equipo"
        else:
            group, module = "audit", "Auditor├¡a"
            if url_name in {"projects", "project_check"}:
                page = "Auditor├¡a Proyectos"
            elif url_name in {"subscriptions", "subscription_check"}:
                page = "Auditor├¡a Suscripciones"
            else:
                page = "Logs del sistema"
    elif namespace == "accounts" and url_name.startswith("user"):
        group, module, page = "configuration", "Configuraci├│n", "Usuarios"
    elif namespace == "domains":
        group, module, page = "development", "Desarrollo", "Dominios"

    return {
        "active_nav_group": group,
        "current_module_label": module,
        "current_page_label": page,
        "current_namespace": namespace,
        "current_url_name": url_name,
    }


def _management_area_context(request, nav_context):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    namespace = nav_context["current_namespace"]
    url_name = nav_context["current_url_name"]
    area = None
    area_label = ""

    # Dise├▒o integra las tareas de Gerencia directamente dentro de /design/tasks/
    # para que sean parte del dataset y filtros del ├írea, no un panel global.
    if namespace == "design" and url_name in {"tasks", "project_tasks"}:
        return {"show_management_tasks_panel": False}
    elif namespace == "marketing" and url_name == "tasks":
        area, area_label = "marketing", "Marketing"
    elif namespace == "questionnaires" and url_name == "development_dashboard":
        area, area_label = "development", "Desarrollo"
    elif namespace == "sales" and url_name == "dashboard":
        area, area_label = "sales", "Vendedores"
    elif namespace == "administration" and url_name == "dashboard":
        area, area_label = "administration", "Administraci├│n"

    if not area:
        return {"show_management_tasks_panel": False}

    # Import local para evitar cargar el modelo de Auditor├¡a durante el arranque
    # del m├│dulo de configuraci├│n.
    from apps.audit.models import ManagementTask

    tasks = ManagementTask.objects.select_related("assigned_to", "client", "project", "created_by").filter(area=area)
    if not (getattr(user, "is_manager", False) or getattr(user, "is_superuser", False)):
        tasks = tasks.filter(assigned_to=user)

    return {
        "show_management_tasks_panel": True,
        "management_area_tasks": tasks[:12],
        "management_area_label": area_label,
        "management_area_key": area,
    }


def global_ui(request):
    user = getattr(request, "user", None)
    role = getattr(user, "role", "") if user and getattr(user, "is_authenticated", False) else ""
    nav_context = _navigation_context(request)
    context = {
        "PROJECT_NAME": settings.PROJECT_NAME,
        "current_role": role,
    }
    if user and getattr(user, "is_authenticated", False):
        from apps.operations.models import DevelopmentTaskNotification
        context["development_task_unread_count"] = (
            DevelopmentTaskNotification.objects
            .filter(recipient=user, is_read=False)
            .count()
        )
    else:
        context["development_task_unread_count"] = 0
    context.update(nav_context)
    context.update(_management_area_context(request, nav_context))
    return context
