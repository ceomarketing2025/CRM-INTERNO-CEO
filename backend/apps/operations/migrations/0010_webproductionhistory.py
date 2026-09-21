from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0009_development_task"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WebProductionHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_type", models.CharField(max_length=32)),
                ("row_id", models.PositiveBigIntegerField()),
                ("row_label", models.CharField(blank=True, max_length=220)),
                ("event", models.CharField(max_length=40)),
                ("from_status", models.CharField(blank=True, max_length=32)),
                ("to_status", models.CharField(blank=True, max_length=32)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="web_production_history_entries", to=settings.AUTH_USER_MODEL)),
                ("sheet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history_entries", to="operations.webproductionsheet")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="webproductionhistory",
            index=models.Index(fields=["sheet", "row_type", "row_id", "created_at"], name="operations__sheet_i_6d58d9_idx"),
        ),
    ]
