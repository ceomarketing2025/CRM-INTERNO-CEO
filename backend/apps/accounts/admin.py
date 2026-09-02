from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserAccount

@admin.register(UserAccount)
class UserAccountAdmin(UserAdmin):
    model = UserAccount
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active")
    fieldsets = ((None, {"fields": ("email", "password")}), ("Perfil", {"fields": ("first_name", "last_name", "role", "job_title")}), ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}), ("Fechas", {"fields": ("last_login", "date_joined")}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "role", "is_active")}),)
    search_fields = ("email", "first_name", "last_name")
