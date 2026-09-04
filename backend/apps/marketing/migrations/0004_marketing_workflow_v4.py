# Marketing workflow V4 - additive migration.
# Keeps 0001-0003 untouched so existing installations can upgrade safely.

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def preserve_previous_workspace_data(apps, schema_editor):
    MarketingWorkspace = apps.get_model("marketing", "MarketingWorkspace")
    AdCampaign = apps.get_model("marketing", "AdCampaign")
    AdCampaign.objects.filter(status="ready").update(status="manager_review")
    for workspace in MarketingWorkspace.objects.all().iterator():
        updates = []
        if workspace.gmail_email and workspace.email_account_mode == "pending":
            workspace.email_account_mode = "existing"
            updates.append("email_account_mode")
        if workspace.documents_available in {"yes", "no"} and not workspace.lsa_documents_available:
            workspace.lsa_documents_available = workspace.documents_available
            updates.append("lsa_documents_available")
        if updates:
            workspace.save(update_fields=updates)


def noop_reverse(apps, schema_editor):
    # New fields/models are removed by the schema reverse; historical values are left untouched.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("marketing", "0003_marketingworkspace_business_profile_mode_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="marketingworkspace",
            name="intake_status",
            field=models.CharField(choices=[("incomplete", "Incompleto"), ("complete", "Completo")], default="incomplete", max_length=20, verbose_name="Información inicial"),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="contact_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="Correo electrónico"),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="email_account_mode",
            field=models.CharField(choices=[("existing", "Ya existe"), ("create", "Lo crea Marketing"), ("pending", "Pendiente de definir")], default="pending", max_length=20, verbose_name="Estado del correo"),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="lsa_documents_available",
            field=models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="¿Tiene documentos para LSA?"),
        ),
        migrations.AlterField(
            model_name="marketingworkspace",
            name="business_profile_mode",
            field=models.CharField(blank=True, choices=[("existing", "Ya tiene perfil"), ("create", "Crear perfil"), ("no", "No tiene perfil")], default="", max_length=20, verbose_name="Google Business: situación"),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_id",
            field=models.CharField(blank=True, max_length=180, verbose_name="ID Google Business"),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_social_links",
            field=models.TextField(blank=True, verbose_name="Links de redes sociales del perfil"),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_notes",
            field=models.TextField(blank=True, verbose_name="Notas Google Business"),
        ),
        migrations.AddField(
            model_name="marketingchecklistitem",
            name="active",
            field=models.BooleanField(default=True, help_text="Permite ocultar checks de versiones anteriores sin borrar historial."),
        ),
        migrations.AlterField(
            model_name="marketingchecklistitem",
            name="area",
            field=models.CharField(choices=[("intake", "Información inicial / reunión"), ("google_profile", "Google Business Profile"), ("google_lsa", "Google LSA"), ("digital_ads", "Publicidad digital"), ("meta_ads", "Meta Ads"), ("google_ads", "Google Ads"), ("tiktok_ads", "TikTok Ads"), ("traditional", "Pauta tradicional"), ("social_media", "Social Media")], max_length=30),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="primary_keyword",
            field=models.CharField(blank=True, max_length=240, verbose_name="Keyword principal"),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="weekly_followup_enabled",
            field=models.BooleanField(default=True, verbose_name="Seguimiento semanal"),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="monthly_cost",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Costo de campaña por mes"),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="conversion_cost",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Costo por conversión"),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="conversions",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Conversiones"),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="manager_approved",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="manager_approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="adcampaign",
            name="manager_approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_ad_campaigns", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="adcampaign",
            name="platform",
            field=models.CharField(choices=[("meta", "Meta Ads"), ("google", "Google Ads"), ("tiktok", "TikTok Ads"), ("traditional", "Pauta tradicional")], max_length=20),
        ),
        migrations.AlterField(
            model_name="adcampaign",
            name="status",
            field=models.CharField(choices=[("draft", "Borrador"), ("manager_review", "Esperando validación"), ("changes_requested", "Correcciones requeridas"), ("approved", "Aprobada"), ("scheduled", "Programada"), ("launched", "Lanzada"), ("paused", "Pausada"), ("completed", "Finalizada")], default="draft", max_length=30),
        ),
        migrations.AlterField(
            model_name="adcampaign",
            name="keyword_research",
            field=models.TextField(blank=True, help_text="Keywords a usar o link al estudio."),
        ),
        migrations.CreateModel(
            name="GoogleLSAWorkspace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("documents_drive_url", models.URLField(blank=True, verbose_name="Drive de documentos")),
                ("driver_license_ready", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="Licencia de conducir disponible")),
                ("founding_year", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Año de fundación")),
                ("verification_status", models.CharField(choices=[("incomplete", "Incompleto"), ("complete", "Completo")], default="incomplete", max_length=20, verbose_name="Verificación LSA")),
                ("weekly_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Costo por semana")),
                ("leads_last_7_days", models.PositiveIntegerField(blank=True, null=True, verbose_name="Leads últimos 7 días")),
                ("has_social_media", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="¿Tiene Social Media?")),
                ("followup_mode", models.CharField(choices=[("none", "Sin recordatorio"), ("weekly", "Semanal"), ("custom", "Personalizado")], default="weekly", max_length=20, verbose_name="Recordatorio de revisión")),
                ("followup_start_date", models.DateField(blank=True, null=True, verbose_name="Primera revisión")),
                ("custom_followup_date", models.DateField(blank=True, null=True, verbose_name="Fecha personalizada")),
                ("notes", models.TextField(blank=True)),
                ("workspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="lsa_workspace", to="marketing.marketingworkspace")),
            ],
        ),
        migrations.CreateModel(
            name="AdvertisingAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("platform", models.CharField(choices=[("meta", "Meta Ads"), ("google", "Google Ads"), ("tiktok", "TikTok Ads"), ("traditional", "Pauta tradicional")], max_length=20)),
                ("enabled", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="¿Se trabajará esta plataforma?")),
                ("profile_url", models.URLField(blank=True, verbose_name="Link de la plataforma")),
                ("account_verified", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="Cuenta verificada")),
                ("account_id", models.CharField(blank=True, max_length=180, verbose_name="ID de cuenta")),
                ("payment_method_ready", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="Método de pago configurado")),
                ("terms_accepted", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="Términos y condiciones aceptados")),
                ("campaigns_enabled", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="¿Tiene / realizará campañas publicitarias?")),
                ("portfolio_created", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="Portafolio comercial creado")),
                ("portfolio_id", models.CharField(blank=True, max_length=180, verbose_name="ID de portafolio")),
                ("ad_account_created", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="Cuenta publicitaria creada")),
                ("fanpage_connected", models.CharField(blank=True, choices=[("yes", "Sí"), ("no", "No")], default="", max_length=10, verbose_name="Fanpage vinculada / acceso")),
                ("notes", models.TextField(blank=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="advertising_accounts", to="marketing.marketingworkspace")),
            ],
            options={"ordering": ["platform"]},
        ),
        migrations.AddConstraint(
            model_name="advertisingaccount",
            constraint=models.UniqueConstraint(fields=("workspace", "platform"), name="unique_marketing_ad_account_platform"),
        ),
        migrations.CreateModel(
            name="CampaignWeeklyReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("review_date", models.DateField(default=django.utils.timezone.localdate)),
                ("spend", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("leads", models.PositiveIntegerField(blank=True, null=True)),
                ("conversions", models.PositiveIntegerField(blank=True, null=True)),
                ("conversion_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("notes", models.TextField(blank=True)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="weekly_reports", to="marketing.adcampaign")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marketing_weekly_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-review_date", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="campaignweeklyreport",
            constraint=models.UniqueConstraint(fields=("campaign", "review_date"), name="unique_campaign_weekly_report_date"),
        ),
        migrations.RunPython(preserve_previous_workspace_data, noop_reverse),
    ]
