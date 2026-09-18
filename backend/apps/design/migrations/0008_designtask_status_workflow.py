from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("design", "0007_rename_design_desi_cycle_i_96ae28_idx_design_desi_cycle_i_55342d_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="designtask",
            name="status_note",
            field=models.TextField(blank=True, verbose_name="Motivo / novedad"),
        ),
        migrations.AlterField(
            model_name="designtask",
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
                max_length=20,
                verbose_name="Estado",
            ),
        ),
    ]
