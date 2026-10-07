from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0007_webproductioncity_reviewer_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="webproductionsheet",
            name="button_style_code",
            field=models.TextField(blank=True, verbose_name="Código de estilo de botones"),
        ),
        migrations.AddField(
            model_name="webproductioninternalsection",
            name="smtp_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="SMTP email"),
        ),
        migrations.AddField(
            model_name="webproductioninternalsection",
            name="smtp_password_encrypted",
            field=models.TextField(blank=True, editable=False, verbose_name="SMTP password cifrado"),
        ),
    ]
