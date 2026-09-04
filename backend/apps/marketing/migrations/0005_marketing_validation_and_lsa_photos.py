# Marketing workflow V5 - dependent validation + LSA photo reminders.
# Additive migration; previous migrations remain untouched.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marketing", "0004_marketing_workflow_v4"),
    ]

    operations = [
        migrations.AddField(
            model_name="googlelsaworkspace",
            name="photo_reminder_enabled",
            field=models.CharField(
                choices=[("yes", "Sí"), ("no", "No")],
                default="yes",
                max_length=10,
                verbose_name="¿Activar recordatorio para subir fotos cada 15 días?",
            ),
        ),
        migrations.AddField(
            model_name="googlelsaworkspace",
            name="photo_reminder_start_date",
            field=models.DateField(blank=True, null=True, verbose_name="Primera fecha para subir fotos"),
        ),
        migrations.AlterField(
            model_name="googlelsaworkspace",
            name="driver_license_ready",
            field=models.CharField(
                blank=True,
                choices=[("yes", "Sí"), ("no", "No")],
                default="",
                max_length=10,
                verbose_name="Licencia de conducir",
            ),
        ),
        migrations.AlterField(
            model_name="marketingchecklistitem",
            name="area",
            field=models.CharField(
                choices=[
                    ("intake", "Información inicial / reunión"),
                    ("google_profile", "Google Business Profile"),
                    ("google_lsa", "Google LSA"),
                    ("digital_ads", "Publicidad digital"),
                    ("meta_ads", "Meta Ads"),
                    ("google_ads", "Google Ads"),
                    ("tiktok_ads", "TikTok Ads"),
                    ("traditional", "Publicidad tradicional"),
                    ("social_media", "Social Media"),
                ],
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="advertisingaccount",
            name="platform",
            field=models.CharField(
                choices=[
                    ("meta", "Meta Ads"),
                    ("google", "Google Ads"),
                    ("tiktok", "TikTok Ads"),
                    ("traditional", "Publicidad tradicional"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="adcampaign",
            name="platform",
            field=models.CharField(
                choices=[
                    ("meta", "Meta Ads"),
                    ("google", "Google Ads"),
                    ("tiktok", "TikTok Ads"),
                    ("traditional", "Publicidad tradicional"),
                ],
                max_length=20,
            ),
        ),
    ]
