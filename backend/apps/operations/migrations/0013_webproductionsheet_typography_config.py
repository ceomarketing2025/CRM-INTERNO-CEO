from django.db import migrations, models
import apps.operations.models


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0012_webproductionnotification"),
    ]

    operations = [
        migrations.AddField(
            model_name="webproductionsheet",
            name="typography_config",
            field=models.JSONField(
                blank=True,
                default=apps.operations.models.default_typography_config,
                verbose_name="Configuración de tipografía",
            ),
        ),
    ]
