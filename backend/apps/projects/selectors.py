from django.db.models import Q
from .models import Project


def visible_projects_for_user(user):
    qs = Project.objects.select_related("client", "purchased_plan__plan").prefetch_related("assignments__user")
    if user.is_manager or user.role == "administration":
        return qs
    area = {"design": "design", "developer": "development", "marketing": "marketing"}.get(user.role)
    if area:
        return qs.filter(assignments__user=user, assignments__area=area).distinct()
    return qs.none()


def can_access_project(user, project):
    if user.is_manager or user.role == "administration":
        return True
    area = {"design": "design", "developer": "development", "marketing": "marketing"}.get(user.role)
    return bool(area and project.assignments.filter(user=user, area=area).exists())
