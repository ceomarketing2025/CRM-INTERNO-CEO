from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0001_initial"),
        ("projects", "0003_alter_project_project_type_and_more"),
        ("sales", "0002_followup_created_by_salesmeeting_created_by"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="client",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sales_leads", to="clients.client", verbose_name="Cliente vinculado"),
        ),
        migrations.AddField(
            model_name="lead",
            name="converted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Fecha de conversión"),
        ),
        migrations.AddField(
            model_name="lead",
            name="converted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="converted_sales_leads", to=settings.AUTH_USER_MODEL, verbose_name="Convertido por"),
        ),
        migrations.AddField(
            model_name="lead",
            name="converted_project",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="origin_sales_leads", to="projects.project", verbose_name="Proyecto creado"),
        ),
        migrations.AddField(
            model_name="lead",
            name="sale_value",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Valor vendido"),
        ),
    ]
