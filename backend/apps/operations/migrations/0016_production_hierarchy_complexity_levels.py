from django.db import migrations, models
import django.db.models.deletion


MODEL_NAMES = (
    "WebProductionPage",
    "WebProductionCounty",
    "WebProductionCountyService",
    "WebProductionCity",
    "WebProductionInternalSection",
)


def forwards_complexity(apps, schema_editor):
    mapping = {"S": "1", "M": "3", "C": "5"}
    for model_name in MODEL_NAMES:
        model = apps.get_model("operations", model_name)
        for old_value, new_value in mapping.items():
            model.objects.filter(complexity=old_value).update(
                complexity=new_value,
                points=int(new_value),
            )


def backwards_complexity(apps, schema_editor):
    mapping = {"1": "S", "2": "M", "3": "M", "4": "C", "5": "C"}
    points = {"S": 1, "M": 2, "C": 3}
    for model_name in MODEL_NAMES:
        model = apps.get_model("operations", model_name)
        for old_value, new_value in mapping.items():
            model.objects.filter(complexity=old_value).update(
                complexity=new_value,
                points=points[new_value],
            )


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0015_developmentstandard"),
    ]

    operations = [
        migrations.AddField(
            model_name="webproductionpage",
            name="entry_type",
            field=models.CharField(
                choices=[("page", "Página"), ("group", "Nombre / grupo")],
                default="page",
                max_length=12,
                verbose_name="Tipo de elemento",
            ),
        ),
        migrations.AddField(
            model_name="webproductionpage",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="children",
                to="operations.webproductionpage",
                verbose_name="Elemento superior",
            ),
        ),
        migrations.RunPython(forwards_complexity, backwards_complexity),
        migrations.AlterField(
            model_name="webproductionpage",
            name="complexity",
            field=models.CharField(
                choices=[("1", "Nivel 1"), ("2", "Nivel 2"), ("3", "Nivel 3"), ("4", "Nivel 4"), ("5", "Nivel 5")],
                default="1",
                max_length=2,
            ),
        ),
        migrations.AlterField(
            model_name="webproductioncounty",
            name="complexity",
            field=models.CharField(
                choices=[("1", "Nivel 1"), ("2", "Nivel 2"), ("3", "Nivel 3"), ("4", "Nivel 4"), ("5", "Nivel 5")],
                default="1",
                max_length=2,
            ),
        ),
        migrations.AlterField(
            model_name="webproductioncountyservice",
            name="complexity",
            field=models.CharField(
                choices=[("1", "Nivel 1"), ("2", "Nivel 2"), ("3", "Nivel 3"), ("4", "Nivel 4"), ("5", "Nivel 5")],
                default="1",
                max_length=2,
            ),
        ),
        migrations.AlterField(
            model_name="webproductioncity",
            name="complexity",
            field=models.CharField(
                choices=[("1", "Nivel 1"), ("2", "Nivel 2"), ("3", "Nivel 3"), ("4", "Nivel 4"), ("5", "Nivel 5")],
                default="1",
                max_length=2,
            ),
        ),
        migrations.AlterField(
            model_name="webproductioninternalsection",
            name="complexity",
            field=models.CharField(
                choices=[("1", "Nivel 1"), ("2", "Nivel 2"), ("3", "Nivel 3"), ("4", "Nivel 4"), ("5", "Nivel 5")],
                default="1",
                max_length=2,
            ),
        ),
    ]
