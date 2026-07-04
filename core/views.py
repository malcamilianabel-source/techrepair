import uuid
import datetime
import json
import re
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Case, Count, DecimalField, F, IntegerField, Q, Sum, When
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import rol_requerido, tecnico_asignado_o_staff
from .forms import (
    AmpliacionTiempoForm, AsignarTecnicoForm, AvanceForm, CambiarEstadoForm,
    ClienteForm, ClienteUpdateForm, CostoForm, DiagnosticoForm, EquipoForm,
    EquipoUpdateForm, NotaBitacoraForm, RepuestoForm, SolicitudForm, UsuarioForm,
)
from .models import (
    AmpliacionTiempo, Avance, Cliente, Costo, DetalleSolicitud, Equipo,
    HistorialEstado, Notificacion, Repuesto, Solicitud, Usuario,
)

# deploy test


# ── HELPERS ────────────────────────────────────────────────────

def parsear_rango_fechas(request):
    """Devuelve (fecha_inicio, fecha_fin, fi_str, ff_str, error)."""
    fi_str = request.GET.get('fecha_inicio', '')
    ff_str = request.GET.get('fecha_fin', '')
    fi = ff = error = None
    try:
        if fi_str:
            fi = datetime.date.fromisoformat(fi_str)
        if ff_str:
            ff = datetime.date.fromisoformat(ff_str)
        if fi and ff and fi > ff:
            error = 'La fecha de inicio no puede ser mayor que la fecha fin.'
            fi = ff = None
    except ValueError:
        error = 'Formato de fecha inválido.'
        fi = ff = None
    return fi, ff, fi_str, ff_str, error


def filtrar_por_rango(qs, campo_fecha, fi, ff):
    if fi:
        qs = qs.filter(**{f'{campo_fecha}__gte': fi})
    if ff:
        qs = qs.filter(**{f'{campo_fecha}__lte': ff})
    return qs


def paginar(request, qs, per_page=20):
    return Paginator(qs, per_page).get_page(request.GET.get('page', 1))

# ── LOGIN ──────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            error = 'Usuario o contraseña incorrectos.'

    return render(request, 'core/login.html', {'error': error})


# ── LOGOUT ─────────────────────────────────────────────────────
def logout_view(request):
    logout(request)
    return redirect('login')


# ── DASHBOARD ─────────────────────────────────────────────────
@login_required
def dashboard(request):
    if request.user.rol == 'tec':
        # Dashboard del técnico — solo sus solicitudes
        orden = request.GET.get('orden', 'desc')  # desc=Alta primero, asc=Baja primero
        orden_prioridad = Case(
            When(prioridad='alta',  then=0),
            When(prioridad='media', then=1),
            When(prioridad='baja',  then=2),
            default=3, output_field=IntegerField(),
        )
        mis_solicitudes = Solicitud.objects.filter(
            detalle__tecnico=request.user
        ).select_related('cliente', 'equipo').annotate(
            _ord=orden_prioridad
        ).order_by('_ord' if orden == 'desc' else '-_ord', '-creado_en')

        pendientes  = mis_solicitudes.filter(estado='pendiente').count()
        en_proceso  = mis_solicitudes.filter(estado='proceso').count()
        finalizadas = mis_solicitudes.filter(estado='finalizado').count()

        # Calcular horas de carga personal
        activas = mis_solicitudes.filter(estado__in=['pendiente', 'proceso'])
        agg = activas.aggregate(horas=Sum('tiempo_estimado_horas'))
        total_horas = int(agg['horas'] or 0)

        return render(request, 'core/dashboard.html', {
            'mis_solicitudes': mis_solicitudes[:8],
            'pendientes':      pendientes,
            'en_proceso':      en_proceso,
            'finalizadas':     finalizadas,
            'total_horas':     total_horas,
            'total_activas':   activas.count(),
            'orden':           orden,
        })

    else:
        # Dashboard del admin/recepcionista
        total_sol   = Solicitud.objects.count()
        pendientes  = Solicitud.objects.filter(estado='pendiente').count()
        en_proceso  = Solicitud.objects.filter(estado='proceso').count()
        finalizadas = Solicitud.objects.filter(estado='finalizado').count()

        # Carga por técnico con horas
        tecnicos_data = Usuario.objects.filter(rol='tec').annotate(
            trabajos=Count(
                'detalles__solicitud',
                filter=Q(detalles__solicitud__estado__in=['pendiente', 'proceso'])
            ),
            horas_dec=Sum(
                'detalles__solicitud__tiempo_estimado_horas',
                filter=Q(detalles__solicitud__estado__in=['pendiente', 'proceso'])
            ),
        )
        carga_tecnicos = [
            {
                'nombre': t.get_full_name() or t.username,
                'trabajos': t.trabajos or 0,
                'horas': int(t.horas_dec or 0),
            }
            for t in tecnicos_data
        ]

        recientes = Solicitud.objects.select_related(
            'cliente', 'equipo', 'detalle__tecnico'
        ).order_by('-creado_en')[:8]

        return render(request, 'core/dashboard.html', {
            'total_sol':      total_sol,
            'pendientes':     pendientes,
            'en_proceso':     en_proceso,
            'finalizadas':    finalizadas,
            'carga_tecnicos': carga_tecnicos,
            'recientes':      recientes,
        })


# ── LISTAR CLIENTES ────────────────────────────────────────────
@login_required
def consultar_clientes(request):
    query    = request.GET.get('q', '')
    clientes = Cliente.objects.all().order_by('-creado_en')
    if query:
        clientes = clientes.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query) |
            Q(dni__icontains=query)    | Q(telefono__icontains=query)
        )
    page_obj = paginar(request, clientes)
    return render(request, 'core/clientes/consultar.html', {
        'clientes': page_obj, 'page_obj': page_obj, 'query': query,
    })


# ── REGISTRAR CLIENTE ──────────────────────────────────────────
@login_required
def registrar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(
                request,
                f'Cliente {cliente.nombre_completo} registrado. Ahora registra su equipo.'
            )
            return redirect(f'/equipos/registrar/?cliente_id={cliente.pk}')
    else:
        form = ClienteForm()
    return render(request, 'core/clientes/registrar.html', {'form': form})


# ── ACTUALIZAR CLIENTE ─────────────────────────────────────────
@login_required
def actualizar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteUpdateForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('consultar_clientes')
    else:
        form = ClienteUpdateForm(instance=cliente)
    return render(request, 'core/clientes/actualizar.html', {
        'form':    form,
        'cliente': cliente,
    })

# ── CONSULTAR EQUIPOS ──────────────────────────────────────────
@login_required
def consultar_equipos(request):
    query   = request.GET.get('q', '')
    tipo    = request.GET.get('tipo', '')
    equipos = Equipo.objects.select_related('cliente').order_by('-creado_en')
    if query:
        equipos = equipos.filter(
            Q(marca__icontains=query) | Q(modelo__icontains=query) |
            Q(serie__icontains=query)
        )
    if tipo:
        equipos = equipos.filter(tipo=tipo)
    page_obj = paginar(request, equipos)
    return render(request, 'core/equipos/consultar.html', {
        'equipos': page_obj, 'page_obj': page_obj,
        'query': query, 'tipo': tipo, 'tipos': Equipo.TIPOS,
    })


# ── REGISTRAR EQUIPO ───────────────────────────────────────────
@login_required
def registrar_equipo(request):
    if request.user.rol == 'tec':
        return redirect('dashboard')

    cliente_id = request.GET.get('cliente_id') or request.POST.get('cliente_id_hidden')
    cliente_fijo = None
    if cliente_id:
        try:
            cliente_fijo = Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            cliente_fijo = None

    if request.method == 'POST':
        form = EquipoForm(request.POST)
        if form.is_valid():
            equipo = form.save()
            messages.success(request, 'Equipo registrado correctamente.')
            if cliente_fijo:
                return redirect(
                    f'/solicitudes/registrar/?cliente_id={cliente_fijo.pk}&equipo_id={equipo.pk}'
                )
            return redirect('consultar_equipos')
    else:
        initial = {}
        if cliente_fijo:
            initial['cliente'] = cliente_fijo
        form = EquipoForm(initial=initial)

    return render(request, 'core/equipos/registrar.html', {
        'form':         form,
        'cliente_fijo': cliente_fijo,
    })


# ── HORARIO LABORAL ────────────────────────────────────────────
HORA_INICIO = 9   # 9am
HORA_FIN    = 22  # 10pm

def calcular_fecha_libre_laboral(now, total_horas):
    """Distribuye total_horas dentro del horario 9am-10pm."""
    hora_actual = now.hour + now.minute / 60

    if hora_actual < HORA_INICIO:
        inicio = now.replace(hour=HORA_INICIO, minute=0, second=0, microsecond=0)
    elif hora_actual >= HORA_FIN:
        inicio = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1),
            datetime.time(HORA_INICIO, 0)
        )
    else:
        inicio = now

    current        = inicio
    horas_restantes = total_horas

    while horas_restantes > 0:
        fin_dia   = current.replace(hour=HORA_FIN, minute=0, second=0, microsecond=0)
        horas_hoy = (fin_dia - current).total_seconds() / 3600

        if horas_restantes <= horas_hoy:
            current = current + datetime.timedelta(hours=horas_restantes)
            break
        else:
            horas_restantes -= horas_hoy
            current = datetime.datetime.combine(
                current.date() + datetime.timedelta(days=1),
                datetime.time(HORA_INICIO, 0)
            )

    return current


# ── MOTOR DE ESTIMACIÓN DE TIEMPO ─────────────────────────────
def calcular_tiempo_estimado(tipo, estado_fisico, fecha_ingreso):
    import math
    tiempos_base = {
        'revision':   1,
        'preventivo': 2,
        'software':   3,
        'hardware':   6,
    }
    multiplicadores = {
        'bueno':   1.0,
        'regular': 1.25,
        'malo':    1.5,
    }
    base = tiempos_base.get(tipo, 3)
    mult = multiplicadores.get(estado_fisico, 1.25)
    horas = base * mult

    if horas < 1:
        minutos = round(horas * 60)
        tiempo_texto = f"{minutos} minutos"
    elif horas == int(horas):
        tiempo_texto = f"{int(horas)} hora{'s' if horas != 1 else ''}"
    else:
        horas_int = int(horas)
        minutos = round((horas - horas_int) * 60)
        tiempo_texto = f"{horas_int}h {minutos}min"

    inicio = datetime.datetime.combine(fecha_ingreso, datetime.time(HORA_INICIO, 0))
    fecha_estimada = calcular_fecha_libre_laboral(inicio, horas)
    dias_estimados = math.ceil(horas / 8)

    return dias_estimados, fecha_estimada.date(), tiempo_texto, horas, fecha_estimada


# ── REGISTRAR SOLICITUD ────────────────────────────────────────
@login_required
def registrar_solicitud(request):
    if request.user.rol == 'tec':
        return redirect('consultar_solicitudes')

    # Pre-vinculación desde flujo automático
    cliente_id   = request.GET.get('cliente_id') or request.POST.get('cliente_id_hidden')
    equipo_id    = request.GET.get('equipo_id')  or request.POST.get('equipo_id_hidden')
    cliente_fijo = None
    equipo_fijo  = None
    if cliente_id:
        try:
            cliente_fijo = Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            pass
    if equipo_id:
        try:
            equipo_fijo = Equipo.objects.get(pk=equipo_id)
        except Equipo.DoesNotExist:
            pass

    if request.method == 'POST':
        form = SolicitudForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                solicitud = form.save(commit=False)
                dias, fecha_est, tiempo_texto, horas_est, fecha_hora_est = calcular_tiempo_estimado(
                     solicitud.tipo_reparacion,
                     solicitud.equipo.estado,
                     timezone.localdate()
                )
                solicitud.dias_estimados        = dias
                solicitud.fecha_estimada        = fecha_est
                solicitud.fecha_hora_estimada   = fecha_hora_est
                solicitud.tiempo_estimado_texto = tiempo_texto
                solicitud.tiempo_estimado_horas = horas_est
                solicitud.save()
                DetalleSolicitud.objects.get_or_create(solicitud=solicitud)
                HistorialEstado.objects.create(
                    solicitud=solicitud, usuario=request.user,
                    estado_antes='', estado_nuevo='pendiente',
                    observacion='Solicitud creada'
                )
            messages.success(request,
                f'Solicitud #{solicitud.id} registrada. '
                f'Tiempo estimado: {tiempo_texto}.')
            return redirect('detalle_solicitud', pk=solicitud.pk)
    else:
        initial = {}
        if cliente_fijo:
            initial['cliente'] = cliente_fijo
        if equipo_fijo:
            initial['equipo'] = equipo_fijo
        form = SolicitudForm(initial=initial)

    return render(request, 'core/solicitudes/registrar.html', {
        'form':         form,
        'cliente_fijo': cliente_fijo,
        'equipo_fijo':  equipo_fijo,
    })


# ── CONSULTAR SOLICITUDES ──────────────────────────────────────
@login_required
def consultar_solicitudes(request):
    estado   = request.GET.get('estado', '')
    tecnico  = request.GET.get('tecnico', '')
    prioridad= request.GET.get('prioridad', '')
    q        = request.GET.get('q', '')
    orden    = request.GET.get('orden', 'desc')  # desc=Alta primero, asc=Baja primero

    orden_prioridad = Case(
        When(prioridad='alta',  then=0),
        When(prioridad='media', then=1),
        When(prioridad='baja',  then=2),
        default=3,
        output_field=IntegerField(),
    )
    solicitudes = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).annotate(
        _ord=orden_prioridad
    ).order_by('_ord' if orden == 'desc' else '-_ord', '-creado_en')

    if request.user.rol == 'tec':
        solicitudes = solicitudes.filter(detalle__tecnico=request.user)

    if estado:
        solicitudes = solicitudes.filter(estado=estado)
    if prioridad:
        solicitudes = solicitudes.filter(prioridad=prioridad)
    if q:
        solicitudes = solicitudes.filter(
            Q(cliente__nombre__icontains=q) | Q(cliente__apellido__icontains=q) |
            Q(cliente__dni__icontains=q)
        )

    tecnicos = Usuario.objects.filter(rol='tec')

    page_obj = paginar(request, solicitudes)

    return render(request, 'core/solicitudes/consultar.html', {
        'solicitudes': page_obj,
        'page_obj':    page_obj,
        'tecnicos':    tecnicos,
        'estado':      estado,
        'prioridad':   prioridad,
        'q':           q,
        'orden':       orden,
    })


# ── DETALLE SOLICITUD ──────────────────────────────────────────
@login_required
def detalle_solicitud(request, pk):
    solicitud = get_object_or_404(
        Solicitud.objects.select_related('cliente', 'equipo', 'detalle__tecnico'),
        pk=pk
    )
    # Técnicos solo pueden ver sus propias solicitudes
    if request.user.rol == 'tec':
        detalle = getattr(solicitud, 'detalle', None)
        asignado = detalle.tecnico if detalle else None
        if asignado != request.user:
            messages.error(request, 'No tienes permiso para ver esta solicitud.')
            return redirect('consultar_solicitudes')
    historial = solicitud.historial.select_related('usuario').all()
    avances   = solicitud.avances.select_related('usuario').all()

    ETAPA_ORDEN = ['diagnostico', 'desmontaje', 'reparacion', 'prueba', 'ensamblaje', 'prueba_final']
    ETAPA_LABELS = dict(Avance.ETAPAS)
    avances_dict    = {av.etapa: av for av in avances}
    progreso_etapas = [(k, ETAPA_LABELS.get(k, k), avances_dict.get(k)) for k in ETAPA_ORDEN]
    bitacora_completa = all(avances_dict.get(k) for k in ETAPA_ORDEN)
    seguimiento_url   = request.build_absolute_uri(f'/seguimiento/{solicitud.token_seguimiento}/')

    return render(request, 'core/solicitudes/detalle.html', {
        'solicitud':         solicitud,
        'historial':         historial,
        'progreso_etapas':   progreso_etapas,
        'bitacora_completa': bitacora_completa,
        'seguimiento_url':   seguimiento_url,
    })


# ── CAMBIAR ESTADO ─────────────────────────────────────────────
@login_required
def cambiar_estado(request, pk):
    if request.user.rol not in ['admin', 'tec']:
        return redirect('detalle_solicitud', pk=pk)
    solicitud = get_object_or_404(Solicitud, pk=pk)

    ESTADO_ORDEN = ['pendiente', 'proceso', 'finalizado', 'entregado']
    ESTADO_LABELS = {
        'pendiente':  'Pendiente',
        'proceso':    'En proceso',
        'finalizado': 'Finalizado',
        'entregado':  'Entregado',
    }
    idx_actual = ESTADO_ORDEN.index(solicitud.estado) if solicitud.estado in ESTADO_ORDEN else 0
    estados_siguientes = ESTADO_ORDEN[idx_actual + 1:]
    if request.user.rol == 'tec':
        estados_siguientes = [e for e in estados_siguientes if e != 'entregado']
    choices = [(e, ESTADO_LABELS[e]) for e in estados_siguientes]

    if request.method == 'POST':
        form = CambiarEstadoForm(request.POST)
        form.fields['estado'].choices = choices
        if form.is_valid():
            nuevo_estado = form.cleaned_data['estado']
            if nuevo_estado not in estados_siguientes:
                messages.error(request, 'Estado no válido.')
                return redirect('detalle_solicitud', pk=pk)

            # Verificar técnico asignado antes de pasar a proceso
            if nuevo_estado == 'proceso':
                detalle = getattr(solicitud, 'detalle', None)
                tiene_tecnico = detalle is not None and detalle.tecnico_id is not None
                if not tiene_tecnico:
                    messages.error(
                        request,
                        'Debes asignar un técnico antes de cambiar el estado a "En proceso".'
                    )
                    return redirect('detalle_solicitud', pk=pk)

            # Verificar costo antes de finalizar
            if nuevo_estado == 'finalizado':
                tiene_repuestos = solicitud.repuestos.exists()
                try:
                    tiene_costo = solicitud.costo.mano_obra > 0
                except Exception:
                    tiene_costo = False
                if not tiene_repuestos and not tiene_costo:
                    messages.error(
                        request,
                        'Debes registrar el costo de reparación antes de finalizar la solicitud.'
                    )
                    return render(request, 'core/solicitudes/cambiar_estado.html', {
                        'form':        form,
                        'solicitud':   solicitud,
                        'sin_opciones': False,
                        'error_costo': True,
                    })

            estado_antes     = solicitud.estado
            solicitud.estado = nuevo_estado
            solicitud.save()
            HistorialEstado.objects.create(
                solicitud    = solicitud,
                usuario      = request.user,
                estado_antes = estado_antes,
                estado_nuevo = solicitud.estado,
                observacion  = form.cleaned_data['observacion']
            )
            messages.success(request, 'Estado actualizado correctamente.')
            return redirect('detalle_solicitud', pk=pk)
    else:
        initial = choices[0][0] if choices else solicitud.estado
        form = CambiarEstadoForm(initial={'estado': initial})
        form.fields['estado'].choices = choices

    return render(request, 'core/solicitudes/cambiar_estado.html', {
        'form':        form,
        'solicitud':   solicitud,
        'sin_opciones': not choices,
    })


# ── ASIGNAR TÉCNICO ────────────────────────────────────────────
@login_required
def asignar_tecnico(request, pk):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('detalle_solicitud', pk=pk)

    solicitud = get_object_or_404(Solicitud, pk=pk)

    MAPA_TIPO_ESP = {
        'hardware':   'hardware',
        'software':   'software',
        'preventivo': 'general',
        'revision':   'general',
    }
    esp_ideal = MAPA_TIPO_ESP.get(solicitud.tipo_reparacion, 'general')
    tecnicos  = Usuario.objects.filter(rol='tec')
    # Si hay técnico actual asignado, excluirlo de la lista de reasignación
    try:
        tecnico_actual = solicitud.detalle.tecnico
        if tecnico_actual:
            tecnicos = tecnicos.exclude(pk=tecnico_actual.pk)
    except Exception:
        tecnico_actual = None
    now = timezone.localtime().replace(tzinfo=None)

    tecnicos_libres   = []
    tecnicos_ocupados = []

    for tec in tecnicos:
        activos = Solicitud.objects.filter(
            detalle__tecnico=tec, estado__in=['pendiente', 'proceso']
        ).count()

        if activos == 0:
            tecnicos_libres.append(tec)
        else:
            # Sumar todas las horas estimadas de trabajos activos
            activos_qs = Solicitud.objects.filter(
                detalle__tecnico=tec, estado__in=['pendiente', 'proceso']
            )
            total_horas = float(
                activos_qs.aggregate(h=Sum('tiempo_estimado_horas'))['h'] or Decimal('0')
            )

            fecha_libre     = None
            tiempo_restante = None

            if total_horas > 0:
                fecha_libre   = calcular_fecha_libre_laboral(now, total_horas)
                total_seconds = int(total_horas * 3600)
                h = total_seconds // 3600
                m = (total_seconds % 3600) // 60
                if h >= 48:
                    dias = h // 24
                    tiempo_restante = f'{dias} día{"s" if dias != 1 else ""}'
                elif h >= 1:
                    tiempo_restante = f'{h}h {m}min' if m else f'{h}h'
                else:
                    tiempo_restante = f'{m} min'
            else:
                tiempo_restante = 'Sin estimado'

            tecnicos_ocupados.append({
                'tec':             tec,
                'activos':         activos,
                'proxima':         fecha_libre,
                'tiempo_restante': tiempo_restante,
            })

    tecnicos_ocupados.sort(key=lambda x: (x['proxima'] is None, x['proxima']))

    # Técnico recomendado entre los libres
    recomendado = None
    if tecnicos_libres:
        def puntaje(tec):
            match_esp = 0 if tec.especialidad == esp_ideal else (1 if tec.especialidad == 'general' else 2)
            historico = Solicitud.objects.filter(detalle__tecnico=tec).count()
            return (match_esp, historico)
        recomendado = min(tecnicos_libres, key=puntaje)

    # Lista de espera: solicitudes pendientes sin técnico asignado (excluye la actual)
    lista_espera_clientes = Solicitud.objects.filter(
        estado='pendiente'
    ).filter(
        Q(detalle__isnull=True) | Q(detalle__tecnico__isnull=True)
    ).exclude(pk=pk).select_related('cliente', 'equipo').order_by('creado_en')

    if request.method == 'POST':
        # No permitir asignación si la solicitud ya está finalizada o entregada
        if solicitud.estado in ['finalizado', 'entregado']:
            messages.error(request, 'No se puede asignar técnico a una solicitud finalizada o entregada.')
            return redirect('detalle_solicitud', pk=pk)

        form = AsignarTecnicoForm(request.POST)
        if form.is_valid():
            tec_id  = form.cleaned_data['tecnico'].pk
            tec_obj = Usuario.objects.get(pk=tec_id)
            det, _ = DetalleSolicitud.objects.get_or_create(solicitud=solicitud)
            det.tecnico = tec_obj
            det.save()

            # Recalcular fecha_estimada considerando carga actual del técnico
            horas_actuales = float(
                Solicitud.objects.filter(
                    detalle__tecnico=tec_obj,
                    estado__in=['pendiente', 'proceso']
                ).exclude(pk=solicitud.pk)
                .aggregate(h=Sum('tiempo_estimado_horas'))['h'] or Decimal('0')
            )
            inicio = timezone.localtime().replace(tzinfo=None)
            if horas_actuales > 0:
                inicio = calcular_fecha_libre_laboral(inicio, horas_actuales)
            nueva_fecha = calcular_fecha_libre_laboral(inicio, float(solicitud.tiempo_estimado_horas or 0))
            solicitud.fecha_estimada = nueva_fecha.date()
            solicitud.fecha_hora_estimada = nueva_fecha

            # Solo avanzar a proceso si estaba pendiente; si ya estaba en proceso, mantener
            estado_antes = solicitud.estado
            if solicitud.estado == 'pendiente':
                solicitud.estado = 'proceso'
            solicitud.save()

            HistorialEstado.objects.create(
                solicitud=solicitud, usuario=request.user,
                estado_antes=estado_antes, estado_nuevo=solicitud.estado,
                observacion=f'Técnico asignado: {tec_obj.get_full_name() or tec_obj.username}'
            )
            messages.success(request, f'Técnico {tec_obj.get_full_name() or tec_obj.username} asignado correctamente.')
            return redirect('detalle_solicitud', pk=pk)
    else:
        form = AsignarTecnicoForm()

    # Recomendado entre ocupados: el que se desocupa antes
    recomendado_ocupado = next(
        (item for item in tecnicos_ocupados if item['proxima'] is not None), None
    )

    return render(request, 'core/solicitudes/asignar_tecnico.html', {
        'solicitud':             solicitud,
        'form':                  form,
        'tecnicos_libres':       tecnicos_libres,
        'tecnicos_ocupados':     tecnicos_ocupados,
        'recomendado':           recomendado,
        'recomendado_ocupado':   recomendado_ocupado,
        'esp_ideal':             esp_ideal,
        'hay_libres':            len(tecnicos_libres) > 0,
        'lista_espera_clientes': lista_espera_clientes,
    })

    # ── REGISTRAR USUARIO ──────────────────────────────────────────
@login_required
def registrar_usuario(request):
    if request.user.rol != 'admin':
        return redirect('dashboard')
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario registrado correctamente.')
            return redirect('registrar_usuario')
    else:
        form = UsuarioForm()
    return render(request, 'core/usuarios/registrar.html', {'form': form})

# ── CONSULTAR USUARIO ──────────────────────────────────────────
@login_required
def consultar_usuarios(request):
    if request.user.rol != 'admin':
        return redirect('dashboard')
    query    = request.GET.get('q', '')
    usuarios = Usuario.objects.exclude(pk=request.user.pk).order_by('rol', 'first_name')
    if query:
        usuarios = usuarios.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(username__icontains=query)
        )
    page_obj = paginar(request, usuarios)
    return render(request, 'core/usuarios/consultar.html', {
        'usuarios': page_obj, 'page_obj': page_obj, 'query': query,
    })

# ── ELIMINAR USUARIO ────────────────────────────────────────────
@login_required
def eliminar_usuario(request, pk):
    if request.user.rol != 'admin':
        return redirect('dashboard')

    usuario = get_object_or_404(Usuario, pk=pk)

    if usuario.pk == request.user.pk:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('consultar_usuarios')

    if request.method == 'POST':
        # Verificar si el técnico tiene trabajos en curso asignados
        trabajos_activos = DetalleSolicitud.objects.filter(
            tecnico=usuario,
            solicitud__estado__in=['pendiente', 'proceso']
        ).count()

        if trabajos_activos > 0:
            messages.error(
                request,
                f'No se puede eliminar a "{usuario.get_full_name() or usuario.username}" '
                f'porque tiene {trabajos_activos} solicitud(es) activa(s) asignada(s). '
                f'Reasigna esos trabajos a otro técnico antes de eliminarlo, '
                f'o desactiva su cuenta en su lugar.'
            )
            return redirect('consultar_usuarios')

        nombre = usuario.get_full_name() or usuario.username
        usuario.delete()
        messages.success(request, f'Usuario "{nombre}" eliminado correctamente.')
        return redirect('consultar_usuarios')

    return redirect('consultar_usuarios')

    # ── DIAGNÓSTICO ────────────────────────────────────────────────
@login_required
def diagnostico(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if not tecnico_asignado_o_staff(request.user, solicitud):
        messages.error(request, 'No tienes permiso para editar esta solicitud.')
        return redirect('detalle_solicitud', pk=pk)
    if solicitud.estado in ['finalizado', 'entregado']:
        messages.error(request, 'No se puede editar el diagnóstico de una solicitud finalizada.')
        return redirect('detalle_solicitud', pk=pk)
    detalle, _ = DetalleSolicitud.objects.get_or_create(solicitud=solicitud)
    if request.method == 'POST':
        form = DiagnosticoForm(request.POST, instance=detalle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Diagnóstico guardado correctamente.')
            return redirect('detalle_solicitud', pk=pk)
    else:
        form = DiagnosticoForm(instance=detalle)
    return render(request, 'core/solicitudes/diagnostico.html', {
        'form':      form,
        'solicitud': solicitud,
    })

    # ── AVANCE / BITÁCORA ──────────────────────────────────────────
@login_required
def avance(request, pk):
    ETAPA_ORDEN = ['diagnostico', 'desmontaje', 'reparacion', 'prueba', 'ensamblaje', 'prueba_final']
    ETAPA_LABELS = dict(Avance.ETAPAS)

    solicitud = get_object_or_404(Solicitud, pk=pk)
    if not tecnico_asignado_o_staff(request.user, solicitud):
        messages.error(request, 'No tienes permiso para editar esta solicitud.')
        return redirect('detalle_solicitud', pk=pk)
    if solicitud.estado in ['finalizado', 'entregado']:
        messages.error(request, 'No se pueden registrar avances en una solicitud finalizada.')
        return redirect('detalle_solicitud', pk=pk)
    avances   = solicitud.avances.select_related('usuario').all()

    ultimo_avance = avances.last()
    if ultimo_avance and ultimo_avance.etapa in ETAPA_ORDEN:
        idx_ultimo = ETAPA_ORDEN.index(ultimo_avance.etapa)
        etapas_disponibles = ETAPA_ORDEN[idx_ultimo + 1:]
    else:
        etapas_disponibles = list(ETAPA_ORDEN)

    choices = [('', '---------')] + [(e, ETAPA_LABELS.get(e, e)) for e in etapas_disponibles]

    if request.method == 'POST' and request.POST.get('form_type') == 'nota':
        form = AvanceForm()
        form.fields['etapa'].choices = choices
        nota_form = NotaBitacoraForm(request.POST)
        if nota_form.is_valid():
            nota           = nota_form.save(commit=False)
            nota.solicitud = solicitud
            nota.usuario   = request.user
            nota.tipo      = 'nota'
            nota.etapa     = ''
            nota.save()
            messages.success(request, 'Nota registrada correctamente.')
            return redirect('avance', pk=pk)
    elif request.method == 'POST':
        form = AvanceForm(request.POST)
        form.fields['etapa'].choices = choices
        nota_form = NotaBitacoraForm()
        if form.is_valid():
            if form.cleaned_data['etapa'] not in etapas_disponibles:
                messages.error(request, 'Esa etapa no está disponible.')
                return redirect('avance', pk=pk)
            av           = form.save(commit=False)
            av.solicitud = solicitud
            av.usuario   = request.user
            av.tipo      = 'etapa'
            av.save()
            messages.success(request, 'Avance registrado correctamente.')
            return redirect('avance', pk=pk)
    else:
        form = AvanceForm()
        form.fields['etapa'].choices = choices
        nota_form = NotaBitacoraForm()

    return render(request, 'core/solicitudes/avance.html', {
        'form':        form,
        'nota_form':   nota_form,
        'solicitud':   solicitud,
        'avances':     avances,
        'sin_etapas':  not etapas_disponibles,
    })

    # ── REPUESTOS ──────────────────────────────────────────────────
@login_required
def repuestos(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    repuestos = solicitud.repuestos.all()
    if request.method == 'POST':
        if not tecnico_asignado_o_staff(request.user, solicitud):
            messages.error(request, 'No tienes permiso.')
            return redirect('detalle_solicitud', pk=pk)
        form_rep = RepuestoForm(request.POST)
        if form_rep.is_valid():
            rep = form_rep.save(commit=False)
            rep.solicitud = solicitud
            rep.save()
            costo, _ = Costo.objects.get_or_create(
                solicitud=solicitud, defaults={'mano_obra': 0}
            )
            costo.calcular_total()
            messages.success(request, 'Repuesto agregado correctamente.')
        else:
            for campo, errores in form_rep.errors.items():
                for e in errores:
                    messages.error(request, f'{campo}: {e}')
        return redirect('repuestos', pk=pk)
    return render(request, 'core/solicitudes/repuestos.html', {
        'solicitud': solicitud,
        'repuestos': repuestos,
    })


# ── COSTOS ─────────────────────────────────────────────────────
@login_required
def costos(request, pk):
    solicitud    = get_object_or_404(Solicitud, pk=pk)
    repuestos    = solicitud.repuestos.all()
    costo, _     = Costo.objects.get_or_create(
        solicitud=solicitud, defaults={'mano_obra': 0}
    )
    if request.method == 'POST':
        if not tecnico_asignado_o_staff(request.user, solicitud):
            messages.error(request, 'No tienes permiso.')
            return redirect('detalle_solicitud', pk=pk)
        form_costo = CostoForm(request.POST, instance=costo)
        if form_costo.is_valid():
            form_costo.save()
            costo.calcular_total()
            messages.success(request, 'Costo actualizado.')
        else:
            for campo, errores in form_costo.errors.items():
                for e in errores:
                    messages.error(request, f'{campo}: {e}')
        return redirect('costos', pk=pk)
    return render(request, 'core/solicitudes/costos.html', {
        'solicitud': solicitud,
        'repuestos': repuestos,
        'costo':     costo,
    })

    # ── REPORTES — ÍNDICE ──────────────────────────────────────────
@login_required
def reportes(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')
    return render(request, 'core/reportes/index.html', {})


# ── REPORTE SOLICITUDES ────────────────────────────────────────
@login_required
def reporte_solicitudes(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')

    # ── Filtros de fecha ──
    fi, ff, fecha_inicio_str, fecha_fin_str, error_fecha = parsear_rango_fechas(request)

    qs = filtrar_por_rango(Solicitud.objects.all(), 'fecha_ingreso', fi, ff)

    por_estado = dict(
        qs.values('estado')
        .annotate(n=Count('id'))
        .values_list('estado', 'n')
    )
    total = sum(por_estado.values())
    estados = {
        'pendiente':  por_estado.get('pendiente', 0),
        'proceso':    por_estado.get('proceso', 0),
        'finalizado': por_estado.get('finalizado', 0),
        'entregado':  por_estado.get('entregado', 0),
    }

    tipos = {}
    for t, label in Solicitud.TIPOS_REP:
        tipos[label] = qs.filter(tipo_reparacion=t).count()

    por_tecnico = []
    for tec in Usuario.objects.filter(rol='tec'):
        cant = DetalleSolicitud.objects.filter(tecnico=tec, solicitud__in=qs).count()
        por_tecnico.append({
            'nombre':   tec.get_full_name() or tec.username,
            'cantidad': cant,
        })

    # Solicitudes por mes — últimos 6 meses
    hoy = timezone.localdate()
    meses_labels = []
    meses_data   = []
    for i in range(5, -1, -1):
        year  = hoy.year
        month = hoy.month - i
        while month <= 0:
            month += 12
            year  -= 1
        count = qs.filter(fecha_ingreso__year=year, fecha_ingreso__month=month).count()
        meses_labels.append(datetime.date(year, month, 1).strftime('%b %Y'))
        meses_data.append(count)

    # Marca más reparada
    marca_top = (Equipo.objects
                 .filter(solicitudes__in=qs)
                 .values('marca')
                 .annotate(total=Count('solicitudes'))
                 .order_by('-total')
                 .first())

    resueltas = estados['finalizado'] + estados['entregado']
    tasa = round((resueltas / total * 100), 1) if total else 0

    recientes = qs.select_related('cliente', 'equipo', 'detalle__tecnico').order_by('-creado_en')[:10]

    return render(request, 'core/reportes/solicitudes.html', {
        'total':             total,
        'estados':           estados,
        'tipos':             tipos,
        'por_tecnico':       por_tecnico,
        'recientes':         recientes,
        'meses_labels':      json.dumps(meses_labels),
        'meses_data':        json.dumps(meses_data),
        'marca_top':         marca_top,
        'tasa':              tasa,
        'resueltas':         resueltas,
        'fecha_inicio_str':  fecha_inicio_str,
        'fecha_fin_str':     fecha_fin_str,
        'error_fecha':       error_fecha,
        'sin_datos':         total == 0 and (fi or ff),
    })


# ── REPORTE TIEMPOS ────────────────────────────────────────────
@login_required
def reporte_tiempos(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')

    # ── Filtros de fecha ──
    fi, ff, fecha_inicio_str, fecha_fin_str, error_fecha = parsear_rango_fechas(request)

    qs = filtrar_por_rango(Solicitud.objects.all(), 'fecha_ingreso', fi, ff)

    tiempos_por_tipo = {}
    for t, label in Solicitud.TIPOS_REP:
        sols = qs.filter(tipo_reparacion=t)
        agg = sols.filter(tiempo_estimado_horas__isnull=False).aggregate(
            total=Sum('tiempo_estimado_horas'),
            promedio=Avg('tiempo_estimado_horas')
        )
        tiempos_por_tipo[label] = {
            'cantidad':    sols.count(),
            'promedio':    round(float(agg['promedio'] or 0), 1),
            'total_horas': round(float(agg['total'] or 0), 1),
        }

    agg_general = qs.filter(tiempo_estimado_horas__isnull=False).aggregate(
        total=Sum('tiempo_estimado_horas'),
        promedio=Avg('tiempo_estimado_horas')
    )
    total_horas_acum = round(float(agg_general['total'] or 0), 1)
    promedio_general = round(float(agg_general['promedio'] or 0), 1)

    tipos_con_datos = {k: v for k, v in tiempos_por_tipo.items() if v['promedio'] > 0}
    tipo_rapido = min(tipos_con_datos.items(), key=lambda x: x[1]['promedio'])[0] if tipos_con_datos else '—'
    tipo_lento  = max(tipos_con_datos.items(), key=lambda x: x[1]['promedio'])[0] if tipos_con_datos else '—'

    tiempos_prioridad = {}
    for p, label in Solicitud.PRIORIDADES:
        agg_p = qs.filter(prioridad=p, tiempo_estimado_horas__isnull=False).aggregate(
            promedio=Avg('tiempo_estimado_horas')
        )
        tiempos_prioridad[label] = round(float(agg_p['promedio'] or 0), 1)

    return render(request, 'core/reportes/tiempos.html', {
        'tiempos_por_tipo':  tiempos_por_tipo,
        'promedio_general':  promedio_general,
        'total_solicitudes': qs.count(),
        'total_horas_acum':  total_horas_acum,
        'tipo_rapido':       tipo_rapido,
        'tipo_lento':        tipo_lento,
        'chart_labels':      json.dumps(list(tiempos_por_tipo.keys())),
        'chart_promedios':   json.dumps([v['promedio']    for v in tiempos_por_tipo.values()]),
        'chart_totales':     json.dumps([v['total_horas'] for v in tiempos_por_tipo.values()]),
        'chart_cantidad':    json.dumps([v['cantidad']    for v in tiempos_por_tipo.values()]),
        'tiempos_prioridad': json.dumps(tiempos_prioridad),
        'prioridad_labels':  json.dumps(list(tiempos_prioridad.keys())),
        'fecha_inicio_str':  fecha_inicio_str,
        'fecha_fin_str':     fecha_fin_str,
        'error_fecha':       error_fecha,
        'sin_datos':         qs.count() == 0 and (fi or ff),
    })

# ── REPORTE INGRESOS ───────────────────────────────────────────
@login_required
def reporte_ingresos(request):
    if request.user.rol != 'admin':
        return redirect('dashboard')

    # ── Filtros de fecha ──
    fi, ff, fecha_inicio_str, fecha_fin_str, error_fecha = parsear_rango_fechas(request)

    costos_qs = Costo.objects.select_related('solicitud__cliente', 'solicitud__equipo').all()
    costos_qs = filtrar_por_rango(costos_qs, 'solicitud__fecha_ingreso', fi, ff)

    agg = costos_qs.aggregate(
        total_ingresos=Sum('total'),
        total_mano_obra=Sum('mano_obra'),
    )
    total_ingresos  = agg['total_ingresos']  or Decimal('0')
    total_mano_obra = agg['total_mano_obra'] or Decimal('0')
    total_repuestos = total_ingresos - total_mano_obra
    ticket_promedio = round(total_ingresos / costos_qs.count(), 2) if costos_qs.count() else 0

    # Ingresos por mes — últimos 6 meses
    hoy = timezone.localdate()
    meses_labels   = []
    meses_ingresos = []
    meses_mano     = []
    for i in range(5, -1, -1):
        year  = hoy.year
        month = hoy.month - i
        while month <= 0:
            month += 12; year -= 1
        agg_mes = costos_qs.filter(
            solicitud__fecha_ingreso__year=year,
            solicitud__fecha_ingreso__month=month
        ).aggregate(total=Sum('total'), mano=Sum('mano_obra'))
        meses_labels.append(datetime.date(year, month, 1).strftime('%b %Y'))
        meses_ingresos.append(float(agg_mes['total'] or 0))
        meses_mano.append(float(agg_mes['mano'] or 0))

    # Ingresos por tipo de reparación
    ingresos_tipo = {}
    for t, label in Solicitud.TIPOS_REP:
        agg_t = costos_qs.filter(solicitud__tipo_reparacion=t).aggregate(total=Sum('total'))
        ingresos_tipo[label] = float(agg_t['total'] or 0)

    # Ingresos por técnico
    tec_ingresos = []
    for tec in Usuario.objects.filter(rol='tec'):
        agg_tec = costos_qs.filter(solicitud__detalle__tecnico=tec).aggregate(total=Sum('total'))
        tec_ingresos.append({'nombre': tec.get_full_name() or tec.username,
                             'total': float(agg_tec['total'] or 0)})
    tec_ingresos.sort(key=lambda x: x['total'], reverse=True)

    ultimos = costos_qs.order_by('-solicitud__creado_en')[:10]

    return render(request, 'core/reportes/ingresos.html', {
        'total_ingresos':       total_ingresos,
        'total_mano_obra':      total_mano_obra,
        'total_repuestos':      total_repuestos,
        'ticket_promedio':      ticket_promedio,
        'total_registros':      costos_qs.count(),
        'ultimos':              ultimos,
        'tec_ingresos':         tec_ingresos,
        'meses_labels':         json.dumps(meses_labels),
        'meses_ingresos':       json.dumps(meses_ingresos),
        'meses_mano':           json.dumps(meses_mano),
        'ingresos_tipo_labels': json.dumps(list(ingresos_tipo.keys())),
        'ingresos_tipo_data':   json.dumps(list(ingresos_tipo.values())),
        'tec_labels':           json.dumps([t['nombre'] for t in tec_ingresos]),
        'tec_data':             json.dumps([t['total']  for t in tec_ingresos]),
        'fecha_inicio_str':     fecha_inicio_str,
        'fecha_fin_str':        fecha_fin_str,
        'error_fecha':          error_fecha,
        'sin_datos':            costos_qs.count() == 0 and (fi or ff),
    })

    # ── PDF REPORTE SOLICITUDES ────────────────────────────────────
@login_required
def reporte_solicitudes_pdf(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import io

    fecha_inicio, fecha_fin, fecha_inicio_str, fecha_fin_str, error_fecha = parsear_rango_fechas(request)

    qs = filtrar_por_rango(Solicitud.objects.all(), 'fecha_ingreso', fecha_inicio, fecha_fin)

    total = qs.count()
    estados = {
        'Pendiente':  qs.filter(estado='pendiente').count(),
        'En proceso': qs.filter(estado='proceso').count(),
        'Finalizado': qs.filter(estado='finalizado').count(),
        'Entregado':  qs.filter(estado='entregado').count(),
    }
    tipos = {label: qs.filter(tipo_reparacion=t).count() for t, label in Solicitud.TIPOS_REP}
    por_tecnico = [
        (tec.get_full_name() or tec.username,
         DetalleSolicitud.objects.filter(tecnico=tec, solicitud__in=qs).count())
        for tec in Usuario.objects.filter(rol='tec')
    ]
    resueltas = estados['Finalizado'] + estados['Entregado']
    tasa = round((resueltas / total * 100), 1) if total else 0

    AZUL = colors.HexColor('#1F3864')
    LIGHT = colors.HexColor('#EBF3FB')
    GRIS  = colors.HexColor('#f5f5f5')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    titulo_s  = ParagraphStyle('t', fontSize=16, textColor=AZUL, fontName='Helvetica-Bold')
    subtit_s  = ParagraphStyle('s', fontSize=9,  textColor=colors.grey, fontName='Helvetica')
    seccion_s = ParagraphStyle('sec', fontSize=8, textColor=colors.grey,
                               fontName='Helvetica-Bold', spaceAfter=4)
    W = 17*cm

    def tabla(data, col_widths, header=True):
        t = Table(data, colWidths=col_widths)
        style = [
            ('FONTNAME',  (0,0), (-1,0 if header else -1), 'Helvetica-Bold'),
            ('FONTSIZE',  (0,0), (-1,-1), 8),
            ('BACKGROUND',(0,0), (-1,0), AZUL if header else GRIS),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white if header else colors.black),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, GRIS]),
            ('GRID',      (0,0), (-1,-1), 0.4, colors.HexColor('#CCCCCC')),
            ('ALIGN',     (0,0), (-1,-1), 'LEFT'),
            ('VALIGN',    (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',(0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]
        t.setStyle(TableStyle(style))
        return t

    periodo = ''
    if fecha_inicio and fecha_fin:
        periodo = f' | Período: {fecha_inicio.strftime("%d/%m/%Y")} — {fecha_fin.strftime("%d/%m/%Y")}'
    elif fecha_inicio:
        periodo = f' | Desde: {fecha_inicio.strftime("%d/%m/%Y")}'
    elif fecha_fin:
        periodo = f' | Hasta: {fecha_fin.strftime("%d/%m/%Y")}'

    story = [
        Paragraph('TechRepair — Reporte de Solicitudes', titulo_s),
        Paragraph(f'Generado el {timezone.localdate().strftime("%d/%m/%Y")}{periodo}', subtit_s),
        Spacer(1, 0.4*cm),
        Paragraph('RESUMEN GENERAL', seccion_s),
        tabla([['Total solicitudes', 'Resueltas', 'Tasa de resolución'],
               [total, resueltas, f'{tasa}%']], [W/3]*3),
        Spacer(1, 0.3*cm),
        Paragraph('POR ESTADO', seccion_s),
        tabla([['Estado', 'Cantidad']] + list(estados.items()), [W*0.6, W*0.4]),
        Spacer(1, 0.3*cm),
        Paragraph('POR TIPO DE REPARACIÓN', seccion_s),
        tabla([['Tipo', 'Cantidad']] + list(tipos.items()), [W*0.6, W*0.4]),
    ]
    if por_tecnico:
        story += [
            Spacer(1, 0.3*cm),
            Paragraph('POR TÉCNICO', seccion_s),
            tabla([['Técnico', 'Solicitudes']] + por_tecnico, [W*0.6, W*0.4]),
        ]

    if total == 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('No hay solicitudes en el período seleccionado.', subtit_s))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_solicitudes.pdf"'
    return response


# ── PDF REPORTE TIEMPOS ────────────────────────────────────────
@login_required
def reporte_tiempos_pdf(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    import io

    fecha_inicio, fecha_fin, fecha_inicio_str, fecha_fin_str, error_fecha = parsear_rango_fechas(request)

    qs = filtrar_por_rango(Solicitud.objects.all(), 'fecha_ingreso', fecha_inicio, fecha_fin)

    tiempos_por_tipo = {}
    for t, label in Solicitud.TIPOS_REP:
        sols = qs.filter(tipo_reparacion=t)
        agg = sols.filter(tiempo_estimado_horas__isnull=False).aggregate(
            total=Sum('tiempo_estimado_horas'), promedio=Avg('tiempo_estimado_horas'))
        tiempos_por_tipo[label] = {
            'cantidad':    sols.count(),
            'promedio':    round(float(agg['promedio'] or 0), 1),
            'total_horas': round(float(agg['total'] or 0), 1),
        }

    agg_gen = qs.filter(tiempo_estimado_horas__isnull=False).aggregate(
        total=Sum('tiempo_estimado_horas'), promedio=Avg('tiempo_estimado_horas'))
    promedio_general = round(float(agg_gen['promedio'] or 0), 1)
    total_horas_acum = round(float(agg_gen['total'] or 0), 1)

    AZUL = colors.HexColor('#1F3864')
    GRIS = colors.HexColor('#f5f5f5')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    titulo_s  = ParagraphStyle('t', fontSize=16, textColor=AZUL, fontName='Helvetica-Bold')
    subtit_s  = ParagraphStyle('s', fontSize=9,  textColor=colors.grey, fontName='Helvetica')
    seccion_s = ParagraphStyle('sec', fontSize=8, textColor=colors.grey,
                               fontName='Helvetica-Bold', spaceAfter=4)
    W = 17*cm

    def tabla(data, col_widths):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 8),
            ('BACKGROUND',   (0,0), (-1,0),  AZUL),
            ('TEXTCOLOR',    (0,0), (-1,0),  colors.white),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, GRIS]),
            ('GRID',         (0,0), (-1,-1), 0.4, colors.HexColor('#CCCCCC')),
            ('ALIGN',        (1,0), (-1,-1), 'CENTER'),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',   (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]))
        return t

    periodo = ''
    if fecha_inicio and fecha_fin:
        periodo = f' | Período: {fecha_inicio.strftime("%d/%m/%Y")} — {fecha_fin.strftime("%d/%m/%Y")}'
    elif fecha_inicio:
        periodo = f' | Desde: {fecha_inicio.strftime("%d/%m/%Y")}'
    elif fecha_fin:
        periodo = f' | Hasta: {fecha_fin.strftime("%d/%m/%Y")}'

    rows = [['Tipo de reparación', 'Solicitudes', 'Prom. horas', 'Total horas']]
    for label, v in tiempos_por_tipo.items():
        rows.append([label, v['cantidad'], f"{v['promedio']}h", f"{v['total_horas']}h"])

    story = [
        Paragraph('TechRepair — Reporte de Tiempos de Reparación', titulo_s),
        Paragraph(f'Generado el {timezone.localdate().strftime("%d/%m/%Y")}{periodo}', subtit_s),
        Spacer(1, 0.4*cm),
        Paragraph('RESUMEN GENERAL', seccion_s),
        tabla([['Total solicitudes', 'Promedio general', 'Total horas acum.'],
               [qs.count(), f'{promedio_general}h', f'{total_horas_acum}h']], [W/3]*3),
        Spacer(1, 0.3*cm),
        Paragraph('TIEMPOS POR TIPO DE REPARACIÓN', seccion_s),
        tabla(rows, [W*0.4, W*0.2, W*0.2, W*0.2]),
    ]

    if qs.count() == 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('Sin datos finalizados en el período.', subtit_s))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_tiempos.pdf"'
    return response


# ── PDF REPORTE INGRESOS ───────────────────────────────────────
@login_required
def reporte_ingresos_pdf(request):
    if request.user.rol != 'admin':
        return redirect('dashboard')

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    import io

    fecha_inicio, fecha_fin, fecha_inicio_str, fecha_fin_str, error_fecha = parsear_rango_fechas(request)

    costos_qs = Costo.objects.select_related(
        'solicitud__cliente', 'solicitud__equipo', 'solicitud__detalle__tecnico'
    ).all()
    costos_qs = filtrar_por_rango(costos_qs, 'solicitud__fecha_ingreso', fecha_inicio, fecha_fin)

    total_ingresos  = sum(c.total     for c in costos_qs)
    total_mano_obra = sum(c.mano_obra for c in costos_qs)
    total_repuestos = total_ingresos - total_mano_obra
    ticket_promedio = round(total_ingresos / costos_qs.count(), 2) if costos_qs.count() else 0

    ingresos_tipo = {
        label: float(sum(c.total for c in costos_qs.filter(solicitud__tipo_reparacion=t)))
        for t, label in Solicitud.TIPOS_REP
    }
    tec_ingresos = sorted([
        (tec.get_full_name() or tec.username,
         float(sum(c.total for c in costos_qs.filter(solicitud__detalle__tecnico=tec))))
        for tec in Usuario.objects.filter(rol='tec')
    ], key=lambda x: x[1], reverse=True)

    AZUL  = colors.HexColor('#1F3864')
    GRIS  = colors.HexColor('#f5f5f5')
    LIGHT = colors.HexColor('#EBF3FB')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    titulo_s  = ParagraphStyle('t', fontSize=16, textColor=AZUL, fontName='Helvetica-Bold')
    subtit_s  = ParagraphStyle('s', fontSize=9,  textColor=colors.grey, fontName='Helvetica')
    seccion_s = ParagraphStyle('sec', fontSize=8, textColor=colors.grey,
                               fontName='Helvetica-Bold', spaceAfter=4)
    W = 17*cm

    def tabla(data, col_widths, align_right_cols=None):
        t = Table(data, colWidths=col_widths)
        style = [
            ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0,0), (-1,-1), 8),
            ('BACKGROUND',   (0,0), (-1,0),  AZUL),
            ('TEXTCOLOR',    (0,0), (-1,0),  colors.white),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [colors.white, GRIS]),
            ('GRID',         (0,0), (-1,-1), 0.4, colors.HexColor('#CCCCCC')),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',   (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ]
        if align_right_cols:
            for col in align_right_cols:
                style.append(('ALIGN', (col,0), (col,-1), 'RIGHT'))
        t.setStyle(TableStyle(style))
        return t

    periodo = ''
    if fecha_inicio and fecha_fin:
        periodo = f' | Período: {fecha_inicio.strftime("%d/%m/%Y")} — {fecha_fin.strftime("%d/%m/%Y")}'
    elif fecha_inicio:
        periodo = f' | Desde: {fecha_inicio.strftime("%d/%m/%Y")}'
    elif fecha_fin:
        periodo = f' | Hasta: {fecha_fin.strftime("%d/%m/%Y")}'

    story = [
        Paragraph('TechRepair — Reporte de Ingresos', titulo_s),
        Paragraph(f'Generado el {timezone.localdate().strftime("%d/%m/%Y")}{periodo}', subtit_s),
        Spacer(1, 0.4*cm),
        Paragraph('RESUMEN DE INGRESOS', seccion_s),
        tabla([
            ['Total ingresos', 'Mano de obra', 'Repuestos', 'Ticket promedio'],
            [f'S/ {total_ingresos:.2f}', f'S/ {total_mano_obra:.2f}',
             f'S/ {total_repuestos:.2f}', f'S/ {ticket_promedio:.2f}'],
        ], [W/4]*4, align_right_cols=[0,1,2,3]),
        Spacer(1, 0.3*cm),
        Paragraph('INGRESOS POR TIPO DE REPARACIÓN', seccion_s),
        tabla(
            [['Tipo', 'Total (S/)']] + [[k, f'S/ {v:.2f}'] for k,v in ingresos_tipo.items()],
            [W*0.6, W*0.4], align_right_cols=[1]
        ),
    ]

    if tec_ingresos:
        story += [
            Spacer(1, 0.3*cm),
            Paragraph('INGRESOS POR TÉCNICO', seccion_s),
            tabla(
                [['Técnico', 'Total generado (S/)']] +
                [[n, f'S/ {v:.2f}'] for n,v in tec_ingresos],
                [W*0.6, W*0.4], align_right_cols=[1]
            ),
        ]

    if costos_qs.count() == 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('Sin ingresos en el período seleccionado.', subtit_s))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_ingresos.pdf"'
    return response


    # ── API: EQUIPOS POR CLIENTE ───────────────────────────────────
@login_required
def equipos_por_cliente(request, cliente_id):
    equipos = Equipo.objects.filter(cliente_id=cliente_id).values(
        'id', 'tipo', 'marca', 'modelo', 'serie'
    )
    TIPO_LABELS = dict(Equipo.TIPOS)
    data = []
    for e in equipos:
        tipo_label = TIPO_LABELS.get(e['tipo'], e['tipo'])
        data.append({
            'id':    e['id'],
            'texto': f"{tipo_label} — {e['marca'].upper()} {e['modelo']} — Serie: {e['serie']}"
        })
    return JsonResponse({'equipos': data})


# ── SEGUIMIENTO PÚBLICO ────────────────────────────────────────
def seguimiento(request, token):
    solicitud = get_object_or_404(
        Solicitud.objects.select_related('cliente', 'equipo', 'detalle__tecnico'),
        token_seguimiento=token
    )

    avances = solicitud.avances.select_related('usuario').all()

    ETAPA_ORDEN = ['diagnostico', 'desmontaje', 'reparacion', 'prueba', 'ensamblaje', 'prueba_final']
    ETAPA_LABELS = dict(Avance.ETAPAS)
    avances_dict    = {av.etapa: av for av in avances}
    progreso_etapas = [(k, ETAPA_LABELS.get(k, k), avances_dict.get(k)) for k in ETAPA_ORDEN]

    # Línea de tiempo combinada: etapas completadas + notas visibles para el cliente,
    # ordenadas cronológicamente. Las etapas pendientes se muestran al final.
    timeline = []
    for k, label, av in progreso_etapas:
        if av:
            timeline.append({'tipo': 'etapa', 'label': label, 'fecha': av.fecha_hora, 'av': av})
    for nota in avances:
        if nota.tipo == 'nota' and nota.visible_cliente:
            timeline.append({'tipo': 'nota', 'label': 'Nota del taller', 'fecha': nota.fecha_hora, 'av': nota})
    timeline.sort(key=lambda x: x['fecha'])

    pendientes = [{'tipo': 'etapa', 'label': label, 'fecha': None, 'av': None}
                   for k, label, av in progreso_etapas if not av]

    timeline_completa = timeline + pendientes

    return render(request, 'core/solicitudes/seguimiento.html', {
        'solicitud':       solicitud,
        'progreso_etapas': progreso_etapas,
        'timeline':        timeline_completa,
    })


# ── ENTREGA DE EQUIPO ──────────────────────────────────────────
@login_required
def entrega(request, pk):
    solicitud = get_object_or_404(
        Solicitud.objects.select_related('cliente', 'equipo', 'detalle__tecnico'),
        pk=pk
    )
    try:
        costo = solicitud.costo
    except Costo.DoesNotExist:
        costo = None
    repuestos = solicitud.repuestos.all()

    if request.method == 'POST':
        if solicitud.estado == 'entregado':
            messages.error(request, 'Esta solicitud ya fue entregada.')
            return redirect('detalle_solicitud', pk=pk)
        if solicitud.estado != 'finalizado':
            messages.error(request, 'Solo se puede registrar la entrega de una solicitud finalizada.')
            return redirect('detalle_solicitud', pk=pk)
        confirmacion = request.POST.get('confirmacion') == 'on'
        observaciones = request.POST.get('observaciones', '')
        solicitud.fecha_entrega         = timezone.localdate()
        solicitud.hora_entrega          = timezone.localtime().time()
        solicitud.confirmacion_cliente  = confirmacion
        solicitud.observaciones_entrega = observaciones
        solicitud.estado                = 'entregado'
        solicitud.save()
        HistorialEstado.objects.create(
            solicitud    = solicitud,
            usuario      = request.user,
            estado_antes = 'finalizado',
            estado_nuevo = 'entregado',
            observacion  = f'Equipo entregado al cliente. {observaciones}'
        )
        messages.success(request, f'Equipo entregado correctamente al cliente {solicitud.cliente.nombre}.')
        return redirect('detalle_solicitud', pk=pk)

    return render(request, 'core/solicitudes/entrega.html', {
        'solicitud': solicitud,
        'costo':     costo,
        'repuestos': repuestos,
        'hoy':       timezone.localdate(),
        'ahora':     timezone.localtime().strftime('%H:%M'),
    })


# ── INFORME PDF ────────────────────────────────────────────────
@login_required
def informe_pdf(request, pk):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import io

    solicitud = get_object_or_404(
        Solicitud.objects.select_related('cliente', 'equipo', 'detalle__tecnico'),
        pk=pk
    )

    try:
        costo = solicitud.costo
    except Costo.DoesNotExist:
        costo = None
    detalle = getattr(solicitud, 'detalle', None)

    repuestos = solicitud.repuestos.all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    AZUL  = colors.HexColor('#1F3864')
    TEAL  = colors.HexColor('#00c9a7')
    GRIS  = colors.HexColor('#f5f5f5')
    GRIS2 = colors.HexColor('#e0e0e0')

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('titulo', fontSize=20, textColor=AZUL,
                                  fontName='Helvetica-Bold', alignment=TA_LEFT)
    label_style = ParagraphStyle('label', fontSize=7, textColor=colors.grey,
                                 fontName='Helvetica', leading=10)
    valor_style = ParagraphStyle('valor', fontSize=10, textColor=colors.HexColor('#222222'),
                                 fontName='Helvetica-Bold', leading=14)
    normal_style = ParagraphStyle('normal', fontSize=9, textColor=colors.HexColor('#333333'),
                                  fontName='Helvetica', leading=13)
    seccion_style = ParagraphStyle('seccion', fontSize=7, textColor=colors.grey,
                                   fontName='Helvetica-Bold', letterSpacing=1.5)

    story = []
    W = 17*cm

    # ENCABEZADO
    header_data = [[
        Paragraph('<b><font color="#1F3864" size="16">TechRepair</font></b><br/>'
                  '<font color="grey" size="8">Taller de Reparacion de Equipos · Lima, Peru</font>', styles['Normal']),
        Paragraph(f'<font color="grey" size="8">N de servicio</font><br/>'
                  f'<b><font color="#1F3864" size="16">#S-{solicitud.id:03d}</font></b>',
                  ParagraphStyle('r', alignment=TA_RIGHT))
    ]]
    header_table = Table(header_data, colWidths=[W*0.6, W*0.4])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,0), 1.5, AZUL),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.4*cm))

    # DATOS CLIENTE Y EQUIPO
    def campo(label, valor):
        return [Paragraph(label.upper(), label_style),
                Paragraph(str(valor) if valor else '--', valor_style)]

    fecha_entrega_str = (solicitud.fecha_entrega.strftime('%d/%m/%Y')
                         if solicitud.fecha_entrega
                         else timezone.localdate().strftime('%d/%m/%Y'))

    datos = Table([
        [campo('Cliente', solicitud.cliente.nombre),
         campo('DNI', solicitud.cliente.dni)],
        [campo('Equipo', f'{solicitud.equipo.get_marca_display()} {solicitud.equipo.modelo}'),
         campo('N de serie', solicitud.equipo.serie)],
        [campo('Fecha de ingreso', solicitud.fecha_ingreso.strftime('%d/%m/%Y')),
         campo('Fecha de entrega', fecha_entrega_str)],
    ], colWidths=[W*0.5, W*0.5])
    datos.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [GRIS, colors.white]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, GRIS2),
        ('BOX', (0,0), (-1,-1), 0.5, GRIS2),
    ]))
    story.append(datos)
    story.append(Spacer(1, 0.5*cm))

    # DIAGNOSTICO
    if detalle and detalle.diagnostico:
        story.append(Paragraph('DIAGNOSTICO', seccion_style))
        story.append(HRFlowable(width=W, thickness=0.5, color=GRIS2, spaceAfter=4))
        story.append(Paragraph(detalle.diagnostico, normal_style))
        story.append(Spacer(1, 0.3*cm))

    if detalle and detalle.trabajo_realizado:
        story.append(Paragraph('TRABAJO REALIZADO', seccion_style))
        story.append(HRFlowable(width=W, thickness=0.5, color=GRIS2, spaceAfter=4))
        story.append(Paragraph(detalle.trabajo_realizado, normal_style))
        story.append(Spacer(1, 0.3*cm))

    if detalle and detalle.recomendaciones:
        story.append(Paragraph('RECOMENDACIONES', seccion_style))
        story.append(HRFlowable(width=W, thickness=0.5, color=GRIS2, spaceAfter=4))
        story.append(Paragraph(detalle.recomendaciones, normal_style))
        story.append(Spacer(1, 0.4*cm))

    # COSTOS
    story.append(Paragraph('DETALLE DE COSTOS', seccion_style))
    story.append(HRFlowable(width=W, thickness=0.5, color=GRIS2, spaceAfter=4))

    filas_costo = []
    if costo:
        filas_costo.append([
            Paragraph('Mano de obra', normal_style),
            Paragraph(f'S/. {costo.mano_obra:.2f}',
                      ParagraphStyle('r', alignment=TA_RIGHT, fontSize=9, fontName='Helvetica'))
        ])
    for rep in repuestos:
        filas_costo.append([
            Paragraph(f'{rep.nombre} x{rep.cantidad}', normal_style),
            Paragraph(f'S/. {rep.subtotal:.2f}',
                      ParagraphStyle('r', alignment=TA_RIGHT, fontSize=9, fontName='Helvetica'))
        ])

    total = costo.total if costo else 0
    filas_costo.append([
        Paragraph('<b>Total cobrado</b>',
                  ParagraphStyle('tb', fontSize=11, fontName='Helvetica-Bold', textColor=AZUL)),
        Paragraph(f'<b>S/. {total:.2f}</b>',
                  ParagraphStyle('tr', alignment=TA_RIGHT, fontSize=11,
                                 fontName='Helvetica-Bold', textColor=TEAL))
    ])

    costo_table = Table(filas_costo, colWidths=[W*0.7, W*0.3])
    costo_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-2), 0.5, GRIS2),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('BACKGROUND', (0, len(filas_costo)-1), (-1, len(filas_costo)-1),
         colors.HexColor('#EBF3FB')),
        ('LINEABOVE', (0, len(filas_costo)-1), (-1, len(filas_costo)-1), 1, AZUL),
        ('BOX', (0,0), (-1,-1), 0.5, GRIS2),
    ]))
    story.append(costo_table)
    story.append(Spacer(1, 1*cm))

    # FIRMAS
    tecnico_nombre = ''
    if detalle and detalle.tecnico:
        tecnico_nombre = detalle.tecnico.get_full_name() or detalle.tecnico.username

    firmas = Table([[
        Paragraph(f'<font color="grey">Firma del tecnico · {tecnico_nombre}</font>',
                  ParagraphStyle('f', alignment=TA_CENTER, fontSize=8, fontName='Helvetica')),
        Paragraph(f'<font color="grey">Firma del cliente · {solicitud.cliente.nombre}</font>',
                  ParagraphStyle('f', alignment=TA_CENTER, fontSize=8, fontName='Helvetica')),
    ]], colWidths=[W*0.5, W*0.5])
    firmas.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (0,0), 0.5, colors.grey),
        ('LINEABOVE', (1,0), (1,0), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(firmas)

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="informe_S{solicitud.id:03d}.pdf"'
    return response

    # ── ELIMINAR SOLICITUD ─────────────────────────────────────────
@login_required
def eliminar_solicitud(request, pk):
    if request.user.rol != 'admin':
        return redirect('consultar_solicitudes')
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if solicitud.estado != 'entregado':
        messages.error(request, 'Solo se pueden eliminar solicitudes entregadas.')
        return redirect('detalle_solicitud', pk=pk)
    if request.method == 'POST':
        solicitud.delete()
        messages.success(request, f'Solicitud #S-{pk} eliminada correctamente.')
        return redirect('consultar_solicitudes')
    return render(request, 'core/solicitudes/eliminar.html', {'solicitud': solicitud})
    
    # ── MARCAR COMO PRIORITARIA ────────────────────────────────────
@require_POST
@login_required
def marcar_prioritaria(request, pk):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('consultar_solicitudes')
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if solicitud.prioridad != 'alta':
        solicitud.prioridad_anterior = solicitud.prioridad
    solicitud.prioridad      = 'alta'
    solicitud.es_prioritaria = True
    solicitud.save()
    messages.success(request, f'Solicitud #S-{pk} marcada como prioritaria.')
    return redirect('consultar_solicitudes')


# ── QUITAR PRIORIDAD ───────────────────────────────────────────
@require_POST
@login_required
def quitar_prioritaria(request, pk):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('consultar_solicitudes')
    solicitud = get_object_or_404(Solicitud, pk=pk)
    solicitud.prioridad      = solicitud.prioridad_anterior or 'media'
    solicitud.prioridad_anterior = ''
    solicitud.es_prioritaria = False
    solicitud.save()
    messages.success(request, f'Prioridad de solicitud #S-{pk} restaurada a "{solicitud.get_prioridad_display()}".')
    return redirect('consultar_solicitudes')


# ── REASIGNAR TÉCNICO ──────────────────────────────────────────
@login_required
def reasignar_tecnico(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    detalle, _ = DetalleSolicitud.objects.get_or_create(solicitud=solicitud)
    tecnico_actual = detalle.tecnico

    if request.method == 'POST':
        form = AsignarTecnicoForm(request.POST)
        if form.is_valid():
            tecnico_nuevo = form.cleaned_data['tecnico']
            detalle.tecnico = tecnico_nuevo
            detalle.save()
            HistorialEstado.objects.create(
                solicitud    = solicitud,
                usuario      = request.user,
                estado_antes = solicitud.estado,
                estado_nuevo = solicitud.estado,
                observacion  = f'Técnico reasignado de '
                               f'{tecnico_actual.get_full_name() if tecnico_actual else "Sin asignar"} '
                               f'a {tecnico_nuevo.get_full_name()}'
            )
            messages.success(request, 'Técnico reasignado correctamente.')
            return redirect('detalle_solicitud', pk=pk)
    else:
        form = AsignarTecnicoForm()

    return render(request, 'core/solicitudes/reasignar_tecnico.html', {
        'form':           form,
        'solicitud':      solicitud,
        'tecnico_actual': tecnico_actual,
    })

    # ── HISTORIAL DEL CLIENTE ──────────────────────────────────────
@login_required
def historial_cliente(request, pk):
    cliente    = get_object_or_404(Cliente, pk=pk)
    solicitudes = Solicitud.objects.filter(
        cliente=cliente
    ).select_related('equipo', 'detalle__tecnico').order_by('-creado_en')
    return render(request, 'core/clientes/historial.html', {
        'cliente':     cliente,
        'solicitudes': solicitudes,
    })

    # ── HISTORIAL DEL EQUIPO ───────────────────────────────────────
@login_required
def historial_equipo(request, pk):
    equipo      = get_object_or_404(Equipo, pk=pk)
    solicitudes = Solicitud.objects.filter(
        equipo=equipo
    ).select_related('cliente', 'detalle__tecnico').order_by('-creado_en')
    return render(request, 'core/equipos/historial.html', {
        'equipo':      equipo,
        'solicitudes': solicitudes,
    })

    # ── ACTUALIZAR EQUIPO ──────────────────────────────────────────
@login_required
def actualizar_equipo(request, pk):
    if request.user.rol == 'tec':
        return redirect('dashboard')
    equipo = get_object_or_404(Equipo.objects.select_related('cliente'), pk=pk)
    if request.method == 'POST':
        form = EquipoUpdateForm(request.POST, instance=equipo)
        if form.is_valid():
            if request.user.rol != 'admin':
                campos_identidad = ['tipo', 'marca', 'modelo', 'serie']
                equipo_actual = Equipo.objects.get(pk=pk)
                for campo in campos_identidad:
                    setattr(form.instance, campo, getattr(equipo_actual, campo))
            form.save()
            messages.success(request, 'Equipo actualizado correctamente.')
            return redirect('consultar_equipos')
    else:
        form = EquipoUpdateForm(instance=equipo)
    return render(request, 'core/equipos/actualizar.html', {
        'form':   form,
        'equipo': equipo,
    })

    # ── ELIMINAR CLIENTE ────────────────────────────────────────────
@login_required
def eliminar_cliente(request, pk):
    if request.user.rol != 'admin':
        messages.error(request, 'Solo el administrador puede eliminar clientes.')
        return redirect('consultar_clientes')
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        try:

            nombre = cliente.nombre_completo
            cliente.delete()
            messages.success(request, f'Cliente {nombre} eliminado correctamente.')
            return redirect('consultar_clientes')
        except ProtectedError:
            messages.error(request,
                f'No se puede eliminar a {cliente.nombre_completo} porque tiene '
                f'equipos o solicitudes registradas. Elimínalos primero.')
            return redirect('consultar_clientes')
    return render(request, 'core/clientes/eliminar.html', {'cliente': cliente})


# ── ELIMINAR EQUIPO ─────────────────────────────────────────────
@login_required
def eliminar_equipo(request, pk):
    if request.user.rol != 'admin':
        messages.error(request, 'Solo el administrador puede eliminar equipos.')
        return redirect('consultar_equipos')
    equipo = get_object_or_404(Equipo.objects.select_related('cliente'), pk=pk)
    if request.method == 'POST':
        try:

            desc = f'{equipo.get_marca_display()} {equipo.modelo}'
            equipo.delete()
            messages.success(request, f'Equipo {desc} eliminado correctamente.')
            return redirect('consultar_equipos')
        except ProtectedError:
            messages.error(request,
                'No se puede eliminar este equipo porque tiene solicitudes '
                'registradas. Elimínalas primero.')
            return redirect('consultar_equipos')
    return render(request, 'core/equipos/eliminar.html', {'equipo': equipo})

  # ── AMPLIACIÓN DE TIEMPO ────────────────────────────────────────
@login_required
def solicitar_ampliacion(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)

    if request.user.rol == 'tec':
        try:
            if solicitud.detalle.tecnico != request.user:
                messages.error(request, 'Solo el técnico asignado puede solicitar ampliación.')
                return redirect('detalle_solicitud', pk=pk)
        except Exception:
            messages.error(request, 'Esta solicitud no tiene técnico asignado.')
            return redirect('detalle_solicitud', pk=pk)
    elif request.user.rol not in ('admin', 'tec'):
        return redirect('detalle_solicitud', pk=pk)

    if request.method == 'POST':
        form = AmpliacionTiempoForm(request.POST)
        if form.is_valid():
            cantidad = form.cleaned_data['cantidad']
            unidad   = form.cleaned_data['unidad']
            justif   = form.cleaned_data['justificacion']

            AmpliacionTiempo.objects.create(
                solicitud     = solicitud,
                tecnico       = request.user,
                cantidad      = cantidad,
                unidad        = unidad,
                justificacion = justif,
            )

            if solicitud.fecha_estimada:
                if unidad == 'horas':
                    delta = datetime.timedelta(hours=cantidad)
                else:
                    delta = datetime.timedelta(minutes=cantidad)
                solicitud.fecha_estimada = solicitud.fecha_estimada + delta
                if solicitud.fecha_hora_estimada:
                    solicitud.fecha_hora_estimada = solicitud.fecha_hora_estimada + delta

            sufijo = f'+{cantidad} {"h" if unidad == "horas" else "min"}'
            if solicitud.tiempo_estimado_texto:
                solicitud.tiempo_estimado_texto += f' ({sufijo})'
            else:
                solicitud.tiempo_estimado_texto = sufijo

            delta_horas = Decimal(cantidad) if unidad == 'horas' else Decimal(cantidad) / 60
            if solicitud.tiempo_estimado_horas is None:
                solicitud.tiempo_estimado_horas = delta_horas
            else:
                solicitud.tiempo_estimado_horas += delta_horas

            solicitud.save()

            HistorialEstado.objects.create(
                solicitud    = solicitud,
                usuario      = request.user,
                estado_antes = solicitud.estado,
                estado_nuevo = solicitud.estado,
                observacion  = f'Ampliación de tiempo: +{cantidad} {unidad}. '
                               f'Justificación: {justif}'
            )
            messages.success(request,
                f'Ampliación de {cantidad} {unidad} registrada correctamente.')
            return redirect('detalle_solicitud', pk=pk)
    else:
        form = AmpliacionTiempoForm()

    return render(request, 'core/solicitudes/ampliacion.html', {
        'form':      form,
        'solicitud': solicitud,
    })