from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("design", "0005_designtask_cycles_and_recurrence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DesignTaskCycleItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("content_type", models.CharField(choices=[("post", "Post"), ("video", "Video")], default="post", max_length=12)),
                ("sequence", models.PositiveSmallIntegerField(default=1)),
                ("week_number", models.PositiveSmallIntegerField(default=1, verbose_name="Semana")),
                ("content_created", models.BooleanField(default=False, verbose_name="Creado")),
                ("content_published", models.BooleanField(default=False, verbose_name="Publicado")),
                ("notes", models.CharField(blank=True, max_length=300, verbose_name="Notas")),
                ("cycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_items", to="design.designtaskcycle")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_design_delivery_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["week_number", "content_type", "sequence", "id"]},
        ),
        migrations.AddConstraint(
            model_name="designtaskcycleitem",
            constraint=models.UniqueConstraint(fields=("cycle", "content_type", "sequence"), name="unique_design_cycle_delivery_item"),
        ),
        migrations.AddIndex(
            model_name="designtaskcycleitem",
            index=models.Index(fields=["cycle", "week_number"], name="design_desi_cycle_i_96ae28_idx"),
        ),
    ]
