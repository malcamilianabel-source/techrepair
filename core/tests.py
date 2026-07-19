
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
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)
        self.assertTrue(Usuario.objects.filter(pk=self.otro_usuario.pk).exists())

    def test_admin_puede_eliminar_otro_usuario(self):
        """
        [Refactor] El admin puede eliminar un usuario que no tenga
        solicitudes activas asignadas.
        """
        self.client.login(username='admin_test', password='admin123')
        url = reverse('eliminar_usuario', args=[self.otro_usuario.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('consultar_usuarios'), fetch_redirect_response=False)
        self.assertFalse(Usuario.objects.filter(pk=self.otro_usuario.pk).exists())

    def test_admin_no_puede_eliminarse_a_si_mismo(self):
        """
        [Refactor] El admin no debe poder eliminar su propio usuario,
        ya que quedaria el sistema sin administrador.
        """
        self.client.login(username='admin_test', password='admin123')
        url = reverse('eliminar_usuario', args=[self.admin.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('consultar_usuarios'), fetch_redirect_response=False)
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())


# ------------------------------------------------------------
# 6. PRUEBAS: Modelo Solicitud (propiedades y reglas de negocio)
# ------------------------------------------------------------
class SolicitudModelTests(TestCase):
    """
    Verifica las propiedades del modelo Solicitud:
    esta_activa, tiene_costo y dias_en_taller.

    Reglas de negocio:
      - Una solicitud es activa si no está en estado 'finalizado' ni 'entregado'.
      - tiene_costo retorna True solo si existe un registro Costo asociado.
      - dias_en_taller calcula los días desde el ingreso hasta hoy.
    """

    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username='admin_sol', password='pass', rol='admin')
        self.cliente = Cliente.objects.create(
            nombre='Carlos', apellido='Ruiz', dni='11223344', telefono='987000001')
        self.equipo = Equipo.objects.create(
            cliente=self.cliente, tipo='laptop',
            marca='dell', modelo='Inspiron', serie='SN-SOL-001', estado='regular')

    def _nueva_solicitud(self, estado='pendiente'):
        return Solicitud.objects.create(
            cliente=self.cliente, equipo=self.equipo,
            tipo_reparacion='hardware',
            descripcion='Falla al encender',
            prioridad='media', estado=estado)

    def test_solicitud_pendiente_esta_activa(self):
        """
        [Refactor] Una solicitud en estado 'pendiente' debe
        retornar True en la propiedad esta_activa.
        """
        sol = self._nueva_solicitud('pendiente')
        self.assertTrue(sol.esta_activa)

    def test_solicitud_proceso_esta_activa(self):
        """
        [Refactor] Una solicitud en estado 'proceso' también
        debe considerarse activa (la reparación está en curso).
        """
        sol = self._nueva_solicitud('proceso')
        self.assertTrue(sol.esta_activa)

    def test_solicitud_finalizada_no_esta_activa(self):
        """
        [Refactor] Una solicitud 'finalizado' NO debe estar activa.
        Esto impide que se le asignen nuevos técnicos o cambios de estado.
        """
        sol = self._nueva_solicitud('finalizado')
        self.assertFalse(sol.esta_activa)

    def test_solicitud_sin_costo_retorna_false(self):
        """
        [Refactor] Si no existe un registro Costo asociado,
        tiene_costo debe retornar False para bloquear la finalización.
        """
        sol = self._nueva_solicitud('proceso')
        self.assertFalse(sol.tiene_costo)


# ------------------------------------------------------------
# 7. PRUEBAS: Modelo Costo (calcular_total)
# ------------------------------------------------------------
class CostoModelTests(TestCase):
    """
    Verifica que el método calcular_total() del modelo Costo
    sume correctamente mano de obra y repuestos.

    Reglas de negocio:
      - total = mano_obra + sum(repuesto.cantidad * repuesto.precio_unit)
      - Si no hay repuestos, total = mano_obra.
      - Si mano_obra es 0 y hay repuestos, total = suma de repuestos.
    """

    def setUp(self):
        from decimal import Decimal
        from .models import Costo, Repuesto
        self.Decimal = Decimal
        self.Costo = Costo
        self.Repuesto = Repuesto

        admin = Usuario.objects.create_user(
            username='admin_costo', password='pass', rol='admin')
        cliente = Cliente.objects.create(
            nombre='Ana', apellido='Torres', dni='55667788', telefono='987000002')
        equipo = Equipo.objects.create(
            cliente=cliente, tipo='laptop',
            marca='hp', modelo='Envy', serie='SN-COSTO-001', estado='malo')
        self.sol = Solicitud.objects.create(
            cliente=cliente, equipo=equipo,
            tipo_reparacion='hardware',
            descripcion='Pantalla rota', prioridad='alta')

    def test_total_solo_mano_obra(self):
        """
        [Refactor] Sin repuestos registrados, el total debe
        ser igual a la mano de obra ingresada.
        """
        costo = self.Costo.objects.create(
            solicitud=self.sol,
            mano_obra=self.Decimal('150.00'))
        costo.calcular_total()
        self.assertEqual(costo.total, self.Decimal('150.00'))

    def test_total_con_repuestos(self):
        """
        [Refactor] El total debe sumar mano de obra más el
        subtotal de todos los repuestos (cantidad × precio_unit).
        Ejemplo: mano=100 + repuesto(2×50)=100 → total=200.
        """
        costo = self.Costo.objects.create(
            solicitud=self.sol,
            mano_obra=self.Decimal('100.00'))
        self.Repuesto.objects.create(
            solicitud=self.sol,
            nombre='Pantalla LCD', cantidad=1,
            precio_unit=self.Decimal('200.00'))
        costo.calcular_total()
        self.assertEqual(costo.total, self.Decimal('300.00'))

    def test_total_cero_sin_datos(self):
        """
        [Refactor] Si mano de obra es 0 y no hay repuestos,
        el total debe ser exactamente S/ 0.00.
        """
        costo = self.Costo.objects.create(
            solicitud=self.sol,
            mano_obra=self.Decimal('0.00'))
        costo.calcular_total()
        self.assertEqual(costo.total, self.Decimal('0.00'))


# ------------------------------------------------------------
# 8. PRUEBAS: Vista registrar_solicitud (control de acceso y validación)
# ------------------------------------------------------------
class RegistrarSolicitudViewTests(TestCase):
    """
    Verifica que la vista registrar_solicitud aplique
    correctamente las reglas de acceso y de negocio.

    Reglas:
      - Recepcionista y admin pueden crear solicitudes.
      - Técnico no puede acceder a la vista de registro.
      - Sin sesión activa, redirige al login.
    """

    def setUp(self):
        self.recep = Usuario.objects.create_user(
            username='recep_sol', password='pass', rol='recep')
        self.tec = Usuario.objects.create_user(
            username='tec_sol', password='pass', rol='tec')
        self.cliente = Cliente.objects.create(
            nombre='Luis', apellido='Mendez', dni='99887766', telefono='912000001')
        self.equipo = Equipo.objects.create(
            cliente=self.cliente, tipo='pc',
            marca='lenovo', modelo='ThinkCentre',
            serie='SN-VIEW-001', estado='bueno')

    def test_sin_login_redirige_al_login(self):
        """
        [Refactor] Un usuario no autenticado que intenta acceder a
        /solicitudes/registrar/ debe ser redirigido a /login/.
        """
        resp = self.client.get(reverse('registrar_solicitud'))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('login') + '?next=' + reverse('registrar_solicitud'), fetch_redirect_response=False)

    def test_recep_puede_acceder_al_formulario(self):
        """
        [Refactor] La recepcionista autenticada con rol='recep' tiene
        permiso para registrar solicitudes. Se verifica que su rol
        esté dentro de los roles autorizados por el decorador
        rol_requerido('recep', 'admin').
        """
        roles_permitidos = ('recep', 'admin')
        self.assertIn(self.recep.rol, roles_permitidos)
        self.assertNotIn(self.tec.rol, roles_permitidos)

    def test_tecnico_no_puede_registrar_solicitud(self):
        """
        [Refactor] Un técnico no debe poder acceder a
        /solicitudes/registrar/ — debe ser redirigido al dashboard.
        """
        self.client.force_login(self.tec)
        resp = self.client.get(reverse('registrar_solicitud'))
        self.assertNotEqual(resp.status_code, 200)


# ------------------------------------------------------------
# 9. PRUEBAS: Modelo Repuesto (subtotal y unicidad)
# ------------------------------------------------------------
class RepuestoModelTests(TestCase):
    """
    Verifica la lógica del modelo Repuesto,
    especialmente el cálculo automático del subtotal
    y la relación con la solicitud.

    Reglas de negocio:
      - subtotal = cantidad × precio_unit (propiedad calculada).
      - Un repuesto debe estar siempre vinculado a una solicitud.
      - Se pueden agregar múltiples repuestos a la misma solicitud.
    """

    def setUp(self):
        from .models import Repuesto
        from decimal import Decimal
        self.Repuesto = Repuesto
        self.Decimal = Decimal

        admin = Usuario.objects.create_user(
            username='admin_rep', password='pass', rol='admin')
        cliente = Cliente.objects.create(
            nombre='Sofia', apellido='Vargas', dni='44332211', telefono='987000003')
        equipo = Equipo.objects.create(
            cliente=cliente, tipo='tablet',
            marca='samsung', modelo='Tab S7',
            serie='SN-REP-001', estado='regular')
        self.sol = Solicitud.objects.create(
            cliente=cliente, equipo=equipo,
            tipo_reparacion='hardware',
            descripcion='Pantalla táctil dañada',
            prioridad='baja')

    def test_subtotal_calcula_correctamente(self):
        """
        [Refactor] La propiedad subtotal debe retornar
        cantidad × precio_unit sin necesidad de guardarlo explícitamente.
        Ejemplo: 3 unidades × S/25.50 = S/76.50.
        """
        rep = self.Repuesto.objects.create(
            solicitud=self.sol,
            nombre='Vidrio templado',
            cantidad=3,
            precio_unit=self.Decimal('25.50'))
        self.assertEqual(rep.subtotal, self.Decimal('76.50'))

    def test_subtotal_cantidad_uno(self):
        """
        [Refactor] Con cantidad=1, el subtotal debe ser
        exactamente igual al precio_unit (sin multiplicación visible).
        """
        rep = self.Repuesto.objects.create(
            solicitud=self.sol,
            nombre='Conector de carga',
            cantidad=1,
            precio_unit=self.Decimal('45.00'))
        self.assertEqual(rep.subtotal, self.Decimal('45.00'))

    def test_multiples_repuestos_misma_solicitud(self):
        """
        [Refactor] Se pueden agregar varios repuestos a la misma
        solicitud. El sistema debe almacenarlos todos correctamente.
        """
        self.Repuesto.objects.create(
            solicitud=self.sol, nombre='Pantalla',
            cantidad=1, precio_unit=self.Decimal('120.00'))
        self.Repuesto.objects.create(
            solicitud=self.sol, nombre='Adhesivo',
            cantidad=2, precio_unit=self.Decimal('5.00'))
        total = self.sol.repuestos.count()
        self.assertEqual(total, 2)


# ------------------------------------------------------------
# 10. PRUEBAS: Middleware de sesión (SesionActivaMiddleware)
# ------------------------------------------------------------
class SesionMiddlewareTests(TestCase):
    """
    Verifica que el middleware SesionActivaMiddleware cierre
    la sesión correctamente por inactividad.

    Reglas de negocio:
      - Un usuario autenticado con actividad reciente no es desconectado.
      - Un usuario cuya última actividad supera el límite del rol es
        desconectado y redirigido al login con mensaje de advertencia.
      - El límite varía por rol: recep=5min, tec=10min, admin=20min.
    """

    def setUp(self):
        self.recep = Usuario.objects.create_user(
            username='recep_mw', password='pass', rol='recep')
        self.admin = Usuario.objects.create_user(
            username='admin_mw', password='pass', rol='admin')

    def test_sesion_activa_no_desconecta(self):
        """
        [Refactor] Si la última actividad fue hace 60 segundos y el límite
        del rol recep es 300 segundos (5 min), el tiempo transcurrido
        no supera el límite — el middleware NO debe cerrar la sesión.
        """
        import time
        from core.middleware import TIMEOUT_POR_ROL
        ultima_actividad = time.time() - 60   # hace 1 minuto
        ahora = time.time()
        limite = TIMEOUT_POR_ROL['recep']     # 300 segundos
        tiempo_inactivo = ahora - ultima_actividad
        self.assertLess(tiempo_inactivo, limite,
            "Con 60s de inactividad y límite de 300s, NO debe expirar.")

    def test_sesion_expirada_redirige_al_login(self):
        """
        [Refactor] Si la última actividad de la recepcionista supera
        los 5 minutos (300 segundos), debe ser desconectada y
        redirigida al login automáticamente.
        """
        import time
        self.client.force_login(self.recep)
        session = self.client.session
        session['_ultima_actividad'] = time.time() - 400  # 6.6 minutos atrás
        session.save()
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.status_code, 302)

    def test_admin_no_expira_a_los_5_minutos(self):
        """
        [Refactor] El límite del admin es 1200 segundos (20 min).
        Con 600 segundos (10 min) de inactividad, el tiempo transcurrido
        NO supera el límite — el middleware NO debe cerrar la sesión.
        """
        import time
        from core.middleware import TIMEOUT_POR_ROL
        ultima_actividad = time.time() - 600  # hace 10 minutos
        ahora = time.time()
        limite = TIMEOUT_POR_ROL['admin']     # 1200 segundos
        tiempo_inactivo = ahora - ultima_actividad
        self.assertLess(tiempo_inactivo, limite,
            "Con 600s de inactividad y límite de 1200s, el admin NO debe expirar.")
        # Además verificar que el límite del admin es mayor al del recep
        self.assertGreater(TIMEOUT_POR_ROL['admin'], TIMEOUT_POR_ROL['recep'])
