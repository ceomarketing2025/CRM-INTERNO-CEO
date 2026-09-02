from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from apps.core.decorators import manager_required
from .forms import EmailAuthenticationForm, ManagerUserCreateForm, ManagerUserEditForm
from .models import UserAccount

class AppLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

class AppLogoutView(LogoutView):
    pass

@manager_required
def user_list(request):
    users = UserAccount.objects.order_by("role", "first_name", "email")
    return render(request, "accounts/user_list.html", {"users": users})

@manager_required
def user_create(request):
    form = ManagerUserCreateForm(request.POST or None, initial={"is_active": True})
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Usuario {user.email} creado correctamente.")
        return redirect("accounts:user_list")
    return render(request, "shared/form.html", {"form": form, "title": "Crear usuario", "subtitle": "Correo, contraseña y rol de acceso."})

@manager_required
def user_edit(request, pk):
    user = get_object_or_404(UserAccount, pk=pk)
    form = ManagerUserEditForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuario actualizado.")
        return redirect("accounts:user_list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar usuario", "subtitle": user.email})
