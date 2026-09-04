# Generated for Google Calendar / Meet integration.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reminders", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleCalendarConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account_email", models.EmailField(blank=True, max_length=254)),
                ("calendar_id", models.CharField(default="primary", max_length=255)),
                ("encrypted_credentials", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("disconnected", "Desconectado"), ("connected", "Conectado"), ("error", "Error")], default="disconnected", max_length=20)),
                ("last_error", models.TextField(blank=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("connected_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="google_calendar_connections", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Conexión Google Calendar", "verbose_name_plural": "Conexiones Google Calendar"},
        ),
        migrations.AddField(model_name="meeting", name="create_google_event", field=models.BooleanField(default=True, verbose_name="Crear evento en Google Calendar")),
        migrations.AddField(model_name="meeting", name="create_google_meet", field=models.BooleanField(default=True, verbose_name="Crear Google Meet")),
        migrations.AddField(model_name="meeting", name="duration_minutes", field=models.PositiveIntegerField(default=60, verbose_name="Duración (minutos)")),
        migrations.AddField(model_name="meeting", name="google_event_id", field=models.CharField(blank=True, db_index=True, max_length=255)),
        migrations.AddField(model_name="meeting", name="google_event_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="meeting", name="google_last_synced_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="meeting", name="google_sync_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="meeting", name="google_sync_status", field=models.CharField(choices=[("not_synced", "Sin sincronizar"), ("pending", "Pendiente"), ("synced", "Sincronizado"), ("error", "Error"), ("skipped", "No aplica")], default="pending", max_length=20)),
        migrations.AlterField(model_name="meeting", name="meet_url", field=models.URLField(blank=True, help_text="Se genera automáticamente cuando Google Meet está activado.")),
        migrations.AddField(model_name="reminder", name="google_event_id", field=models.CharField(blank=True, db_index=True, max_length=255)),
        migrations.AddField(model_name="reminder", name="google_event_url", field=models.URLField(blank=True)),
        migrations.AddField(model_name="reminder", name="google_last_synced_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="reminder", name="google_sync_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="reminder", name="google_sync_status", field=models.CharField(choices=[("not_synced", "Sin sincronizar"), ("pending", "Pendiente"), ("synced", "Sincronizado"), ("error", "Error"), ("skipped", "No aplica")], default="pending", max_length=20)),
        migrations.AddField(model_name="reminder", name="sync_to_google", field=models.BooleanField(default=True, verbose_name="Sincronizar con Google Calendar")),
    ]
