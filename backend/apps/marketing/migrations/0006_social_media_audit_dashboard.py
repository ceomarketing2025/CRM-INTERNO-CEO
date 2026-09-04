import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_legacy_tracking_to_google_business(apps, schema_editor):
    """Conserva los checks útiles del seguimiento viejo en su nueva fuente."""
    Tracking = apps.get_model("marketing", "SocialMediaTracking")
    Workspace = apps.get_model("marketing", "MarketingWorkspace")

    for row in Tracking.objects.all().iterator():
        workspace = None
        if row.project_id:
            workspace = Workspace.objects.filter(project_id=row.project_id).first()
        if workspace is None:
            workspace = Workspace.objects.filter(project__client_id=row.client_id).order_by("id").first()
        if workspace is None:
            continue

        changed = []
        mappings = [
            ("business_profile_reviews_status", row.reviews),
            ("business_profile_products_status", row.products),
            ("business_profile_completion_status", row.profile_percentage),
            ("business_profile_website_status", row.website_in_gb),
            ("business_profile_photos_status", row.photos),
        ]
        for field_name, legacy_value in mappings:
            if legacy_value == "complete" and getattr(workspace, field_name) != "complete":
                setattr(workspace, field_name, "complete")
                changed.append(field_name)

        if row.last_post_gb and not workspace.business_profile_last_post:
            workspace.business_profile_last_post = row.last_post_gb
            changed.append("business_profile_last_post")
        if row.gb_notes and not workspace.business_profile_notes:
            workspace.business_profile_notes = row.gb_notes
            changed.append("business_profile_notes")

        if changed:
            workspace.save(update_fields=changed)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("marketing", "0005_marketing_validation_and_lsa_photos"),
        ("projects", "0003_alter_project_project_type_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_reviews_status",
            field=models.CharField(
                choices=[("incomplete", "Incompleto"), ("complete", "Completo")],
                default="incomplete",
                max_length=20,
                verbose_name="Reseñas",
            ),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_products_status",
            field=models.CharField(
                choices=[("incomplete", "Incompleto"), ("complete", "Completo")],
                default="incomplete",
                max_length=20,
                verbose_name="Productos",
            ),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_completion_status",
            field=models.CharField(
                choices=[("incomplete", "Incompleto"), ("complete", "Completo")],
                default="incomplete",
                max_length=20,
                verbose_name="Porcentaje del perfil",
            ),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_website_status",
            field=models.CharField(
                choices=[("incomplete", "Incompleto"), ("complete", "Completo")],
                default="incomplete",
                max_length=20,
                verbose_name="Website en Google Business",
            ),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_last_post",
            field=models.DateField(blank=True, null=True, verbose_name="Último post en Google Business"),
        ),
        migrations.AddField(
            model_name="marketingworkspace",
            name="business_profile_photos_status",
            field=models.CharField(
                choices=[("incomplete", "Incompleto"), ("complete", "Completo")],
                default="incomplete",
                max_length=20,
                verbose_name="Fotos",
            ),
        ),
        migrations.AddField(
            model_name="googlelsaworkspace",
            name="last_lead_date",
            field=models.DateField(blank=True, null=True, verbose_name="Fecha del último lead"),
        ),
        migrations.CreateModel(
            name="SocialMediaAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_ready", models.BooleanField(default=False, verbose_name="Auditoría lista")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True, verbose_name="Última revisión")),
                ("note", models.TextField(blank=True, verbose_name="Nota de auditoría")),
                (
                    "project_plan",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="social_media_audit",
                        to="projects.projectplanassignment",
                        verbose_name="Plan Social Media del proyecto",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_social_media_audits",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Revisado por",
                    ),
                ),
            ],
            options={
                "ordering": ["project_plan__project__client__business_name", "project_plan__plan__name"],
            },
        ),
        migrations.RunPython(copy_legacy_tracking_to_google_business, noop_reverse),
    ]
