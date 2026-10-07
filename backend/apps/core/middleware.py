from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class SalesPortalRestrictionMiddleware:
    """Limita el rol Vendedor a Dashboard, su panel y la agenda operativa.

    La restricción se aplica en backend para que no dependa únicamente de ocultar
    enlaces en el sidebar.
    """

    allowed_namespaces = {"dashboard", "sales", "reminders", "accounts"}
    allowed_view_names = {"health"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None
        if getattr(user, "is_superuser", False) or getattr(user, "role", "") != "sales":
            return None

        match = getattr(request, "resolver_match", None)
        namespace = getattr(match, "namespace", "") or ""
        view_name = getattr(match, "view_name", "") or ""

        if namespace in self.allowed_namespaces or view_name in self.allowed_view_names:
            return None
        if namespace == "audit" and getattr(match, "url_name", "") == "management_task_status":
            return None
        raise PermissionDenied("El rol Vendedor solo tiene acceso a Dashboard, Vendedores, Reuniones y Recordatorios.")
