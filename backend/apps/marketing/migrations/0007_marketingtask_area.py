from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("marketing", "0006_social_media_audit_dashboard"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketingtask",
            name="area",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("google_business", "Google Business"),
                    ("google_lsa", "Google LSA"),
                    ("digital_ads", "Publicidad Digital"),
                    ("social_media", "Social Media"),
                ],
                default="general",
                max_length=30,
                verbose_name="Área de trabajo",
            ),
        ),
    ]
