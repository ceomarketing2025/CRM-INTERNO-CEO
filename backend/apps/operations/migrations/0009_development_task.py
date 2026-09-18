from django.conf import settings
from django.db import migrations, models

import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        (
            "operations",
            "0008_production_sheet_button_style_and_internal_smtp",
        ),
        migrations.swappable_dependency(
            settings.AUTH_USER_MODEL
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="DevelopmentTask",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        max_length=180,
                        verbose_name="Tarea",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        verbose_name="Descripción",
                    ),
                ),
                (
                    "assigned_date",
                    models.DateField(
                        verbose_name="Fecha de asignación",
                    ),
                ),
                (
                    "due_date",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Fecha objetivo",
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("low", "Baja"),
                            ("medium", "Media"),
                            ("high", "Alta"),
                        ],
                        default="medium",
                        max_length=16,
                        verbose_name="Prioridad",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente"),
                            (
                                "in_progress",
                                "En proceso",
                            ),
                            (
                                "issue",
                                "Con inconveniente",
                            ),
                            (
                                "completed",
                                "Completada",
                            ),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="Estado",
                    ),
                ),
                (
                    "assignment_note",
                    models.TextField(
                        blank=True,
                        verbose_name="Nota de asignación",
                    ),
                ),
                (
                    "developer_note",
                    models.TextField(
                        blank=True,
                        verbose_name="Nota del desarrollador",
                    ),
                ),
                (
                    "issue_reason",
                    models.TextField(
                        blank=True,
                        verbose_name="Motivo del inconveniente",
                    ),
                ),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Fecha de finalización",
                    ),
                ),
                (
                    "assigned_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="development_tasks_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Asignado por",
                    ),
                ),
                (
                    "assigned_to",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="development_tasks_assigned",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Asignado a",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="development_tasks",
                        to="projects.project",
                        verbose_name="Proyecto",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_development_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": [
                    "-assigned_date",
                    "-created_at",
                ],
            },
        ),
        migrations.AddIndex(
            model_name="developmenttask",
            index=models.Index(
                fields=[
                    "assigned_to",
                    "status",
                ],
                name="devtask_user_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="developmenttask",
            index=models.Index(
                fields=[
                    "assigned_date",
                ],
                name="devtask_date_idx",
            ),
        ),
    ]