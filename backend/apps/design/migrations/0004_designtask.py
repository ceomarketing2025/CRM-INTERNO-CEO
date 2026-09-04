import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("design", "0003_remove_socialmediaweek_month_control_and_more"),
        ("projects", "0003_alter_project_project_type_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DesignTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=180, verbose_name="Actividad")),
                ("description", models.TextField(blank=True, verbose_name="Detalle")),
                ("status", models.CharField(choices=[("todo", "Pendiente"), ("doing", "En proceso"), ("review", "En revisión"), ("done", "Lista")], default="todo", max_length=20, verbose_name="Estado")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Fecha límite")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Orden")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="design_operational_tasks", to=settings.AUTH_USER_MODEL, verbose_name="Responsable")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_design_operational_tasks", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_design_operational_tasks", to=settings.AUTH_USER_MODEL)),
                ("project_plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="design_tasks", to="projects.projectplanassignment", verbose_name="Proyecto / producto de Diseño")),
            ],
            options={"ordering": ["project_plan__project__client__business_name", "project_plan__plan__name", "order", "id"]},
        ),
    ]
