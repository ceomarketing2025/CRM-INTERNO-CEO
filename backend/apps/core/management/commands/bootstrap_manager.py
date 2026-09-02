import os
from django.core.management.base import BaseCommand
from apps.accounts.models import UserAccount

class Command(BaseCommand):
    help = "Crea o actualiza el usuario gerente inicial usando variables de entorno."

    def handle(self, *args, **options):
        email = os.getenv("INITIAL_MANAGER_EMAIL", "").strip().lower()
        password = os.getenv("INITIAL_MANAGER_PASSWORD", "").strip()
        if not email or not password:
            self.stdout.write(self.style.WARNING("INITIAL_MANAGER_EMAIL/PASSWORD no configurados; se omite bootstrap."))
            return
        user, created = UserAccount.objects.get_or_create(email=email, defaults={
            "role": UserAccount.Role.MANAGER,
            "first_name": os.getenv("INITIAL_MANAGER_FIRST_NAME", "Gerencia"),
            "last_name": os.getenv("INITIAL_MANAGER_LAST_NAME", "Global"),
            "is_active": True,
        })
        user.role = UserAccount.Role.MANAGER
        user.is_active = True
        if created:
            user.set_password(password)
        user.save()
        if created:
            self.stdout.write(self.style.SUCCESS(f"Gerente inicial creado: {email}"))
        else:
            self.stdout.write(f"Gerente inicial existente: {email}")
