# Generated manually on 2026-06-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_usuario_especialidad_usuario_especialidad_otro'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitud',
            name='fecha_hora_estimada',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
