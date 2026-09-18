from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_sales_follow_ups",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Creado por",
            ),
        ),
        migrations.AddField(
            model_name="salesmeeting",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_sales_meetings",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Agendado por",
            ),
        ),
    ]
