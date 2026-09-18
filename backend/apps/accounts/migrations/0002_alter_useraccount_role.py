from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="useraccount",
            name="role",
            field=models.CharField(
                choices=[
                    ("manager", "Global / Gerencia"),
                    ("administration", "Administración"),
                    ("marketing", "Marketing"),
                    ("design", "Diseño"),
                    ("developer", "Desarrollador"),
                    ("sales", "Vendedor"),
                ],
                default="developer",
                max_length=24,
            ),
        ),
    ]
