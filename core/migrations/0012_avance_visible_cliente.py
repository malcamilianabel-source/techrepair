from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_avance_tipo_alter_avance_etapa'),
    ]

    operations = [
        migrations.AddField(
            model_name='avance',
            name='visible_cliente',
            field=models.BooleanField(default=False),
        ),
    ]
