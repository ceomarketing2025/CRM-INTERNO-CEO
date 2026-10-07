from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0011_rename_operations__sheet_i_6d58d9_idx_operations__sheet_i_85eb63_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WebProductionNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_type", models.CharField(max_length=32)),
                ("row_id", models.PositiveBigIntegerField()),
                ("row_label", models.CharField(blank=True, max_length=220)),
                ("event", models.CharField(max_length=40)),
                ("message", models.TextField(blank=True)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="web_production_notifications_sent", to=settings.AUTH_USER_MODEL)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="web_production_notifications", to=settings.AUTH_USER_MODEL)),
                ("sheet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="operations.webproductionsheet")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["recipient", "is_read", "created_at"], name="devnotif_recipient_read_idx"),
                    models.Index(fields=["sheet", "created_at"], name="devnotif_sheet_created_idx"),
                ],
            },
        ),
    ]
