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
