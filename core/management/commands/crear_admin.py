from django.core.management.base import BaseCommand
from core.models import Usuario


class Command(BaseCommand):
    help = 'Crea el usuario admin inicial si no existe'

    def handle(self, *args, **kwargs):
        if Usuario.objects.filter(username='admin').exists():
            self.stdout.write('Usuario admin ya existe, omitiendo.')
            return

        u = Usuario.objects.create_superuser(
            username='admin',
            password='Admin2026!',
            first_name='Administrador',
            last_name='TechRepair',
            email='',
        )
        u.rol = 'admin'
        u.save()
        self.stdout.write(self.style.SUCCESS('Usuario admin creado: admin / Admin2026!'))
