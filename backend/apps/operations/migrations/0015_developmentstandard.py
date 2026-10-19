from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.operations.models


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0014_developmenttasknotification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DevelopmentStandard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("singleton_key", models.CharField(default="global", editable=False, max_length=32, unique=True)),
                ("typography_config", models.JSONField(blank=True, default=apps.operations.models.default_typography_config, verbose_name="Tipografía global")),
                ("spacing_config", models.JSONField(blank=True, default=apps.operations.models.default_development_spacing_config, verbose_name="Espaciados globales")),
                ("prompt_rules", models.TextField(blank=True, verbose_name="Reglas para prompts")),
                ("general_rules", models.TextField(blank=True, verbose_name="Reglas generales")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_development_standards", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Estándar de Desarrollo",
                "verbose_name_plural": "Estándares de Desarrollo",
            },
        ),
    ]
