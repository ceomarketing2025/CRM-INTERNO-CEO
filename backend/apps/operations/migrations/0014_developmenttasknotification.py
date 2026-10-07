from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("operations", "0013_webproductionsheet_typography_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="DevelopmentTaskNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("task_assigned", "Nueva tarea asignada"), ("task_reassigned", "Tarea reasignada")], default="task_assigned", max_length=32)),
                ("message", models.TextField(blank=True)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="development_task_notifications_sent", to=settings.AUTH_USER_MODEL)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="development_task_notifications", to=settings.AUTH_USER_MODEL)),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="operations.developmenttask")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="developmenttasknotification",
            index=models.Index(fields=["recipient", "is_read", "created_at"], name="devtasknotif_rec_read_idx"),
        ),
        migrations.AddIndex(
            model_name="developmenttasknotification",
            index=models.Index(fields=["task", "created_at"], name="devtasknotif_task_created_idx"),
        ),
    ]
