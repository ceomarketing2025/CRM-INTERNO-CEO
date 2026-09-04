# Generated for CRM CEO Interno - recurring design task cycles.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("design", "0004_designtask"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="designtask",
            name="task_type",
            field=models.CharField(
                choices=[("standard", "Tarea única"), ("content", "Contenido / publicación")],
                default="standard",
                max_length=20,
                verbose_name="Tipo de actividad",
            ),
        ),
        migrations.AddField(
            model_name="designtask",
            name="recurrence_frequency",
            field=models.CharField(
                choices=[
                    ("none", "Sin renovación"),
                    ("weekly", "Semanal"),
                    ("biweekly", "Quincenal"),
                    ("monthly", "Mensual"),
                ],
                default="none",
                help_text="Para publicaciones: semanal, quincenal o mensual. Cada periodo crea un control nuevo.",
                max_length=20,
                verbose_name="Frecuencia de control",
            ),
        ),
        migrations.AddField(
            model_name="designtask",
            name="recurrence_start_date",
            field=models.DateField(blank=True, null=True, verbose_name="Inicio de la renovación"),
        ),
        migrations.AddField(
            model_name="designtask",
            name="auto_generated",
            field=models.BooleanField(default=False, verbose_name="Creada automáticamente"),
        ),
        migrations.AddField(
            model_name="designtask",
            name="configuration_required",
            field=models.BooleanField(
                default=False,
                help_text="Se usa para tareas Social Media creadas automáticamente al contratar el servicio.",
                verbose_name="Requiere configurar renovación",
            ),
        ),
        migrations.CreateModel(
            name="DesignTaskCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period_start", models.DateField(verbose_name="Inicio del periodo")),
                ("period_end", models.DateField(verbose_name="Fin del periodo")),
                ("label", models.CharField(max_length=120, verbose_name="Periodo")),
                ("content_created", models.BooleanField(default=False, verbose_name="Creado")),
                ("content_published", models.BooleanField(default=False, verbose_name="Publicado")),
                ("notes", models.CharField(blank=True, max_length=300, verbose_name="Notas")),
                (
                    "task",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cycles", to="design.designtask"),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_design_task_cycles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-period_start", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="designtaskcycle",
            constraint=models.UniqueConstraint(fields=("task", "period_start"), name="unique_design_task_cycle_start"),
        ),
        migrations.AddIndex(
            model_name="designtaskcycle",
            index=models.Index(fields=["task", "period_start"], name="design_desi_task_id_0b1698_idx"),
        ),
    ]
