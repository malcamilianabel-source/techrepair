
# Modulos probados:
#   1. calcular_fecha_libre_laboral  (distribucion de horas laborales)
#   2. calcular_tiempo_estimado      (estimacion de tiempo de reparacion)
#   3. ClienteForm                   (validacion de datos del cliente)
#   4. Avance (modelo)               (bitacora / notas de tecnico)
#   5. Vista eliminar_usuario        (control de acceso por rol)


import datetime
from django.test import TestCase, Client
from django.urls import reverse

from .models import (
    Usuario, Cliente, Equipo, Solicitud,
    DetalleSolicitud, Avance,
)
from .forms import ClienteForm, NotaBitacoraForm
from .views import calcular_fecha_libre_laboral, calcular_tiempo_estimado


# ------------------------------------------------------------
# 1. PRUEBAS: calcular_fecha_libre_laboral
# ------------------------------------------------------------
class CalcularFechaLaboralTests(TestCase):
    """
    Verifica que las horas de trabajo se distribuyan correctamente
    dentro del horario laboral del taller (9:00 - 22:00).

    Reglas de negocio:
      - Si la hora actual es < 9:00, el trabajo empieza a las 9:00.
      - Si la hora actual es >= 22:00, empieza al dia siguiente a las 9:00.
      - Las horas sobrantes del dia pasan al siguiente dia desde las 9:00.
    """

    def test_horas_dentro_del_mismo_dia(self):
        """
        [Refactor] Si quedan suficientes horas en el dia,
        la fecha estimada debe ser el mismo dia.
        Ejemplo: inicio 10:00, duracion 3h -> fin 13:00 mismo dia.
        """
        inicio = datetime.datetime(2025, 6, 10, 10, 0)
        resultado = calcular_fecha_libre_laboral(inicio, 3)
        self.assertEqual(resultado.date(), datetime.date(2025, 6, 10))
        self.assertEqual(resultado.hour, 13)
        self.assertEqual(resultado.minute, 0)

    def test_horas_que_pasan_al_dia_siguiente(self):
        """
        [Refactor] Si las horas superan el limite del dia (22:00),
        el trabajo debe continuar al dia siguiente desde las 9:00.
        Ejemplo: inicio 20:00, duracion 4h -> 2h hoy + 2h manana = fin 11:00.
        """
        inicio = datetime.datetime(2025, 6, 10, 20, 0)
        resultado = calcular_fecha_libre_laboral(inicio, 4)
        self.assertEqual(resultado.date(), datetime.date(2025, 6, 11))
        self.assertEqual(resultado.hour, 11)

    def test_inicio_antes_de_horario_laboral(self):
        """
        [Refactor] Si el trabajo se registra antes de las 9:00,
        debe comenzar exactamente a las 9:00 del mismo dia.
        Ejemplo: registro 7:00, duracion 2h -> fin 11:00.
        """
        inicio = datetime.datetime(2025, 6, 10, 7, 0)
        resultado = calcular_fecha_libre_laboral(inicio, 2)
        self.assertEqual(resultado.date(), datetime.date(2025, 6, 10))
        self.assertEqual(resultado.hour, 11)

    def test_inicio_despues_de_horario_laboral(self):
        """
        [Refactor] Si el trabajo se registra despues de las 22:00,
        debe iniciar al dia siguiente a las 9:00.
        Ejemplo: registro 23:00, duracion 1h -> fin manana 10:00.
        """
        inicio = datetime.datetime(2025, 6, 10, 23, 0)
        resultado = calcular_fecha_libre_laboral(inicio, 1)
        self.assertEqual(resultado.date(), datetime.date(2025, 6, 11))
        self.assertEqual(resultado.hour, 10)


# ------------------------------------------------------------
# 2. PRUEBAS: calcular_tiempo_estimado
# ------------------------------------------------------------
class CalcularTiempoEstimadoTests(TestCase):
    """
    Verifica la logica de estimacion de tiempo de reparacion
    segun el tipo de servicio y el estado fisico del equipo.

    Tabla de horas base:
      revision: 1h, preventivo: 2h, software: 3h, hardware: 6h

    Multiplicadores por estado fisico:
      bueno: x1.0, regular: x1.25, malo: x1.5
    """

    def setUp(self):
        self.fecha = datetime.date(2025, 6, 10)

    def test_revision_equipo_bueno(self):
        """
        [Refactor] Revision + equipo bueno = 1h x 1.0 = 1 hora exacta.
        El texto debe ser '1 hora' (no '1 horas').
        """
        dias, fecha_est, texto, horas, fecha_hora = calcular_tiempo_estimado(
            'revision', 'bueno', self.fecha
        )
        self.assertEqual(horas, 1.0)
        self.assertEqual(texto, '1 hora')
# CALCULO DE TIEMPO EQUIPO MALO
    def test_hardware_equipo_malo(self):
        """
        [Refactor] Hardware + equipo malo = 6h x 1.5 = 9 horas.
        Debe requerir 2 dias estimados (ceil(9/8) = 2).
        """
        dias, fecha_est, texto, horas, fecha_hora = calcular_tiempo_estimado(
            'hardware', 'malo', self.fecha
        )
        self.assertEqual(horas, 9.0)
        self.assertEqual(dias, 2)
# CALCULO DE TIEMPO EQUIPO ESTADO REGULAR
    def test_software_equipo_regular(self):
        """
        [Refactor] Software + regular = 3h x 1.25 = 3.75h = '3h 45min'.
        """
        dias, fecha_est, texto, horas, fecha_hora = calcular_tiempo_estimado(
            'software', 'regular', self.fecha
        )
        self.assertEqual(horas, 3.75)
        self.assertEqual(texto, '3h 45min')

    def test_fecha_estimada_es_date(self):
        """
        [Refactor] La funcion debe retornar un objeto date valido
        como segunda posicion del resultado.
        """
        _, fecha_est, _, _, _ = calcular_tiempo_estimado(
            'preventivo', 'bueno', self.fecha
        )
        self.assertIsInstance(fecha_est, datetime.date)

    def test_tipo_desconocido_usa_valor_defecto(self):
        """
        [Refactor] Un tipo de servicio no reconocido debe usar
        el valor base por defecto (3h) sin lanzar excepcion.
        """
        _, _, _, horas, _ = calcular_tiempo_estimado(
            'inexistente', 'bueno', self.fecha
        )
        self.assertEqual(horas, 3.0)


# ------------------------------------------------------------
# 3. PRUEBAS: ClienteForm (validacion de formularios)
# ------------------------------------------------------------
class ClienteFormTests(TestCase):
    """
    Verifica que el formulario de registro de clientes rechace
    datos invalidos y acepte datos correctos.
    """

    def _datos_validos(self, **override):
        datos = {
            'nombre':    'Juan Carlos',
            'apellido':  'Perez Rios',
            'dni':       '12345678',
            'telefono':  '987654321',
            'direccion': '',
            'correo':    '',
        }
        datos.update(override)
        return datos

    def test_formulario_valido(self):
        """[Refactor] Con datos correctos el formulario debe ser valido."""
        form = ClienteForm(data=self._datos_validos())
        self.assertTrue(form.is_valid(), form.errors)

    def test_dni_con_letras_es_invalido(self):
        """[Refactor] El DNI no puede contener letras."""
        form = ClienteForm(data=self._datos_validos(dni='1234ABCD'))
        self.assertFalse(form.is_valid())
        self.assertIn('dni', form.errors)

    def test_dni_menos_de_8_digitos_es_invalido(self):
        """[Refactor] El DNI debe tener exactamente 8 digitos."""
        form = ClienteForm(data=self._datos_validos(dni='1234'))
        self.assertFalse(form.is_valid())
        self.assertIn('dni', form.errors)

    def test_telefono_sin_9_inicial_es_invalido(self):
        """[Refactor] El telefono peruano debe iniciar con 9."""
        form = ClienteForm(data=self._datos_validos(telefono='123456789'))
        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)

    def test_telefono_con_8_digitos_es_invalido(self):
        """[Refactor] El telefono debe tener exactamente 9 digitos."""
        form = ClienteForm(data=self._datos_validos(telefono='98765432'))
        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)


# ------------------------------------------------------------
# 4. PRUEBAS: Modelo Avance (bitacora)
# ------------------------------------------------------------
class AvanceModelTests(TestCase):
    """
    Verifica el comportamiento del modelo Avance,
    especialmente la distincion entre tipo 'etapa' y 'nota',
    y la visibilidad para el cliente.
    """

    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username='admin_test', password='pass123', rol='admin'
        )
        self.cliente = Cliente.objects.create(
            nombre='Maria', apellido='Lopez', dni='87654321', telefono='912345678'
        )
        self.equipo = Equipo.objects.create(
            cliente=self.cliente, tipo='laptop',
            marca='hp', modelo='Pavilion', serie='SN-TEST-001', estado='bueno'
        )
        self.solicitud = Solicitud.objects.create(
            cliente=self.cliente, equipo=self.equipo,
            tipo_reparacion='software',
            descripcion='No enciende',
            prioridad='media',
        )

    def test_avance_etapa_tiene_tipo_etapa_por_defecto(self):
        """
        [Refactor] Al crear un Avance sin especificar tipo,
        debe quedar como 'etapa' (valor por defecto del campo).
        """
        av = Avance.objects.create(
            solicitud=self.solicitud,
            usuario=self.admin,
            etapa='diagnostico',
            descripcion='Se reviso el equipo.',
        )
        self.assertEqual(av.tipo, 'etapa')

    def test_nota_no_requiere_etapa(self):
        """
        [Refactor] Una nota libre (tipo='nota') puede guardarse
        sin especificar una etapa -- el campo etapa queda vacio.
        """
        nota = Avance.objects.create(
            solicitud=self.solicitud,
            usuario=self.admin,
            tipo='nota',
            etapa='',
            descripcion='Se necesita repuesto de pantalla.',
        )
        self.assertEqual(nota.tipo, 'nota')
        self.assertEqual(nota.etapa, '')

    def test_visible_cliente_es_false_por_defecto(self):
        """
        [Refactor] Las notas deben ser privadas por defecto.
        Solo si el tecnico marca visible_cliente=True se muestra al cliente.
        """
        nota = Avance.objects.create(
            solicitud=self.solicitud,
            usuario=self.admin,
            tipo='nota',
            descripcion='Nota interna confidencial.',
        )
        self.assertFalse(nota.visible_cliente)

    def test_nota_visible_para_cliente(self):
        """
        [Refactor] Cuando visible_cliente=True, la nota debe
        guardarse y recuperarse correctamente con ese valor.
        """
        nota = Avance.objects.create(
            solicitud=self.solicitud,
            usuario=self.admin,
            tipo='nota',
            descripcion='Su equipo necesita repuesto, se avisara cuando llegue.',
            visible_cliente=True,
        )
        self.assertTrue(nota.visible_cliente)


# ------------------------------------------------------------
# 5. PRUEBAS: Vista eliminar_usuario (control de acceso)
# ------------------------------------------------------------
class EliminarUsuarioViewTests(TestCase):
    """
    Verifica que la vista de eliminacion de usuarios aplique
    correctamente las reglas de acceso por rol.

    Reglas:
      - Solo el admin puede eliminar usuarios.
      - Un tecnico o recepcionista debe ser redirigido al dashboard.
      - El admin no puede eliminarse a si mismo.
    """

    def setUp(self):
        self.client = Client()
        self.admin = Usuario.objects.create_user(
            username='admin_test', password='admin123', rol='admin'
        )
        self.tecnico = Usuario.objects.create_user(
            username='tec_test', password='tec123', rol='tec'
        )
        self.otro_usuario = Usuario.objects.create_user(
            username='recep_test', password='recep123', rol='recep'
        )

    def test_tecnico_no_puede_eliminar_usuarios(self):
        """
        [Refactor] Un tecnico que intenta eliminar un usuario
        debe ser redirigido al dashboard sin eliminar nada.
        """
        self.client.login(username='tec_test', password='tec123')
        url = reverse('eliminar_usuario', args=[self.otro_usuario.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(Usuario.objects.filter(pk=self.otro_usuario.pk).exists())

    def test_admin_puede_eliminar_otro_usuario(self):
        """
        [Refactor] El admin puede eliminar un usuario que no tenga
        solicitudes activas asignadas.
        """
        self.client.login(username='admin_test', password='admin123')
        url = reverse('eliminar_usuario', args=[self.otro_usuario.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('consultar_usuarios'))
        self.assertFalse(Usuario.objects.filter(pk=self.otro_usuario.pk).exists())

    def test_admin_no_puede_eliminarse_a_si_mismo(self):
        """
        [Refactor] El admin no debe poder eliminar su propio usuario,
        ya que quedaria el sistema sin administrador.
        """
        self.client.login(username='admin_test', password='admin123')
        url = reverse('eliminar_usuario', args=[self.admin.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('consultar_usuarios'))
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())
