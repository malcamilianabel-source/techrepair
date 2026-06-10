# Generated manually on 2026-06-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_solicitud_fecha_hora_estimada'),
    ]

    operations = [
        migrations.AddField(
            model_name='avance',
            name='tipo',
            field=models.CharField(choices=[('etapa', 'Avance de etapa'), ('nota', 'Nota / comentario')], default='etapa', max_length=10),
        ),
        migrations.AlterField(
            model_name='avance',
            name='etapa',
            field=models.CharField(blank=True, choices=[('diagnostico', 'Diagnóstico inicial'), ('desmontaje', 'Desmontaje'), ('reparacion', 'Reparación'), ('prueba', 'Prueba de funcionamiento'), ('ensamblaje', 'Ensamblaje'), ('prueba_final', 'Prueba final')], default='', max_length=20),
        ),
    ]
