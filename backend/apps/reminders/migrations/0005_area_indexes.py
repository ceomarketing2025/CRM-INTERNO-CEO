from django.db import migrations, models


AREA_CHOICES = [
    ("general", "General"),
    ("marketing", "Marketing"),
    ("design", "Diseño"),
    ("development", "Desarrollo"),
    ("administration", "Administración"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("reminders", "0004_reminder_meeting_area"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reminder",
            name="area",
            field=models.CharField(
                choices=AREA_CHOICES,
                db_index=True,
                default="general",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="meeting",
            name="area",
            field=models.CharField(
                choices=AREA_CHOICES,
                db_index=True,
                default="general",
                max_length=20,
            ),
        ),
    ]
