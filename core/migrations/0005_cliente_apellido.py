from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_solicitud_confirmacion_cliente_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='apellido',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]