from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_cliente_apellido'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipo',
            name='tipo_personalizado',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='equipo',
            name='marca_personalizada',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]