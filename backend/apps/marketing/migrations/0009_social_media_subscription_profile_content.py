from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("marketing", "0008_marketingworkspace_founding_date_text"),
        ("plans", "0001_initial"),
        ("projects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialMediaSubscriptionProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("needs_photos", models.CharField(choices=[("yes", "Sí"), ("no", "No")], default="no", max_length=10, verbose_name="¿Hace falta pedir fotos al cliente?")),
                ("photo_request_status", models.CharField(choices=[("incomplete", "Incompleto"), ("complete", "Completo")], default="incomplete", max_length=20, verbose_name="Estado de solicitud de fotos")),
                ("photo_request_notes", models.TextField(blank=True, verbose_name="Detalle de fotos solicitadas")),
                ("extra_platforms", models.CharField(blank=True, max_length=255, verbose_name="Plataformas extras")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketing_social_subscriptions", to=settings.AUTH_USER_MODEL, verbose_name="Responsable de Marketing")),
                ("client_plan", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="marketing_social_profile", to="plans.clientplan", verbose_name="Suscripción Social Media")),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketing_social_subscriptions", to="projects.project", verbose_name="Proyecto")),
            ],
            options={"ordering": ["client_plan__client__business_name", "-updated_at"]},
        ),
        migrations.CreateModel(
            name="SocialMediaContentRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("planning_month", models.DateField(verbose_name="Mes de planificación")),
                ("service_used", models.CharField(max_length=180, verbose_name="Servicio utilizado")),
                ("topic", models.CharField(max_length=220, verbose_name="Tema")),
                ("objective", models.TextField(blank=True, verbose_name="Objetivo")),
                ("summary", models.TextField(verbose_name="Resumen del contenido")),
                ("adjustment_notes", models.TextField(blank=True, verbose_name="Cambios respecto a la planificación")),
                ("published_on", models.DateField(blank=True, null=True, verbose_name="Fecha de publicación")),
                ("post_url", models.URLField(blank=True, verbose_name="Link de publicación")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketing_social_content_records", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="content_records", to="marketing.socialmediasubscriptionprofile", verbose_name="Suscripción")),
            ],
            options={"ordering": ["-planning_month", "-published_on", "-id"]},
        ),
    ]
