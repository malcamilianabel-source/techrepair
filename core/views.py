import datetime
from django.db.models.deletion import ProtectedError
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import (Usuario, Cliente, Equipo, Solicitud, DetalleSolicitud,
                     HistorialEstado, Avance, Repuesto, Costo, AmpliacionTiempo)
from .forms import (ClienteForm, EquipoForm, EquipoUpdateForm, SolicitudForm,
                    CambiarEstadoForm, AsignarTecnicoForm, UsuarioForm,
                    DiagnosticoForm, AvanceForm, AmpliacionTiempoForm)

# deploy test

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
@login_required(login_url='login')
def dashboard(request):
    import re

    if request.user.rol == 'tec':
        # Dashboard del técnico — solo sus solicitudes
        mis_solicitudes = Solicitud.objects.filter(
            detalle__tecnico=request.user
        ).select_related('cliente', 'equipo').order_by('-creado_en')

        pendientes  = mis_solicitudes.filter(estado='pendiente').count()
        en_proceso  = mis_solicitudes.filter(estado='proceso').count()
        finalizadas = mis_solicitudes.filter(estado='finalizado').count()

        # Calcular horas de carga personal
        activas = mis_solicitudes.filter(estado__in=['pendiente', 'proceso'])
        total_horas = 0
        for sol in activas:
            if sol.tiempo_estimado_texto:
                m = re.search(r'\d+', sol.tiempo_estimado_texto)
                if m:
                    total_horas += int(m.group())

        return render(request, 'core/dashboard.html', {
            'mis_solicitudes': mis_solicitudes[:8],
            'pendientes':      pendientes,
            'en_proceso':      en_proceso,
            'finalizadas':     finalizadas,
            'total_horas':     total_horas,
            'total_activas':   activas.count(),
        })

    else:
        # Dashboard del admin/recepcionista
        total_sol   = Solicitud.objects.count()
        pendientes  = Solicitud.objects.filter(estado='pendiente').count()
        en_proceso  = Solicitud.objects.filter(estado='proceso').count()
        finalizadas = Solicitud.objects.filter(estado='finalizado').count()

        # Carga por técnico con horas
        tecnicos = Usuario.objects.filter(rol='tec')
        carga_tecnicos = []
        for tec in tecnicos:
            sols = Solicitud.objects.filter(
                detalle__tecnico=tec,
                estado__in=['pendiente', 'proceso']
            )
            total_trabajos = sols.count()
            total_horas = 0
            for sol in sols:
                if sol.tiempo_estimado_texto:
                    m = re.search(r'\d+', sol.tiempo_estimado_texto)
                    if m:
                        total_horas += int(m.group())
            carga_tecnicos.append({
                'nombre':   tec.get_full_name() or tec.username,
                'trabajos': total_trabajos,
                'horas':    total_horas,
            })

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
@login_required(login_url='login')
def consultar_clientes(request):
    query    = request.GET.get('q', '')
    clientes = Cliente.objects.all().order_by('-creado_en')
    if query:
        clientes = clientes.filter(
            nombre__icontains=query
        ) | clientes.filter(
            dni__icontains=query
        ) | clientes.filter(
            telefono__icontains=query
        )
    return render(request, 'core/clientes/consultar.html', {
        'clientes': clientes,
        'query':    query,
    })


# ── REGISTRAR CLIENTE ──────────────────────────────────────────
@login_required(login_url='login')
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
@login_required(login_url='login')
def actualizar_cliente(request, pk):
    cliente = Cliente.objects.get(pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('consultar_clientes')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'core/clientes/actualizar.html', {
        'form':    form,
        'cliente': cliente,
    })

# ── CONSULTAR EQUIPOS ──────────────────────────────────────────
@login_required(login_url='login')
def consultar_equipos(request):
    query   = request.GET.get('q', '')
    tipo    = request.GET.get('tipo', '')
    equipos = Equipo.objects.select_related('cliente').order_by('-creado_en')
    if query:
        equipos = equipos.filter(
            marca__icontains=query
        ) | equipos.filter(
            modelo__icontains=query
        ) | equipos.filter(
            serie__icontains=query
        )
    if tipo:
        equipos = equipos.filter(tipo=tipo)
    return render(request, 'core/equipos/consultar.html', {
        'equipos': equipos,
        'query':   query,
        'tipo':    tipo,
        'tipos':   Equipo.TIPOS,
    })


# ── REGISTRAR EQUIPO ───────────────────────────────────────────
@login_required(login_url='login')
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


# ── MOTOR DE ESTIMACIÓN DE TIEMPO ─────────────────────────────
def calcular_tiempo_estimado(tipo, prioridad, fecha_ingreso):
    import math
    tiempos_base = {
        'revision':   1,
        'preventivo': 2,
        'software':   3,
        'hardware':   6,
    }
    multiplicadores = {
        'alta':  0.75,
        'media': 1.0,
        'baja':  1.5,
    }
    base = tiempos_base.get(tipo, 3)
    mult = multiplicadores.get(prioridad, 1.0)
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

    
    fecha_estimada = datetime.datetime.combine(fecha_ingreso, datetime.time(8, 0))
    fecha_estimada = fecha_estimada + datetime.timedelta(hours=horas)
    dias_estimados = math.ceil(horas / 8)  
    return dias_estimados, fecha_estimada.date(), tiempo_texto


# ── REGISTRAR SOLICITUD ────────────────────────────────────────
@login_required(login_url='login')
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
            solicitud = form.save(commit=False)
            if solicitud.equipo.cliente != solicitud.cliente:
                form.add_error('equipo',
                    'El equipo seleccionado no pertenece al cliente elegido.')
                return render(request, 'core/solicitudes/registrar.html', {
                    'form': form,
                    'cliente_fijo': cliente_fijo,
                    'equipo_fijo':  equipo_fijo,
                })
            duplicada = Solicitud.objects.filter(
                cliente    = solicitud.cliente,
                equipo     = solicitud.equipo,
                estado__in = ['pendiente', 'proceso']
            ).exists()
            if duplicada:
                form.add_error(None,
                    f'Ya existe una solicitud activa para {solicitud.cliente.nombre_completo} '
                    f'con el equipo {solicitud.equipo.marca} {solicitud.equipo.modelo}. '
                    f'Finaliza esa solicitud antes de crear una nueva.')
                return render(request, 'core/solicitudes/registrar.html', {
                    'form': form,
                    'cliente_fijo': cliente_fijo,
                    'equipo_fijo':  equipo_fijo,
                })
            dias, fecha_est, tiempo_texto = calcular_tiempo_estimado(
                solicitud.tipo_reparacion,
                solicitud.prioridad,
                datetime.date.today()
            )
            solicitud.dias_estimados        = dias
            solicitud.fecha_estimada        = fecha_est
            solicitud.tiempo_estimado_texto = tiempo_texto
            solicitud.save()
            HistorialEstado.objects.create(
                solicitud    = solicitud,
                usuario      = request.user,
                estado_antes = '—',
                estado_nuevo = 'pendiente',
                observacion  = 'Solicitud creada'
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
@login_required(login_url='login')
def consultar_solicitudes(request):
    estado   = request.GET.get('estado', '')
    tecnico  = request.GET.get('tecnico', '')
    prioridad= request.GET.get('prioridad', '')
    q        = request.GET.get('q', '')

    solicitudes = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).order_by('-creado_en')

    if request.user.rol == 'tec':
        solicitudes = solicitudes.filter(detalle__tecnico=request.user)

    if estado:
        solicitudes = solicitudes.filter(estado=estado)
    if prioridad:
        solicitudes = solicitudes.filter(prioridad=prioridad)
    if q:
        solicitudes = solicitudes.filter(cliente__nombre__icontains=q)

    tecnicos = Usuario.objects.filter(rol='tec')

    return render(request, 'core/solicitudes/consultar.html', {
        'solicitudes': solicitudes,
        'tecnicos':    tecnicos,
        'estado':      estado,
        'prioridad':   prioridad,
        'q':           q,
    })


# ── DETALLE SOLICITUD ──────────────────────────────────────────
@login_required(login_url='login')
def detalle_solicitud(request, pk):
    solicitud = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).get(pk=pk)
    historial = solicitud.historial.select_related('usuario').all()
    return render(request, 'core/solicitudes/detalle.html', {
        'solicitud': solicitud,
        'historial': historial,
    })


# ── CAMBIAR ESTADO ─────────────────────────────────────────────
@login_required(login_url='login')
def cambiar_estado(request, pk):
    solicitud = Solicitud.objects.get(pk=pk)
    if request.method == 'POST':
        form = CambiarEstadoForm(request.POST)
        if form.is_valid():
            if request.user.rol == 'tec' and form.cleaned_data['estado'] == 'entregado':
                messages.error(request, 'Los técnicos no pueden marcar como Entregado.')
                return redirect('detalle_solicitud', pk=pk)
            estado_antes         = solicitud.estado
            solicitud.estado     = form.cleaned_data['estado']
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
        form = CambiarEstadoForm(initial={'estado': solicitud.estado})
        if request.user.rol == 'tec':
            form.fields['estado'].choices = [
                ('pendiente',  'Pendiente'),
                ('proceso',    'En proceso'),
                ('finalizado', 'Finalizado'),
            ]
    return render(request, 'core/solicitudes/cambiar_estado.html', {
        'form':      form,
        'solicitud': solicitud,
    })


# ── ASIGNAR TÉCNICO ────────────────────────────────────────────
@login_required(login_url='login')
def asignar_tecnico(request, pk):
    from django.db.models import Q
    from django.utils import timezone

    if request.user.rol not in ['admin', 'recep']:
        return redirect('detalle_solicitud', pk=pk)

    solicitud = Solicitud.objects.get(pk=pk)

    MAPA_TIPO_ESP = {
        'hardware':   'hardware',
        'software':   'software',
        'preventivo': 'general',
        'revision':   'general',
    }
    esp_ideal = MAPA_TIPO_ESP.get(solicitud.tipo_reparacion, 'general')
    tecnicos  = Usuario.objects.filter(rol='tec')
    now       = timezone.now()

    tecnicos_libres   = []
    tecnicos_ocupados = []

    for tec in tecnicos:
        activos = Solicitud.objects.filter(
            detalle__tecnico=tec, estado__in=['pendiente', 'proceso']
        ).count()

        if activos == 0:
            tecnicos_libres.append(tec)
        else:
            proxima_sol = Solicitud.objects.filter(
                detalle__tecnico=tec,
                estado__in=['pendiente', 'proceso'],
                fecha_estimada__isnull=False
            ).order_by('fecha_estimada').first()

            fecha_libre     = proxima_sol.fecha_estimada if proxima_sol else None
            tiempo_restante = None

            if fecha_libre:
                import datetime as dt_mod
                if isinstance(fecha_libre, dt_mod.date) and not isinstance(fecha_libre, dt_mod.datetime):
                    from django.utils.timezone import make_aware
                    fecha_libre = make_aware(dt_mod.datetime.combine(fecha_libre, dt_mod.time(23, 59)))
                delta         = fecha_libre - now
                total_seconds = int(delta.total_seconds())
                if total_seconds > 0:
                    horas   = total_seconds // 3600
                    minutos = (total_seconds % 3600) // 60
                    if horas >= 48:
                        dias = horas // 24
                        tiempo_restante = f'{dias} día{"s" if dias != 1 else ""}'
                    elif horas >= 1:
                        tiempo_restante = f'{horas}h {minutos}min'
                    else:
                        tiempo_restante = f'{minutos} min'
                else:
                    tiempo_restante = 'Tiempo vencido'

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
        form = AsignarTecnicoForm(request.POST)
        if form.is_valid():
            tec_id  = form.cleaned_data['tecnico'].pk
            tec_obj = Usuario.objects.get(pk=tec_id)
            det     = solicitud.detalle
            det.tecnico = tec_obj
            det.save()
            HistorialEstado.objects.create(
                solicitud=solicitud, usuario=request.user,
                estado_antes=solicitud.estado, estado_nuevo='proceso',
                observacion=f'Técnico asignado: {tec_obj.get_full_name() or tec_obj.username}'
            )
            solicitud.estado = 'proceso'
            solicitud.save()
            messages.success(request, f'Técnico {tec_obj.get_full_name() or tec_obj.username} asignado correctamente.')
            return redirect('detalle_solicitud', pk=pk)
    else:
        form = AsignarTecnicoForm()

    return render(request, 'core/solicitudes/asignar_tecnico.html', {
        'solicitud':             solicitud,
        'form':                  form,
        'tecnicos_libres':       tecnicos_libres,
        'tecnicos_ocupados':     tecnicos_ocupados,
        'recomendado':           recomendado,
        'esp_ideal':             esp_ideal,
        'hay_libres':            len(tecnicos_libres) > 0,
        'lista_espera_clientes': lista_espera_clientes,
    })

    # ── REGISTRAR USUARIO ──────────────────────────────────────────
@login_required(login_url='login')
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

    # ── DIAGNÓSTICO ────────────────────────────────────────────────
@login_required(login_url='login')
def diagnostico(request, pk):
    solicitud = Solicitud.objects.get(pk=pk)
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
@login_required(login_url='login')
def avance(request, pk):
    solicitud = Solicitud.objects.get(pk=pk)
    avances   = solicitud.avances.select_related('usuario').all()
    if request.method == 'POST':
        form = AvanceForm(request.POST)
        if form.is_valid():
            av          = form.save(commit=False)
            av.solicitud = solicitud
            av.usuario   = request.user
            av.save()
            messages.success(request, 'Avance registrado correctamente.')
            return redirect('avance', pk=pk)
    else:
        form = AvanceForm()
    return render(request, 'core/solicitudes/avance.html', {
        'form':      form,
        'solicitud': solicitud,
        'avances':   avances,
    })

    # ── REPUESTOS ──────────────────────────────────────────────────
@login_required(login_url='login')
def repuestos(request, pk):
    solicitud = Solicitud.objects.get(pk=pk)
    repuestos = solicitud.repuestos.all()
    if request.method == 'POST':
        nombre      = request.POST.get('nombre')
        cantidad    = request.POST.get('cantidad')
        precio_unit = request.POST.get('precio_unit')
        if nombre and cantidad and precio_unit:
            Repuesto.objects.create(
                solicitud   = solicitud,
                nombre      = nombre,
                cantidad    = int(cantidad),
                precio_unit = precio_unit
            )
            # Actualizar costo total
            costo, _ = Costo.objects.get_or_create(solicitud=solicitud)
            mano_obra = request.POST.get('mano_obra')
            if mano_obra:
                costo.mano_obra = mano_obra
            costo.calcular_total()
            messages.success(request, 'Repuesto agregado correctamente.')
            return redirect('repuestos', pk=pk)
    return render(request, 'core/solicitudes/repuestos.html', {
        'solicitud': solicitud,
        'repuestos': repuestos,
    })


# ── COSTOS ─────────────────────────────────────────────────────
@login_required(login_url='login')
def costos(request, pk):
    solicitud    = Solicitud.objects.get(pk=pk)
    repuestos    = solicitud.repuestos.all()
    costo, _     = Costo.objects.get_or_create(solicitud=solicitud)
    if request.method == 'POST':
        mano_obra = request.POST.get('mano_obra', 0)
        costo.mano_obra = mano_obra
        costo.calcular_total()
        messages.success(request, 'Costo actualizado correctamente.')
        return redirect('costos', pk=pk)
    return render(request, 'core/solicitudes/costos.html', {
        'solicitud': solicitud,
        'repuestos': repuestos,
        'costo':     costo,
    })

    # ── REPORTES — ÍNDICE ──────────────────────────────────────────
@login_required(login_url='login')
def reportes(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')
    return render(request, 'core/reportes/index.html', {})


# ── REPORTE SOLICITUDES ────────────────────────────────────────
@login_required(login_url='login')
def reporte_solicitudes(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')

    total   = Solicitud.objects.count()
    estados = {
        'pendiente':  Solicitud.objects.filter(estado='pendiente').count(),
        'proceso':    Solicitud.objects.filter(estado='proceso').count(),
        'finalizado': Solicitud.objects.filter(estado='finalizado').count(),
        'entregado':  Solicitud.objects.filter(estado='entregado').count(),
    }

    tipos = {}
    for t, label in Solicitud.TIPOS_REP:
        tipos[label] = Solicitud.objects.filter(tipo_reparacion=t).count()

    por_tecnico = []
    for tec in Usuario.objects.filter(rol='tec'):
        cant = DetalleSolicitud.objects.filter(tecnico=tec).count()
        por_tecnico.append({
            'nombre':   tec.get_full_name() or tec.username,
            'cantidad': cant,
        })

    # Solicitudes por mes — últimos 6 meses
    hoy = datetime.date.today()
    meses_labels = []
    meses_data   = []
    for i in range(5, -1, -1):
        year  = hoy.year
        month = hoy.month - i
        while month <= 0:
            month += 12
            year  -= 1
        count = Solicitud.objects.filter(
            fecha_ingreso__year=year,
            fecha_ingreso__month=month
        ).count()
        meses_labels.append(datetime.date(year, month, 1).strftime('%b %Y'))
        meses_data.append(count)

    # Marca más reparada
    from django.db.models import Count
    marca_top = (Equipo.objects
                 .filter(solicitudes__isnull=False)
                 .values('marca')
                 .annotate(total=Count('solicitudes'))
                 .order_by('-total')
                 .first())

    # Tasa de resolución
    resueltas = estados['finalizado'] + estados['entregado']
    tasa = round((resueltas / total * 100), 1) if total else 0

    recientes = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).order_by('-creado_en')[:10]

    import json
    return render(request, 'core/reportes/solicitudes.html', {
        'total':         total,
        'estados':       estados,
        'tipos':         tipos,
        'por_tecnico':   por_tecnico,
        'recientes':     recientes,
        'meses_labels':  json.dumps(meses_labels),
        'meses_data':    json.dumps(meses_data),
        'marca_top':     marca_top,
        'tasa':          tasa,
        'resueltas':     resueltas,
    })


# ── REPORTE TIEMPOS ────────────────────────────────────────────
@login_required(login_url='login')
def reporte_tiempos(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')

    import json
    from decimal import Decimal
    from django.db.models import Avg, Sum

    tiempos_por_tipo = {}
    for t, label in Solicitud.TIPOS_REP:
        sols = Solicitud.objects.filter(tipo_reparacion=t)
        sols_con_tiempo = sols.filter(tiempo_estimado_horas__isnull=False)
        agg = sols_con_tiempo.aggregate(
            total=Sum('tiempo_estimado_horas'),
            promedio=Avg('tiempo_estimado_horas')
        )
        total_horas = float(agg['total'] or 0)
        promedio    = round(float(agg['promedio'] or 0), 1)
        tiempos_por_tipo[label] = {
            'cantidad':    sols.count(),
            'promedio':    promedio,
            'total_horas': round(total_horas, 1),
        }

    agg_general = Solicitud.objects.filter(
        tiempo_estimado_horas__isnull=False
    ).aggregate(
        total=Sum('tiempo_estimado_horas'),
        promedio=Avg('tiempo_estimado_horas')
    )
    total_horas_acum = round(float(agg_general['total'] or 0), 1)
    promedio_general = round(float(agg_general['promedio'] or 0), 1)

    tipos_con_datos = {k: v for k, v in tiempos_por_tipo.items() if v['promedio'] > 0}
    tipo_rapido = min(tipos_con_datos.items(), key=lambda x: x[1]['promedio'])[0] if tipos_con_datos else '—'
    tipo_lento  = max(tipos_con_datos.items(), key=lambda x: x[1]['promedio'])[0] if tipos_con_datos else '—'

    chart_labels    = json.dumps(list(tiempos_por_tipo.keys()))
    chart_promedios = json.dumps([v['promedio']    for v in tiempos_por_tipo.values()])
    chart_totales   = json.dumps([v['total_horas'] for v in tiempos_por_tipo.values()])
    chart_cantidad  = json.dumps([v['cantidad']    for v in tiempos_por_tipo.values()])

    tiempos_prioridad = {}
    for p, label in Solicitud.PRIORIDADES:
        agg_p = Solicitud.objects.filter(
            prioridad=p, tiempo_estimado_horas__isnull=False
        ).aggregate(promedio=Avg('tiempo_estimado_horas'))
        tiempos_prioridad[label] = round(float(agg_p['promedio'] or 0), 1)

    return render(request, 'core/reportes/tiempos.html', {
        'tiempos_por_tipo':  tiempos_por_tipo,
        'promedio_general':  promedio_general,
        'total_solicitudes': Solicitud.objects.count(),
        'total_horas_acum':  total_horas_acum,
        'tipo_rapido':       tipo_rapido,
        'tipo_lento':        tipo_lento,
        'chart_labels':      chart_labels,
        'chart_promedios':   chart_promedios,
        'chart_totales':     chart_totales,
        'chart_cantidad':    chart_cantidad,
        'tiempos_prioridad': json.dumps(tiempos_prioridad),
        'prioridad_labels':  json.dumps(list(tiempos_prioridad.keys())),
    })

# ── REPORTE INGRESOS ───────────────────────────────────────────
@login_required(login_url='login')
def reporte_ingresos(request):
    if request.user.rol != 'admin':
        return redirect('dashboard')

    import json
    from django.db.models import Sum

    costos = Costo.objects.select_related('solicitud__cliente').all()
    total_ingresos  = sum(c.total     for c in costos)
    total_mano_obra = sum(c.mano_obra for c in costos)
    total_repuestos = total_ingresos - total_mano_obra
    ticket_promedio = round(total_ingresos / costos.count(), 2) if costos.count() else 0

    # Ingresos por mes — últimos 6 meses
    hoy = datetime.date.today()
    meses_labels  = []
    meses_ingresos = []
    meses_mano    = []
    for i in range(5, -1, -1):
        year  = hoy.year
        month = hoy.month - i
        while month <= 0:
            month += 12; year -= 1
        sols_mes = Costo.objects.filter(
            solicitud__fecha_ingreso__year=year,
            solicitud__fecha_ingreso__month=month
        )
        ing = sum(c.total     for c in sols_mes)
        man = sum(c.mano_obra for c in sols_mes)
        meses_labels.append(datetime.date(year, month, 1).strftime('%b %Y'))
        meses_ingresos.append(float(ing))
        meses_mano.append(float(man))

    # Ingresos por tipo de reparación
    ingresos_tipo = {}
    for t, label in Solicitud.TIPOS_REP:
        sols_tipo = Costo.objects.filter(solicitud__tipo_reparacion=t)
        ingresos_tipo[label] = float(sum(c.total for c in sols_tipo))

    # Técnico con más ingresos generados
    tec_ingresos = []
    for tec in Usuario.objects.filter(rol='tec'):
        ing = sum(
            c.total for c in Costo.objects.filter(
                solicitud__detalle__tecnico=tec
            )
        )
        tec_ingresos.append({'nombre': tec.get_full_name() or tec.username, 'total': float(ing)})
    tec_ingresos.sort(key=lambda x: x['total'], reverse=True)

    ultimos = Costo.objects.select_related(
        'solicitud__cliente', 'solicitud__equipo'
    ).order_by('-solicitud__creado_en')[:10]

    return render(request, 'core/reportes/ingresos.html', {
        'total_ingresos':   total_ingresos,
        'total_mano_obra':  total_mano_obra,
        'total_repuestos':  total_repuestos,
        'ticket_promedio':  ticket_promedio,
        'total_registros':  costos.count(),
        'ultimos':          ultimos,
        'tec_ingresos':     tec_ingresos,
        'meses_labels':     json.dumps(meses_labels),
        'meses_ingresos':   json.dumps(meses_ingresos),
        'meses_mano':       json.dumps(meses_mano),
        'ingresos_tipo_labels': json.dumps(list(ingresos_tipo.keys())),
        'ingresos_tipo_data':   json.dumps(list(ingresos_tipo.values())),
        'tec_labels': json.dumps([t['nombre'] for t in tec_ingresos]),
        'tec_data':   json.dumps([t['total']  for t in tec_ingresos]),
    })

    # ── API: EQUIPOS POR CLIENTE ───────────────────────────────────
from django.http import JsonResponse

@login_required(login_url='login')
def equipos_por_cliente(request, cliente_id):
    equipos = Equipo.objects.filter(cliente_id=cliente_id).values(
        'id', 'marca', 'modelo', 'serie'
    )
    data = []
    for e in equipos:
        data.append({
            'id':    e['id'],
            'texto': f"{e['marca'].upper()} {e['modelo']} — Serie: {e['serie']}"
        })
    return JsonResponse({'equipos': data})


    import datetime
from django.http import HttpResponse

# ── ENTREGA DE EQUIPO ──────────────────────────────────────────
@login_required(login_url='login')
def entrega(request, pk):
    solicitud = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).get(pk=pk)
    try:
        costo = solicitud.costo
    except:
        costo = None
    repuestos = solicitud.repuestos.all()

    if request.method == 'POST':
        confirmacion = request.POST.get('confirmacion') == 'on'
        observaciones = request.POST.get('observaciones', '')
        solicitud.fecha_entrega         = datetime.date.today()
        solicitud.hora_entrega          = datetime.datetime.now().time()
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
        'hoy':       datetime.date.today(),
        'ahora':     datetime.datetime.now().strftime('%H:%M'),
    })


# ── INFORME PDF ────────────────────────────────────────────────
@login_required(login_url='login')
def informe_pdf(request, pk):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import io

    solicitud = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).get(pk=pk)

    try:
        costo = solicitud.costo
    except:
        costo = None

    try:
        detalle = solicitud.detalle
    except:
        detalle = None

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
                         else datetime.date.today().strftime('%d/%m/%Y'))

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
@login_required(login_url='login')
def eliminar_solicitud(request, pk):
    if request.user.rol != 'admin':
        return redirect('consultar_solicitudes')
    solicitud = Solicitud.objects.get(pk=pk)
    if solicitud.estado != 'entregado':
        messages.error(request, 'Solo se pueden eliminar solicitudes entregadas.')
        return redirect('detalle_solicitud', pk=pk)
    if request.method == 'POST':
        solicitud.delete()
        messages.success(request, f'Solicitud #S-{pk} eliminada correctamente.')
        return redirect('consultar_solicitudes')
    return render(request, 'core/solicitudes/eliminar.html', {'solicitud': solicitud})
    
    # ── MARCAR COMO PRIORITARIA ────────────────────────────────────
@login_required(login_url='login')
def marcar_prioritaria(request, pk):
    solicitud = Solicitud.objects.get(pk=pk)
    solicitud.prioridad = 'alta'
    solicitud.save()
    messages.success(request, f'Solicitud #S-{pk} marcada como prioritaria.')
    return redirect('consultar_solicitudes')


# ── REASIGNAR TÉCNICO ──────────────────────────────────────────
@login_required(login_url='login')
def reasignar_tecnico(request, pk):
    solicitud = Solicitud.objects.get(pk=pk)
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
@login_required(login_url='login')
def historial_cliente(request, pk):
    from django.shortcuts import get_object_or_404
    cliente    = get_object_or_404(Cliente, pk=pk)
    solicitudes = Solicitud.objects.filter(
        cliente=cliente
    ).select_related('equipo', 'detalle__tecnico').order_by('-creado_en')
    return render(request, 'core/clientes/historial.html', {
        'cliente':     cliente,
        'solicitudes': solicitudes,
    })

    # ── HISTORIAL DEL EQUIPO ───────────────────────────────────────
@login_required(login_url='login')
def historial_equipo(request, pk):
    from django.shortcuts import get_object_or_404
    equipo      = get_object_or_404(Equipo, pk=pk)
    solicitudes = Solicitud.objects.filter(
        equipo=equipo
    ).select_related('cliente', 'detalle__tecnico').order_by('-creado_en')
    return render(request, 'core/equipos/historial.html', {
        'equipo':      equipo,
        'solicitudes': solicitudes,
    })

    # ── ACTUALIZAR EQUIPO ──────────────────────────────────────────
@login_required(login_url='login')
def actualizar_equipo(request, pk):
    if request.user.rol == 'tec':
        return redirect('dashboard')
    equipo = Equipo.objects.select_related('cliente').get(pk=pk)
    if request.method == 'POST':
        form = EquipoUpdateForm(request.POST, instance=equipo)
        if form.is_valid():
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
@login_required(login_url='login')
def eliminar_cliente(request, pk):
    if request.user.rol != 'admin':
        messages.error(request, 'Solo el administrador puede eliminar clientes.')
        return redirect('consultar_clientes')
    cliente = Cliente.objects.get(pk=pk)
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
@login_required(login_url='login')
def eliminar_equipo(request, pk):
    if request.user.rol != 'admin':
        messages.error(request, 'Solo el administrador puede eliminar equipos.')
        return redirect('consultar_equipos')
    equipo = Equipo.objects.select_related('cliente').get(pk=pk)
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
@login_required(login_url='login')
def solicitar_ampliacion(request, pk):
    from decimal import Decimal
    solicitud = Solicitud.objects.get(pk=pk)

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