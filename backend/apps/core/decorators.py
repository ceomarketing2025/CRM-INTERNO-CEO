from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ROLE_MANAGER = "manager"
ROLE_ADMINISTRATION = "administration"
ROLE_MARKETING = "marketing"
ROLE_DESIGN = "design"
ROLE_DEVELOPER = "developer"


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if getattr(user, "role", None) == ROLE_MANAGER or getattr(user, "is_superuser", False):
                return view_func(request, *args, **kwargs)
            if getattr(user, "role", None) not in roles:
                raise PermissionDenied("No tienes acceso a este módulo.")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def manager_required(view_func):
    return role_required(ROLE_MANAGER)(view_func)
