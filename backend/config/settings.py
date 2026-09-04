import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")

def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}

DEBUG = env_bool("DEBUG", True)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key")
ALLOWED_HOSTS = [x.strip() for x in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if x.strip()]
CSRF_TRUSTED_ORIGINS = [x.strip() for x in os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:8000").split(",") if x.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.administration.apps.AdministrationConfig",
    "apps.clients.apps.ClientsConfig",
    "apps.plans.apps.PlansConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.domains.apps.DomainsConfig",
    "apps.questionnaires.apps.QuestionnairesConfig",
    "apps.design.apps.DesignConfig",
    "apps.resources.apps.ResourcesConfig",
    "apps.handoff.apps.HandoffConfig",
    "apps.marketing.apps.MarketingConfig",
    "apps.operations.apps.OperationsConfig",
    "apps.reminders.apps.RemindersConfig",
    "apps.finance.apps.FinanceConfig",
    "apps.audit.apps.AuditConfig",
    "apps.dashboard.apps.DashboardConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "apps.core.context_processors.global_ui",
        ],
    },
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("USE_SQLITE", "false").lower() == "true":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "gestion360"),
            "USER": os.getenv("POSTGRES_USER", "gestion360"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "gestion360_dev"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.UserAccount"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "es"
TIME_ZONE = os.getenv("TIME_ZONE", "America/Guayaquil")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)

PROJECT_NAME = os.getenv("PROJECT_NAME", "CRM CEO Interno")

CELERY_BEAT_SCHEDULE = {
    "daily-social-followups": {
        "task": "apps.marketing.tasks.create_daily_social_followups",
        "schedule": 60 * 60 * 24,
    },
    "due-reminder-digest": {
        "task": "apps.reminders.tasks.due_reminder_digest",
        "schedule": 60 * 60,
    },
}
