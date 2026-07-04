import uuid
from django.db import migrations, models


def generar_tokens(apps, schema_editor):
    """Asigna un UUID único a cada solicitud existente."""
    Solicitud = apps.get_model('core', 'Solicitud')
    for sol in Solicitud.objects.all():
        sol.token_seguimiento = uuid.uuid4()
        sol.save(update_fields=['token_seguimiento'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_add_prioridad_anterior'),
    ]

    operations = [
        # Paso 1: agregar el campo SIN unique para que todas las filas
        # reciban el mismo valor por defecto sin conflicto
        migrations.AddField(
            model_name='solicitud',
            name='token_seguimiento',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=False),
        ),
        # Paso 2: data migration — asignar UUID distinto a cada fila
        migrations.RunPython(generar_tokens, migrations.RunPython.noop),
        # Paso 3: ahora sí aplicar la restricción UNIQUE
        migrations.AlterField(
            model_name='solicitud',
            name='token_seguimiento',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
