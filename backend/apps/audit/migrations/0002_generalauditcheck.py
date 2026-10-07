import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("projects", "0003_alter_project_project_type_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneralAuditCheck",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(max_length=190, unique=True)),
                ("area", models.CharField(max_length=24)),
                ("category", models.CharField(blank=True, max_length=180)),
                ("label", models.CharField(blank=True, max_length=240)),
                ("is_ready", models.BooleanField(default=False, verbose_name="Revisado")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="general_audit_checks", to="projects.project")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="general_audit_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["project__client__business_name", "area", "category", "label"]},
        ),
        migrations.AddIndex(model_name="generalauditcheck", index=models.Index(fields=["area", "is_ready"], name="audit_gener_area_50bc70_idx")),
        migrations.AddIndex(model_name="generalauditcheck", index=models.Index(fields=["project", "area"], name="audit_gener_project_d48d02_idx")),
    ]
