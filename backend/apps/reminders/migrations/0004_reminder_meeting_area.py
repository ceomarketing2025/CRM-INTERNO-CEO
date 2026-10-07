from django.db import migrations, models


MARKETING_CATEGORIES = {
    "social_offer",
    "social_monthly",
    "social_daily",
    "campaign_manager_review",
    "campaign_weekly",
    "google_reviews",
}


def backfill_marketing_area(apps, schema_editor):
    Reminder = apps.get_model("reminders", "Reminder")

    Reminder.objects.filter(category__in=MARKETING_CATEGORIES).update(area="marketing")
    Reminder.objects.filter(source_key__startswith="marketing-").update(area="marketing")
    Reminder.objects.filter(source_key__startswith="campaign:").update(area="marketing")
    Reminder.objects.filter(source_key__startswith="social-plan:").update(area="marketing")


def reverse_backfill(apps, schema_editor):
    Reminder = apps.get_model("reminders", "Reminder")
    Reminder.objects.filter(area="marketing").update(area="general")


class Migration(migrations.Migration):

    dependencies = [
        ("reminders", "0003_alter_meeting_external_attendees"),
    ]

    operations = [
        migrations.AddField(
            model_name="reminder",
            name="area",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("marketing", "Marketing"),
                    ("design", "Diseño"),
                    ("development", "Desarrollo"),
                    ("administration", "Administración"),
                ],
                default="general",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="meeting",
            name="area",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("marketing", "Marketing"),
                    ("design", "Diseño"),
                    ("development", "Desarrollo"),
                    ("administration", "Administración"),
                ],
                default="general",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_marketing_area, reverse_backfill),
    ]
