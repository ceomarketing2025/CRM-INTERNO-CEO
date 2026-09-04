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
                       detail="", counts_for_progress=True, historical=False):
    progress = max(0, min(100, int(source_progress or 0)))
    check = _ensure_general_check(
        project=project,
        source_key=source_key,
        area=area,
        category=category,
        label=label,
    )
    audit_current = bool(
        check.is_ready
        and check.reviewed_at
        and (not source_updated_at or check.reviewed_at >= source_updated_at)
    )
    if audit_current:
        audit_label, audit_state = "Revisado", "green"
    elif check.is_ready:
        audit_label, audit_state = "Cambios nuevos", "yellow"
    else:
        audit_label, audit_state = "Por revisar", "muted"
    return {
        "check": check,
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
        "counts_for_progress": bool(counts_for_progress),
        "historical": bool(historical),
    }


def build_general_audit_rows():
    """Construye la auditoría desde las fuentes reales de las tres áreas.

    Las tareas recurrentes de Diseño conservan periodos históricos, pero solo el
    periodo vigente entra al porcentaje actual. Así un nuevo ciclo vuelve a rojo/
    amarillo aunque los meses anteriores estén publicados.
    """
    from django.urls import reverse
    from apps.design.models import DesignTask
    from apps.design.services import design_task_progress, ensure_current_design_task_cycle
    from apps.marketing.models import MarketingChecklistItem, MarketingTask
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
    ).prefetch_related("cycles").filter(project_plan__is_active=True)
    for task in design_tasks:
        project = task.project_plan.project
        category = task.project_plan.plan.name
        if task.task_type == DesignTask.TaskType.CONTENT:
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
                    source_url=reverse("design:tasks"),
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
                source_url=reverse("design:task_edit", args=[task.pk]),
                detail=task.description,
            ))

    # MARKETING: checklist operativo de cada ficha.
    marketing_checks = MarketingChecklistItem.objects.select_related(
        "workspace__project__client"
    ).filter(active=True)
    for item in marketing_checks:
        project = item.workspace.project
        progress = 100 if item.status == "complete" else 0
        rows.append(_general_audit_row(
            project=project,
            source_key=f"marketing:check:{item.pk}",
            area="marketing",
            area_label="Marketing",
            category=item.get_area_display(),
            label=item.label,
            source_progress=progress,
            source_status=item.get_status_display(),
            source_updated_at=item.updated_at,
            source_url=reverse("marketing:workspace", args=[project.pk]),
            detail=item.detail,
        ))

    # MARKETING: tareas manuales ya existentes en el módulo.
    marketing_tasks = MarketingTask.objects.select_related("project__client", "assigned_to").all()
    marketing_progress = {"todo": 0, "doing": 60, "review": 80, "done": 100}
    for task in marketing_tasks:
        rows.append(_general_audit_row(
            project=task.project,
            source_key=f"marketing:task:{task.pk}",
            area="marketing",
            area_label="Marketing",
            category="Tareas de Marketing",
            label=task.title,
            source_progress=marketing_progress.get(task.status, 0),
            source_status=task.get_status_display(),
            source_updated_at=task.updated_at,
            source_url=reverse("marketing:workspace", args=[task.project_id]),
            detail=task.description,
        ))

    # DESARROLLO: cada pregunta de la ficha técnica es auditable.
    questionnaires = ProjectQuestionnaire.objects.select_related(
        "project__client", "template"
    ).prefetch_related("template__sections__questions", "answers__question")
    completed_states = {AnswerState.CONFIRMED, AnswerState.NO, AnswerState.NOT_APPLICABLE}
    for questionnaire in questionnaires:
        answer_map = {answer.question_id: answer for answer in questionnaire.answers.all()}
        for section in questionnaire.template.sections.all():
            for question in section.questions.all():
                answer = answer_map.get(question.pk)
                done = bool(answer and answer.state in completed_states)
                source_updated_at = answer.updated_at if answer else questionnaire.updated_at
                detail = answer.value_text if answer and answer.value_text else ""
                rows.append(_general_audit_row(
                    project=questionnaire.project,
                    source_key=f"development:question:{questionnaire.pk}:{question.pk}",
                    area="development",
                    area_label="Desarrollo",
                    category=f"Ficha técnica · {section.title}",
                    label=question.text,
                    source_progress=100 if done else 0,
                    source_status="Completo" if done else "Pendiente",
                    source_updated_at=source_updated_at,
                    source_url=reverse("questionnaires:fill", args=[questionnaire.pk]),
                    detail=detail,
                ))

    # DESARROLLO: producción web, indexación/SEO y estructura territorial existente.
    production_sources = [
        (WebProductionPage, "Producción · Páginas"),
        (WebProductionCounty, "Producción · Condados"),
        (WebProductionCountyService, "Producción · Servicios por condado"),
        (WebProductionCity, "Producción · Ciudades / indexación"),
    ]
    for model, category in production_sources:
        qs = model.objects.all()
        if model is WebProductionCountyService:
            qs = qs.select_related("county__sheet__project__client")
        else:
            qs = qs.select_related("sheet__project__client")
        for item in qs:
            sheet = item.county.sheet if model is WebProductionCountyService else item.sheet
            project = sheet.project
            label = item.name or getattr(item, "service_name", "") or str(item)
            done = item.state == CompleteStatus.COMPLETE
            rows.append(_general_audit_row(
                project=project,
                source_key=f"development:{model.__name__.lower()}:{item.pk}",
                area="development",
                area_label="Desarrollo",
                category=category,
                label=label,
                source_progress=100 if done else 0,
                source_status="Lista" if done else "Pendiente",
                source_updated_at=item.updated_at,
                source_url=reverse("operations:web_production_sheet", args=[project.pk]),
                detail=item.notes,
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


def review_general_audit_check(*, check, user, ready=True, note=None):
    from django.utils import timezone
    check.is_ready = bool(ready)
    if note is not None:
        check.note = (note or "").strip()
    if check.is_ready:
        check.reviewed_at = timezone.now()
        check.reviewed_by = user
    else:
        check.reviewed_at = None
        check.reviewed_by = None
    check.save(update_fields=["is_ready", "reviewed_at", "reviewed_by", "note", "updated_at"])
    return check
