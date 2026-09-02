from django.conf import settings

def global_ui(request):
    user = getattr(request, "user", None)
    role = getattr(user, "role", "") if user and getattr(user, "is_authenticated", False) else ""
    return {
        "PROJECT_NAME": settings.PROJECT_NAME,
        "current_role": role,
    }
