from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0005_rename_audit_manag_area_st_733fb5_idx_audit_manag_area_cdfc5f_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="managementtask",
            name="status_note",
            field=models.TextField(blank=True, verbose_name="Motivo / novedad"),
        ),
        migrations.AlterField(
            model_name="managementtask",
            name="status",
            field=models.CharField(
                choices=[
                    ("todo", "Pendiente"),
                    ("doing", "En proceso"),
                    ("paused", "Pausada"),
                    ("review", "Para revisión"),
                    ("changes", "Con novedad"),
                    ("done", "Cerrada"),
                ],
                default="todo",
                max_length=16,
                verbose_name="Estado",
            ),
        ),
    ]
