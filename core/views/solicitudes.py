"""Vistas del ciclo de vida de solicitudes de reparación."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Sum, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import AsignarTecnicoForm, CambiarEstadoForm, SolicitudForm
from ..models import (
    Avance, Cliente, Costo, DetalleSolicitud, Equipo, HistorialEstado, Solicitud, Usuario,
)
from ..services import calcular_fecha_libre_laboral, calcular_tiempo_estimado
from .helpers import ETAPA_ORDEN, paginar


# ── REGISTRAR SOLICITUD ────────────────────────────────────────
@login_required
def registrar_solicitud(request):
    if request.user.rol == Usuario.Rol.TECNICO:
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
    # Pendientes sin asignar primero → pendientes con técnico → en proceso → finalizado → entregado
    orden_urgencia = Case(
        When(estado='pendiente', detalle__tecnico__isnull=True, then=0),
        When(estado='pendiente', then=1),
        When(estado='proceso',    then=2),
        When(estado='finalizado', then=3),
        When(estado='entregado',  then=4),
        default=5,
        output_field=IntegerField(),
    )
    solicitudes = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).annotate(
        _ord=orden_prioridad,
        _urgencia=orden_urgencia,
    ).order_by('_urgencia', '_ord' if orden == 'desc' else '-_ord', '-creado_en')

    if request.user.rol == Usuario.Rol.TECNICO:
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

    tecnicos = Usuario.objects.filter(rol=Usuario.Rol.TECNICO)

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
    if request.user.rol == Usuario.Rol.TECNICO:
        detalle = getattr(solicitud, 'detalle', None)
        asignado = detalle.tecnico if detalle else None
        if asignado != request.user:
            messages.error(request, 'No tienes permiso para ver esta solicitud.')
            return redirect('consultar_solicitudes')
    historial = solicitud.historial.select_related('usuario').all()
    avances   = solicitud.avances.select_related('usuario').all()

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
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.TECNICO]:
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
    if request.user.rol == Usuario.Rol.TECNICO:
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
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
        return redirect('detalle_solicitud', pk=pk)

    solicitud = get_object_or_404(Solicitud, pk=pk)

    MAPA_TIPO_ESP = {
        'hardware':   'hardware',
        'software':   'software',
        'preventivo': 'general',
        'revision':   'general',
    }
    esp_ideal = MAPA_TIPO_ESP.get(solicitud.tipo_reparacion, 'general')
    tecnicos  = Usuario.objects.filter(rol=Usuario.Rol.TECNICO)
    # Si hay técnico actual asignado, excluirlo de la lista de reasignación
    try:
        tecnico_actual = solicitud.detalle.tecnico
        if tecnico_actual:
            tecnicos = tecnicos.exclude(pk=tecnico_actual.pk)
    except (DetalleSolicitud.DoesNotExist, AttributeError):
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


# ── REASIGNAR TÉCNICO ──────────────────────────────────────────
@login_required
def reasignar_tecnico(request, pk):
    if request.user.rol not in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA):
        messages.error(request, 'No tienes permiso para reasignar técnicos.')
        return redirect('detalle_solicitud', pk=pk)
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


# ── MARCAR COMO PRIORITARIA ────────────────────────────────────
@require_POST
@login_required
def marcar_prioritaria(request, pk):
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
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
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
        return redirect('consultar_solicitudes')
    solicitud = get_object_or_404(Solicitud, pk=pk)
    solicitud.prioridad      = solicitud.prioridad_anterior or 'media'
    solicitud.prioridad_anterior = ''
    solicitud.es_prioritaria = False
    solicitud.save()
    messages.success(request, f'Prioridad de solicitud #S-{pk} restaurada a "{solicitud.get_prioridad_display()}".')
    return redirect('consultar_solicitudes')


# ── ELIMINAR SOLICITUD ─────────────────────────────────────────
@login_required
def eliminar_solicitud(request, pk):
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
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


# ── ENTREGA DE EQUIPO ──────────────────────────────────────────
@login_required
def entrega(request, pk):
    if request.user.rol not in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA):
        messages.error(request, 'No tienes permiso para registrar entregas.')
        return redirect('detalle_solicitud', pk=pk)
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


# ── SEGUIMIENTO PÚBLICO ────────────────────────────────────────
def seguimiento(request, token):
    solicitud = get_object_or_404(
        Solicitud.objects.select_related('cliente', 'equipo', 'detalle__tecnico'),
        token_seguimiento=token
    )

    avances = solicitud.avances.select_related('usuario').all()

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
