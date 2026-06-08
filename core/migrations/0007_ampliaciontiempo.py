from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_equipo_personalizado'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AmpliacionTiempo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('cantidad', models.PositiveIntegerField()),
                ('unidad', models.CharField(
                    choices=[('horas', 'Horas'), ('minutos', 'Minutos')],
                    max_length=10)),
                ('justificacion', models.TextField()),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('solicitud', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ampliaciones',
                    to='core.solicitud')),
                ('tecnico', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ampliaciones',
                    to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
