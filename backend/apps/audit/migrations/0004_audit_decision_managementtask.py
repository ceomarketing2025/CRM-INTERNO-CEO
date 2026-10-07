import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_audit_decision(apps, schema_editor):
    GeneralAuditCheck = apps.get_model("audit", "GeneralAuditCheck")
    GeneralAuditCheck.objects.filter(is_ready=True).update(decision="approved")
    GeneralAuditCheck.objects.filter(is_ready=False).update(decision="pending")


def reverse_seed(apps, schema_editor):
    GeneralAuditCheck = apps.get_model("audit", "GeneralAuditCheck")
    GeneralAuditCheck.objects.update(is_ready=False)
    GeneralAuditCheck.objects.filter(decision="approved").update(is_ready=True)


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0003_rename_audit_gener_area_50bc70_idx_audit_gener_area_80c755_idx_and_more"),
        ("clients", "0001_initial"),
        ("projects", "0003_alter_project_project_type_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="generalauditcheck",
            name="decision",
            field=models.CharField(
                choices=[("pending", "Por revisar"), ("approved", "Aprobado"), ("rejected", "Rechazado")],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.RunPython(seed_audit_decision, reverse_seed),
        migrations.CreateModel(
            name="ManagementTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("area", models.CharField(choices=[("design", "Diseño"), ("marketing", "Marketing"), ("development", "Desarrollo"), ("sales", "Vendedores"), ("administration", "Administración")], max_length=24)),
                ("title", models.CharField(max_length=180, verbose_name="Título")),
                ("description", models.TextField(blank=True, verbose_name="Descripción de la actividad")),
                ("priority", models.CharField(choices=[("low", "Baja"), ("medium", "Media"), ("high", "Alta"), ("urgent", "Urgente")], default="medium", max_length=16, verbose_name="Prioridad")),
                ("status", models.CharField(choices=[("todo", "Pendiente"), ("doing", "En proceso"), ("review", "Para revisión"), ("done", "Completada")], default="todo", max_length=16, verbose_name="Estado")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Fecha límite")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="management_tasks_assigned", to=settings.AUTH_USER_MODEL, verbose_name="Responsable")),
                ("client", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="management_tasks", to="clients.client", verbose_name="Cliente")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="management_tasks_created", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="management_tasks", to="projects.project", verbose_name="Proyecto")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="management_tasks_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["status", "due_date", "-created_at"]},
        ),
        migrations.AddIndex(model_name="managementtask", index=models.Index(fields=["area", "status"], name="audit_manag_area_st_733fb5_idx")),
        migrations.AddIndex(model_name="managementtask", index=models.Index(fields=["assigned_to", "status"], name="audit_manag_assigne_3b1952_idx")),
        migrations.AddIndex(model_name="managementtask", index=models.Index(fields=["project", "area"], name="audit_manag_project_8f4087_idx")),
    ]
