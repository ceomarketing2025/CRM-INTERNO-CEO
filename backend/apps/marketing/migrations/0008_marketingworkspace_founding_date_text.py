from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marketing", "0007_marketingtask_area"),
    ]

    operations = [
        migrations.AlterField(
            model_name="marketingworkspace",
            name="founding_date",
            field=models.CharField(
                blank=True,
                max_length=120,
                null=True,
                verbose_name="Fecha de fundación",
            ),
        ),
    ]
