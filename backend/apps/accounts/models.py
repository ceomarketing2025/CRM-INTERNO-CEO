from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserAccountManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El correo es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserAccount.Role.MANAGER)
        return self._create_user(email, password, **extra_fields)


class UserAccount(AbstractUser):
    class Role(models.TextChoices):
        MANAGER = "manager", "Global / Gerencia"
        ADMINISTRATION = "administration", "Administración"
        MARKETING = "marketing", "Marketing"
        DESIGN = "design", "Diseño"
        DEVELOPER = "developer", "Desarrollador"

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.DEVELOPER)
    job_title = models.CharField(max_length=120, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserAccountManager()

    @property
    def display_name(self):
        name = self.get_full_name().strip()
        return name or self.email

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER or self.is_superuser

    def __str__(self):
        return self.email
