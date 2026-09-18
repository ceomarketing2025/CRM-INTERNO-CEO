def _infer_project_id(obj):
    if not obj:
        return None
    if obj.__class__.__name__ == "Project":
        return getattr(obj, "pk", None)
    direct = getattr(obj, "project_id", None)
    if direct:
        return direct
    project = getattr(obj, "project", None)
    if project is not None:
        return getattr(project, "pk", None)
    questionnaire = getattr(obj, "questionnaire", None)
    if questionnaire is not None:
        return getattr(questionnaire, "project_id", None)
    workspace = getattr(obj, "workspace", None)
    if workspace is not None:
        return getattr(workspace, "project_id", None)
    palette = getattr(obj, "palette", None)
    if palette is not None:
        return getattr(palette, "project_id", None)
    plan = getattr(obj, "plan", None)
    if plan is not None:
        return getattr(plan, "project_id", None)
    county = getattr(obj, "county", None)
    if county is not None:
        sheet = getattr(county, "sheet", None)
        if sheet is not None:
            return getattr(sheet, "project_id", None)
    sheet = getattr(obj, "sheet", None)
    if sheet is not None:
        return getattr(sheet, "project_id", None)
    return None


def log_activity(user, module, action, obj=None, description="", metadata=None):
    from .models import ActivityLog
    payload = dict(metadata or {})
    project_id = _infer_project_id(obj)
    if project_id and "project_id" not in payload:
        payload["project_id"] = project_id
    return ActivityLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        module=module,
        action=action,
        entity_type=obj.__class__.__name__ if obj else "",
        entity_id=str(getattr(obj, "pk", "")) if obj else "",
        description=description,
        metadata=payload,
    )


def _progress_state(progress):
    progress = int(progress or 0)
    if progress >= 100:
        return "green"
    if progress > 50:
        return "yellow"
    return "red"


def _social_media_cycle_label(cycle):
    """Etiqueta segura para SocialMediaCycle.

    SocialMediaCycle no tiene un campo/property ``label``: su identidad real se
    deriva de period_start y due_date. Mantener esta lógica aquí evita que
    Auditoría dependa de atributos que no existen en el módulo Social Media.
    """
    if not cycle:
        return "Ciclo actual"
    start = getattr(cycle, "period_start", None)
    due = getattr(cycle, "due_date", None)
    if start and due:
        return f"{start:%d/%m/%Y} → {due:%d/%m/%Y}"
    if start:
        return f"Desde {start:%d/%m/%Y}"
    return "Ciclo actual"


def _ensure_general_check(*, project, source_key, area, category, label):
    from .models import GeneralAuditCheck
    check, _ = GeneralAuditCheck.objects.get_or_create(
        source_key=source_key,
        defaults={
            "project": project,
            "area": area,
            "category": category,
            "label": label[:240],
        },
    )
    changed = []
    for field, value in {
        "project": project,
        "area": area,
        "category": category,
        "label": label[:240],
    }.items():
        current = getattr(check, field)
        if field == "project":
            if check.project_id != project.pk:
                check.project = project
                changed.append("project")
        elif current != value:
            setattr(check, field, value)
            changed.append(field)
    if changed:
        check.save(update_fields=changed + ["updated_at"])
    return check


def _general_audit_row(*, project, source_key, area, area_label, category, label,
                       source_progress, source_status, source_updated_at, source_url="",
                       detail="", counts_for_progress=True, historical=False, workflow_reviewable=True):
    from .models import GeneralAuditCheck

    progress = max(0, min(100, int(source_progress or 0)))
    check = _ensure_general_check(
        project=project,
        source_key=source_key,
        area=area,
        category=category,
        label=label,
    )
    decision = getattr(check, "decision", GeneralAuditCheck.Decision.APPROVED if check.is_ready else GeneralAuditCheck.Decision.PENDING)
    was_reviewed = decision != GeneralAuditCheck.Decision.PENDING
    audit_current = bool(
        was_reviewed
        and check.reviewed_at
        and (not source_updated_at or check.reviewed_at >= source_updated_at)
    )
    if was_reviewed and not audit_current:
        audit_label, audit_state = "Cambios nuevos", "yellow"
    elif decision == GeneralAuditCheck.Decision.APPROVED:
        audit_label, audit_state = "Aprobado", "green"
    elif decision == GeneralAuditCheck.Decision.REJECTED:
        audit_label, audit_state = "Rechazado", "red"
    else:
        audit_label, audit_state = "Por revisar", "muted"
    return {
        "check": check,
        "source_key": source_key,
        "project": project,
        "client": project.client,
        "area": area,
        "area_label": area_label,
        "category": category,
        "label": label,
        "source_done": progress >= 100,
        "source_progress": progress,
        "source_state": _progress_state(progress),
        "source_status": source_status,
        "source_updated_at": source_updated_at,
        "source_url": source_url,
        "detail": detail or "",
        "audit_current": audit_current,
        "audit_label": audit_label,
        "audit_state": audit_state,
        "audit_decision": decision,
        "audit_note": check.note or "",
        "counts_for_progress": bool(counts_for_progress),
        "historical": bool(historical),
        "workflow_reviewable": bool(workflow_reviewable),
    }


def build_general_audit_rows(include_recurring=True):
    """Construye la auditoría desde las fuentes reales de las tres áreas.

    Las tareas recurrentes de Diseño conservan periodos históricos, pero solo el
    periodo vigente entra al porcentaje actual. Así un nuevo ciclo vuelve a rojo/
    amarillo aunque los meses anteriores estén publicados.
    """
    from django.urls import reverse
    from apps.design.models import DesignTask
    from apps.design.services import design_task_progress, ensure_current_design_task_cycle
    from apps.marketing.models import MarketingChecklistItem, MarketingTask, MarketingWorkspace
    from apps.questionnaires.models import ProjectQuestionnaire
    from apps.questionnaires.models.choices import AnswerState
    from apps.operations.models import (
        CompleteStatus,
        WebProductionPage,
        WebProductionCounty,
        WebProductionCountyService,
        WebProductionCity,
    )

    rows = []

    # DISEÑO: tarea única o tarea recurrente con historial por periodo.
    design_tasks = DesignTask.objects.select_related(
        "project_plan__project__client", "project_plan__plan", "assigned_to"
    ).prefetch_related("cycles__delivery_items").filter(project_plan__is_active=True)
    for task in design_tasks:
        project = task.project_plan.project
        category = task.project_plan.plan.name
        if task.task_type == DesignTask.TaskType.CONTENT:
            if not include_recurring:
                # Los controles recurrentes pertenecen a Auditoría Suscripciones.
                # Auditoría Proyectos solo contiene actividades únicas.
                continue
            current = ensure_current_design_task_cycle(task)
            if task.needs_configuration or not current:
                rows.append(_general_audit_row(
                    project=project,
                    source_key=f"design:task:{task.pk}:config",
                    area="design",
                    area_label="Diseño",
                    category=category,
                    label=task.title,
                    source_progress=0,
                    source_status="Configurar renovación",
                    source_updated_at=task.updated_at,
                    source_url=reverse("design:task_edit", args=[task.pk]),
                    detail="Define frecuencia semanal, quincenal o mensual antes de iniciar el control de publicaciones.",
                ))
                continue

            cycles = list(task.cycles.all().order_by("-period_start")[:8])
            if current.pk not in {cycle.pk for cycle in cycles}:
                cycles.insert(0, current)
            for cycle in cycles:
                is_current = cycle.pk == current.pk
                rows.append(_general_audit_row(
                    project=project,
                    source_key=f"design:cycle:{cycle.pk}",
                    area="design",
                    area_label="Diseño",
                    category=category,
                    label=f"{task.title} · {cycle.label}",
                    source_progress=cycle.progress_percent,
                    source_status=cycle.state_label,
                    source_updated_at=cycle.updated_at,
                    source_url=reverse("design:project_tasks", args=[project.pk]),
                    detail="Periodo actual" if is_current else "Periodo histórico",
                    counts_for_progress=is_current,
                    historical=not is_current,
                ))
        else:
            state = design_task_progress(task)
            rows.append(_general_audit_row(
                project=project,
                source_key=f"design:task:{task.pk}",
                area="design",
                area_label="Diseño",
                category=category,
                label=task.title,
                source_progress=state["progress"],
                source_status=state["label"],
                source_updated_at=task.updated_at,
                source_url=reverse("design:project_tasks", args=[project.pk]),
                detail=task.description,
                workflow_reviewable=task.status == DesignTask.Status.REVIEW,
            ))

    # MARKETING: Gerencia audita los cuatro módulos que Marketing ve en su panel,
    # no cada check interno por separado. El detalle sigue leyendo las fuentes reales.
    marketing_progress = {"todo": 0, "doing": 60, "review": 80, "done": 100}
    marketing_groups = [
        {
            "key": "google_business",
            "label": "Google Business",
            "check_areas": {"google_profile"},
            "task_area": "google_business",
            "url_name": "marketing:google_business",
        },
        {
            "key": "google_lsa",
            "label": "Google LSA",
            "check_areas": {"google_lsa"},
            "task_area": "google_lsa",
            "url_name": "marketing:google_lsa",
        },
        {
            "key": "digital_ads",
            "label": "Publicidad Digital",
            "check_areas": {"traditional", "meta_ads", "google_ads", "tiktok_ads", "digital_ads"},
            "task_area": "digital_ads",
            "url_name": "marketing:digital_ads",
        },
    ]

    workspaces = (
        MarketingWorkspace.objects.select_related("project__client")
        .prefetch_related("checklist_items", "project__marketing_tasks")
        .all()
    )
    for workspace in workspaces:
        project = workspace.project
        active_checks = [item for item in workspace.checklist_items.all() if item.active]
        project_tasks = list(project.marketing_tasks.all())
        for group in marketing_groups:
            checks = [item for item in active_checks if item.area in group["check_areas"]]
            tasks = [task for task in project_tasks if task.area == group["task_area"]]
            values = [100 if item.status == "complete" else 0 for item in checks]
            values += [marketing_progress.get(task.status, 0) for task in tasks]
            if not values:
                # El módulo puede existir visualmente, pero no se audita hasta tener
                # controles/tareas reales que correspondan al proyecto.
                continue
            progress = round(sum(values) / len(values))
            completed_checks = sum(1 for item in checks if item.status == "complete")
            done_tasks = sum(1 for task in tasks if task.status == "done")
            pending_labels = [item.label for item in checks if item.status != "complete"][:3]
            pending_labels += [task.title for task in tasks if task.status != "done"][:3]
            timestamps = [workspace.updated_at]
            timestamps += [item.updated_at for item in checks]
            timestamps += [task.updated_at for task in tasks]
            detail_parts = [f"{completed_checks}/{len(checks)} checks completos"]
            if tasks:
                detail_parts.append(f"{done_tasks}/{len(tasks)} tareas finalizadas")
            if pending_labels:
                detail_parts.append("Pendiente: " + "; ".join(pending_labels[:4]))
            rows.append(_general_audit_row(
                project=project,
                source_key=f"marketing:group:{project.pk}:{group['key']}",
                area="marketing",
                area_label="Marketing",
                category="Módulos de Marketing",
                label=group["label"],
                source_progress=progress,
                source_status="Completo" if progress >= 100 else "Trabajo pendiente",
                source_updated_at=max(timestamps),
                source_url=reverse(group["url_name"], args=[project.pk]),
                detail=" · ".join(detail_parts),
            ))

    # SOCIAL MEDIA: cuarto módulo del panel de Marketing. La auditoría detallada
    # por semana sigue viviendo en Auditoría Suscripciones; aquí solo hay resumen.
    from apps.design.services import ensure_current_social_media_cycle
    from apps.plans.models import ClientPlan
    from apps.plans.models.choices import ServiceType
    social_assignments = (
        ClientPlan.objects.select_related("client", "plan")
        .filter(is_active=True, plan__service_type=ServiceType.SOCIAL_MEDIA)
        .prefetch_related("project_links__project", "social_media_cycles__items")
    )
    social_by_project = {}
    for assignment in social_assignments:
        link = assignment.project_links.filter(is_active=True).select_related("project__client").first()
        if not link:
            continue
        cycle = ensure_current_social_media_cycle(assignment)
        items = list(cycle.items.all()) if cycle else []
        bucket = social_by_project.setdefault(link.project_id, {"project": link.project, "items": [], "assignments": []})
        bucket["items"].extend(items)
        bucket["assignments"].append(assignment)

    for bucket in social_by_project.values():
        project = bucket["project"]
        items = bucket["items"]
        total = len(items)
        published = sum(1 for item in items if item.is_complete)
        ready = sum(1 for item in items if item.ready)
        progress = round(published * 100 / total) if total else 0
        timestamps = [item.updated_at for item in items] or [project.updated_at]
        detail = f"{published}/{total} publicaciones completadas · {ready}/{total} piezas listas por Diseño"
        rows.append(_general_audit_row(
            project=project,
            source_key=f"marketing:group:{project.pk}:social_media",
            area="marketing",
            area_label="Marketing",
            category="Módulos de Marketing",
            label="Social Media",
            source_progress=progress,
            source_status="Ciclo publicado" if total and published >= total else "Publicaciones pendientes",
            source_updated_at=max(timestamps),
            source_url=reverse("socialmedia:dashboard"),
            detail=detail,
        ))

    # DESARROLLO: Auditoría trabaja por ETAPAS reales, no por cada pregunta.
    # La ficha técnica ya está organizada en QuestionnaireSection; se calcula el
    # avance de cada sección leyendo sus respuestas sin modificar Desarrollo.
    questionnaires = ProjectQuestionnaire.objects.select_related(
        "project__client", "template"
    ).prefetch_related("template__sections__questions", "answers__question")
    completed_states = {AnswerState.CONFIRMED, AnswerState.NO, AnswerState.NOT_APPLICABLE}
    for questionnaire in questionnaires:
        answer_map = {answer.question_id: answer for answer in questionnaire.answers.all()}
        for section in questionnaire.template.sections.all().order_by("order", "id"):
            questions = list(section.questions.all().order_by("order", "id"))
            if not questions:
                continue
            section_answers = [answer_map.get(question.pk) for question in questions]
            done = sum(1 for answer in section_answers if answer and answer.state in completed_states)
            total = len(questions)
            progress = round(done * 100 / total) if total else 0
            timestamps = [answer.updated_at for answer in section_answers if answer]
            source_updated_at = max(timestamps) if timestamps else questionnaire.updated_at
            pending = max(total - done, 0)
            detail = (
                f"{done}/{total} campos completos"
                if pending
                else f"{total}/{total} campos completos · etapa lista"
            )
            rows.append(_general_audit_row(
                project=questionnaire.project,
                source_key=f"development:section:{questionnaire.pk}:{section.pk}",
                area="development",
                area_label="Desarrollo",
                category="Ficha técnica · Etapas",
                label=section.title,
                source_progress=progress,
                source_status="Etapa completa" if progress >= 100 else "Etapa en progreso",
                source_updated_at=source_updated_at,
                source_url=reverse("questionnaires:fill", args=[questionnaire.pk]),
                detail=detail,
            ))

    # DESARROLLO: la ficha de producción también se resume por etapa.
    # Páginas/condados/servicios/ciudades continúan siendo los registros reales,
    # pero Gerencia audita el bloque completo y no cada fila individual.
    production_sources = [
        (WebProductionPage, "Páginas", "pages"),
        (WebProductionCounty, "Condados / áreas", "counties"),
        (WebProductionCountyService, "Servicios por condado", "county_services"),
        (WebProductionCity, "Ciudades / indexación", "cities"),
    ]
    production_by_project = {}
    for model, stage_label, stage_key in production_sources:
        qs = model.objects.all()
        if model is WebProductionCountyService:
            qs = qs.select_related("county__sheet__project__client")
        else:
            qs = qs.select_related("sheet__project__client")
        for item in qs:
            sheet = item.county.sheet if model is WebProductionCountyService else item.sheet
            project = sheet.project
            bucket = production_by_project.setdefault(
                (project.pk, stage_key),
                {"project": project, "label": stage_label, "key": stage_key, "items": []},
            )
            bucket["items"].append(item)

    for bucket in production_by_project.values():
        project = bucket["project"]
        items = bucket["items"]
        total = len(items)
        done = sum(1 for item in items if item.state == CompleteStatus.COMPLETE)
        progress = round(done * 100 / total) if total else 0
        source_updated_at = max((item.updated_at for item in items), default=project.updated_at)
        rows.append(_general_audit_row(
            project=project,
            source_key=f"development:production-stage:{project.pk}:{bucket['key']}",
            area="development",
            area_label="Desarrollo",
            category="Ficha de producción · Etapas",
            label=bucket["label"],
            source_progress=progress,
            source_status="Etapa completa" if total and done >= total else "Etapa en progreso",
            source_updated_at=source_updated_at,
            source_url=reverse("operations:web_production_sheet", args=[project.pk]),
            detail=f"{done}/{total} elementos listos" if total else "Sin elementos configurados",
        ))

    # TAREAS CREADAS POR GERENCIA: cuando están vinculadas a un proyecto se
    # incorporan como una actividad única del área y se auditan desde aquí.
    from .models import ManagementTask
    management_progress = {"todo": 0, "doing": 50, "paused": 35, "changes": 70, "review": 90, "done": 100}
    management_urls = {
        "design": "design:tasks",
        "marketing": "marketing:tasks",
        "development": "questionnaires:development_dashboard",
        "sales": "sales:dashboard",
        "administration": "administration:dashboard",
    }
    management_labels = dict(ManagementTask.Area.choices)
    for task in ManagementTask.objects.select_related("project__client", "assigned_to").exclude(project__isnull=True).filter(area__in=["design", "marketing", "development"]):
        url_name = management_urls.get(task.area)
        rows.append(_general_audit_row(
            project=task.project,
            source_key=f"management:task:{task.pk}",
            area=task.area,
            area_label=management_labels.get(task.area, task.area.title()),
            category="Tareas asignadas por Gerencia",
            label=task.title,
            source_progress=management_progress.get(task.status, 0),
            source_status=task.get_status_display(),
            source_updated_at=task.updated_at,
            source_url=reverse(url_name) if url_name else "",
            detail=task.description,
            workflow_reviewable=task.status == ManagementTask.Status.REVIEW,
        ))

    area_order = {"design": 0, "marketing": 1, "development": 2}
    rows.sort(key=lambda row: (
        row["client"].business_name.lower(),
        area_order.get(row["area"], 9),
        row["historical"],
        row["category"].lower(),
        row["label"].lower(),
    ))
    return rows


def _sync_audited_source_state(*, check, decision, note, user):
    """Sincroniza la decisión de Gerencia con la actividad operativa viva."""
    from .models import GeneralAuditCheck, ManagementTask

    source_key = check.source_key or ""
    if source_key.startswith("design:task:"):
        parts = source_key.split(":")
        if len(parts) == 3 and parts[2].isdigit():
            from apps.design.models import DesignTask
            task = DesignTask.objects.filter(pk=int(parts[2])).first()
            if task and task.task_type == DesignTask.TaskType.STANDARD:
                if decision == GeneralAuditCheck.Decision.APPROVED:
                    task.status = DesignTask.Status.DONE
                    task.status_note = ""
                elif decision == GeneralAuditCheck.Decision.REJECTED:
                    task.status = DesignTask.Status.CHANGES
                    task.status_note = (note or "").strip()
                elif decision == GeneralAuditCheck.Decision.PENDING and task.status == DesignTask.Status.DONE:
                    task.status = DesignTask.Status.REVIEW
                task.updated_by = user
                task.save(update_fields=["status", "status_note", "updated_by", "updated_at"])
        return

    if source_key.startswith("management:task:"):
        parts = source_key.split(":")
        if len(parts) == 3 and parts[2].isdigit():
            task = ManagementTask.objects.filter(pk=int(parts[2])).first()
            if task:
                if decision == GeneralAuditCheck.Decision.APPROVED:
                    task.status = ManagementTask.Status.DONE
                    task.status_note = ""
                elif decision == GeneralAuditCheck.Decision.REJECTED:
                    task.status = ManagementTask.Status.CHANGES
                    task.status_note = (note or "").strip()
                elif decision == GeneralAuditCheck.Decision.PENDING and task.status == ManagementTask.Status.DONE:
                    task.status = ManagementTask.Status.REVIEW
                task.updated_by = user
                task.save(update_fields=["status", "status_note", "updated_by", "updated_at"])


def review_general_audit_check(*, check, user, ready=None, decision=None, note=None):
    from django.utils import timezone
    from .models import GeneralAuditCheck

    if decision is None:
        if ready is True:
            decision = GeneralAuditCheck.Decision.APPROVED
        elif ready is False:
            decision = GeneralAuditCheck.Decision.PENDING
        else:
            decision = GeneralAuditCheck.Decision.PENDING

    allowed = {choice[0] for choice in GeneralAuditCheck.Decision.choices}
    if decision not in allowed:
        decision = GeneralAuditCheck.Decision.PENDING

    check.decision = decision
    check.is_ready = decision == GeneralAuditCheck.Decision.APPROVED
    if note is not None:
        check.note = (note or "").strip()

    # Primero actualizamos la fuente y después sellamos reviewed_at. Así el
    # timestamp de Auditoría queda posterior al cambio que ella misma provoca.
    _sync_audited_source_state(
        check=check, decision=decision, note=check.note, user=user
    )

    if decision == GeneralAuditCheck.Decision.PENDING:
        check.reviewed_at = None
        check.reviewed_by = None
    else:
        check.reviewed_at = timezone.now()
        check.reviewed_by = user

    check.save(update_fields=["decision", "is_ready", "reviewed_at", "reviewed_by", "note", "updated_at"])
    return check


def build_project_audit_rows():
    """Auditoría de proyectos: solo actividades únicas, sin renovaciones."""
    return build_general_audit_rows(include_recurring=False)


def subscription_audit_rows(today=None):
    """Construye la auditoría viva de suscripciones sin duplicar estados.

    Social Media se deriva de SocialMediaContentItem: Diseño usa `ready` y
    Marketing usa `published_networks`/`is_complete`. Las semanas vencidas con
    cualquiera de las dos etapas pendiente quedan en rojo automáticamente.
    Otros productos recurrentes aparecen con su próxima renovación.
    """
    from collections import OrderedDict
    from datetime import timedelta
    from django.db.models import Q
    from django.utils import timezone
    from apps.design.services import ensure_current_social_media_cycle
    from apps.plans.models import ClientPlan
    from apps.plans.models.choices import BillingCycle, RenewalFrequency, ServiceType
    from apps.plans.services import renewal_urgency

    today = today or timezone.localdate()
    subscriptions = (
        ClientPlan.objects.select_related("client", "plan", "assigned_design_user")
        .prefetch_related("project_links__project", "social_media_cycles__items")
        .filter(is_active=True)
        .filter(
            Q(plan__service_type=ServiceType.SOCIAL_MEDIA)
            | Q(plan__billing_cycle__in=[BillingCycle.MONTHLY, BillingCycle.YEARLY, BillingCycle.CUSTOM])
        )
        .exclude(renewal_frequency=RenewalFrequency.NONE)
        .order_by("client__business_name", "plan__name")
        .distinct()
    )

    rows = []
    totals = {
        "subscriptions": 0,
        "social": 0,
        "complete": 0,
        "alerts": 0,
        "design_pending": 0,
        "marketing_pending": 0,
        "audit_approved": 0,
        "audit_rejected": 0,
        "audit_pending": 0,
        "audit_changed": 0,
    }

    for assignment in subscriptions:
        project_link = assignment.project_links.select_related("project").filter(is_active=True).first()
        project = project_link.project if project_link else None
        urgency = renewal_urgency(assignment.renewal_date)
        row = {
            "assignment": assignment,
            "project": project,
            "urgency": urgency,
            "is_social": assignment.plan.service_type == ServiceType.SOCIAL_MEDIA,
            "weeks": [],
            "state": "neutral",
            "state_label": "Suscripción activa",
            "design_percent": None,
            "marketing_percent": None,
            "overall_percent": None,
            "total_items": 0,
            "design_done": 0,
            "marketing_done": 0,
            "overdue_weeks": 0,
            "current_week": None,
        }
        totals["subscriptions"] += 1

        if row["is_social"]:
            totals["social"] += 1
            cycle = ensure_current_social_media_cycle(assignment)
            row["cycle"] = cycle
            items = list(cycle.items.all().order_by("content_type", "sequence", "id")) if cycle else []
            total_items = len(items)
            design_done = sum(1 for item in items if item.ready)
            marketing_done = sum(1 for item in items if item.is_complete)
            row["total_items"] = total_items
            row["design_done"] = design_done
            row["marketing_done"] = marketing_done
            row["design_percent"] = round(design_done * 100 / total_items) if total_items else 0
            row["marketing_percent"] = round(marketing_done * 100 / total_items) if total_items else 0
            row["overall_percent"] = round((design_done + marketing_done) * 50 / total_items) if total_items else 0
            totals["design_pending"] += max(total_items - design_done, 0)
            totals["marketing_pending"] += max(total_items - marketing_done, 0)

            if assignment.renewal_frequency in {RenewalFrequency.WEEKLY, RenewalFrequency.EVERY_MONDAY}:
                week_count = 1
            elif assignment.renewal_frequency == RenewalFrequency.BIWEEKLY:
                week_count = 2
            else:
                week_count = 4

            by_type = {}
            for item in items:
                by_type[item.content_type] = by_type.get(item.content_type, 0) + 1
            groups = OrderedDict((n, []) for n in range(1, week_count + 1))
            for item in items:
                total_of_type = max(by_type.get(item.content_type, 1), 1)
                week_number = min(week_count, ((item.sequence - 1) * week_count // total_of_type) + 1)
                groups[week_number].append(item)

            for number, week_items in groups.items():
                start = cycle.period_start + timedelta(days=(number - 1) * 7) if cycle else today
                end = start + timedelta(days=6)
                if cycle and cycle.due_date:
                    end = min(end, cycle.due_date - timedelta(days=1))
                total = len(week_items)
                week_design_done = sum(1 for item in week_items if item.ready)
                week_marketing_done = sum(1 for item in week_items if item.is_complete)
                design_complete = bool(total) and week_design_done >= total
                marketing_complete = bool(total) and week_marketing_done >= total
                complete = bool(total) and design_complete and marketing_complete

                if complete:
                    state, label = "green", "Semana completada"
                elif today > end:
                    state, label = "red", "Semana vencida con pendientes"
                elif start <= today <= end:
                    state, label = "yellow", "Semana actual · pendiente"
                    row["current_week"] = number
                else:
                    state, label = "neutral", "Próxima semana"

                if state == "red":
                    row["overdue_weeks"] += 1
                source_updated_at = max(
                    [item.updated_at for item in week_items]
                    or ([cycle.updated_at] if cycle else [assignment.updated_at])
                )
                check = None
                audit_decision = "pending"
                audit_label = "Por revisar"
                audit_state = "muted"
                audit_current = False
                audit_note = ""
                if project:
                    from .models import GeneralAuditCheck
                    check = _ensure_general_check(
                        project=project,
                        source_key=f"subscription:social:{assignment.pk}:cycle:{cycle.pk if cycle else 'none'}:week:{number}",
                        area="social_media",
                        category=f"{assignment.plan.name} · {_social_media_cycle_label(cycle)}",
                        label=f"Semana {number}",
                    )
                    audit_decision = getattr(
                        check,
                        "decision",
                        GeneralAuditCheck.Decision.APPROVED if check.is_ready else GeneralAuditCheck.Decision.PENDING,
                    )
                    was_reviewed = audit_decision != GeneralAuditCheck.Decision.PENDING
                    audit_current = bool(
                        was_reviewed
                        and check.reviewed_at
                        and (not source_updated_at or check.reviewed_at >= source_updated_at)
                    )
                    if was_reviewed and not audit_current:
                        audit_label, audit_state = "Cambios nuevos", "yellow"
                        totals["audit_changed"] += 1
                    elif audit_decision == GeneralAuditCheck.Decision.APPROVED:
                        audit_label, audit_state = "Aprobado", "green"
                        totals["audit_approved"] += 1
                    elif audit_decision == GeneralAuditCheck.Decision.REJECTED:
                        audit_label, audit_state = "Rechazado", "red"
                        totals["audit_rejected"] += 1
                    else:
                        totals["audit_pending"] += 1
                    audit_note = check.note or ""

                week = {
                    "number": number,
                    "label": f"Semana {number}",
                    "start": start,
                    "end": end,
                    "total": total,
                    "design_done": week_design_done,
                    "marketing_done": week_marketing_done,
                    "design_complete": design_complete,
                    "marketing_complete": marketing_complete,
                    "design_percent": round(week_design_done * 100 / total) if total else 0,
                    "marketing_percent": round(week_marketing_done * 100 / total) if total else 0,
                    "complete": complete,
                    "state": state,
                    "state_label": label,
                    "source_updated_at": source_updated_at,
                    "check": check,
                    "audit_decision": audit_decision,
                    "audit_label": audit_label,
                    "audit_state": audit_state,
                    "audit_current": audit_current,
                    "audit_note": audit_note,
                }
                row["weeks"].append(week)

            if row["overdue_weeks"]:
                row["state"], row["state_label"] = "red", f"{row['overdue_weeks']} semana(s) vencida(s)"
                totals["alerts"] += 1
            elif total_items and marketing_done >= total_items:
                row["state"], row["state_label"] = "green", "Ciclo completado"
                totals["complete"] += 1
            elif row["current_week"]:
                row["state"], row["state_label"] = "yellow", f"Semana {row['current_week']} en curso"
            else:
                row["state"], row["state_label"] = "neutral", "Ciclo programado"
        else:
            # Suscripciones recurrentes no Social Media: auditoría de renovación.
            if assignment.renewal_date and assignment.renewal_date < today:
                row["state"], row["state_label"] = "red", "Renovación vencida"
                totals["alerts"] += 1
            elif assignment.renewal_date and assignment.renewal_date <= today + timedelta(days=7):
                row["state"], row["state_label"] = "yellow", "Renovación próxima"
            else:
                row["state"], row["state_label"] = "neutral", "Suscripción activa"

        rows.append(row)

    return rows, totals
