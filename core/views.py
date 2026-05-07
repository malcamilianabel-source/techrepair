from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Solicitud, Cliente, Equipo, Usuario
from .forms import ClienteForm, EquipoForm
from .forms import ClienteForm, EquipoForm, SolicitudForm, CambiarEstadoForm, AsignarTecnicoForm
from .forms import (ClienteForm, EquipoForm, SolicitudForm, CambiarEstadoForm, AsignarTecnicoForm,UsuarioForm, DiagnosticoForm, AvanceForm)
from .models import (Usuario, Cliente, Equipo, Solicitud,DetalleSolicitud, HistorialEstado)
from .forms import ClienteForm, EquipoForm, SolicitudForm, CambiarEstadoForm, AsignarTecnicoForm, UsuarioForm
from .forms import (ClienteForm, EquipoForm, SolicitudForm, CambiarEstadoForm, AsignarTecnicoForm, UsuarioForm, DiagnosticoForm)
from .models import (Usuario, Cliente, Equipo, Solicitud,DetalleSolicitud, HistorialEstado, Avance)
from .models import (Usuario, Cliente, Equipo, Solicitud,DetalleSolicitud, HistorialEstado, Avance,Repuesto, Costo)


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


# ── DASHBOARD ──────────────────────────────────────────────────
@login_required(login_url='login')
def dashboard(request):
    total_solicitudes  = Solicitud.objects.count()
    pendientes         = Solicitud.objects.filter(estado='pendiente').count()
    en_proceso         = Solicitud.objects.filter(estado='proceso').count()
    finalizadas        = Solicitud.objects.filter(estado='finalizado').count()
    recientes          = Solicitud.objects.select_related(
                            'cliente', 'equipo'
                         ).order_by('-creado_en')[:5]
    tecnicos           = Usuario.objects.filter(rol='tec')

    context = {
        'total_solicitudes': total_solicitudes,
        'pendientes':        pendientes,
        'en_proceso':        en_proceso,
        'finalizadas':       finalizadas,
        'recientes':         recientes,
        'tecnicos':          tecnicos,
    }
    return render(request, 'core/dashboard.html', context)

    from django.contrib import messages
from .forms import ClienteForm


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
            form.save()
            messages.success(request, 'Cliente registrado correctamente.')
            return redirect('consultar_clientes')
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
    if request.method == 'POST':
        form = EquipoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Equipo registrado correctamente.')
            return redirect('consultar_equipos')
    else:
        form = EquipoForm()
    return render(request, 'core/equipos/registrar.html', {'form': form})

    from .models import (Usuario, Cliente, Equipo, Solicitud,
                     DetalleSolicitud, HistorialEstado)
import datetime


# ── MOTOR DE ESTIMACIÓN DE TIEMPO ─────────────────────────────
def calcular_tiempo_estimado(tipo, prioridad, fecha_ingreso):
    # Tiempos en horas según tipo y prioridad
    tiempos_horas = {
        'preventivo': {'alta': 1, 'media': 2,  'baja': 3},
        'revision':   {'alta': 1, 'media': 1,  'baja': 2},
        'software':   {'alta': 2, 'media': 2,  'baja': 3},
        'hardware':   {'alta': 1, 'media': 3,  'baja': 5},
    }
    horas = tiempos_horas.get(tipo, {}).get(prioridad, 3)
    tiempo_texto = f"{horas} hora(s)"

    return 0, fecha_ingreso, tiempo_texto


# ── REGISTRAR SOLICITUD ────────────────────────────────────────
@login_required(login_url='login')
def registrar_solicitud(request):
    if request.user.rol == 'tec':
        return redirect('consultar_solicitudes')
    if request.method == 'POST':
        form = SolicitudForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            # Validar que el equipo pertenezca al cliente
            if solicitud.equipo.cliente != solicitud.cliente:
                form.add_error('equipo',
                    'El equipo seleccionado no pertenece al cliente elegido.')
                return render(request, 'core/solicitudes/registrar.html',
                              {'form': form})
            # Validar solicitud duplicada
            duplicada = Solicitud.objects.filter(
                cliente    = solicitud.cliente,
                equipo     = solicitud.equipo,
                estado__in = ['pendiente', 'proceso']
            ).exists()
            if duplicada:
                form.add_error(None,
                    f'Ya existe una solicitud activa para {solicitud.cliente.nombre} '
                    f'con el equipo {solicitud.equipo.marca} {solicitud.equipo.modelo}. '
                    f'Finaliza esa solicitud antes de crear una nueva.')
                return render(request, 'core/solicitudes/registrar.html',
                              {'form': form})
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
            return redirect('consultar_solicitudes')
    else:
        form = SolicitudForm()
    return render(request, 'core/solicitudes/registrar.html', {'form': form})


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
    return render(request, 'core/solicitudes/cambiar_estado.html', {
        'form':      form,
        'solicitud': solicitud,
    })


# ── ASIGNAR TÉCNICO ────────────────────────────────────────────
@login_required(login_url='login')
def asignar_tecnico(request, pk):
    solicitud = Solicitud.objects.get(pk=pk)
    detalle, _ = DetalleSolicitud.objects.get_or_create(solicitud=solicitud)
    if request.method == 'POST':
        form = AsignarTecnicoForm(request.POST)
        if form.is_valid():
            detalle.tecnico = form.cleaned_data['tecnico']
            detalle.save()
            messages.success(request, 'Técnico asignado correctamente.')
            return redirect('detalle_solicitud', pk=pk)
    else:
        form = AsignarTecnicoForm()
    return render(request, 'core/solicitudes/asignar_tecnico.html', {
        'form':      form,
        'solicitud': solicitud,
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

    # ── REPORTES ───────────────────────────────────────────────────
@login_required(login_url='login')
def reportes(request):
    if request.user.rol not in ['admin', 'recep']:
        return redirect('dashboard')

    # Estadísticas generales
    total_sol      = Solicitud.objects.count()
    pendientes     = Solicitud.objects.filter(estado='pendiente').count()
    en_proceso     = Solicitud.objects.filter(estado='proceso').count()
    finalizadas    = Solicitud.objects.filter(estado='finalizado').count()
    entregadas     = Solicitud.objects.filter(estado='entregado').count()

    # Solicitudes por tipo
    tipos = {}
    for t, label in Solicitud.TIPOS_REP:
        tipos[label] = Solicitud.objects.filter(tipo_reparacion=t).count()

    # Solicitudes por técnico
    tecnicos = Usuario.objects.filter(rol='tec')
    carga_tecnicos = []
    for tec in tecnicos:
        cant = DetalleSolicitud.objects.filter(tecnico=tec).count()
        carga_tecnicos.append({
            'nombre': tec.get_full_name() or tec.username,
            'cantidad': cant,
        })

    # Ingresos totales
    from .models import Costo
    costos = Costo.objects.all()
    total_ingresos   = sum(c.total for c in costos)
    total_mano_obra  = sum(c.mano_obra for c in costos)

    # Tiempos promedio
    sols_con_tiempo = Solicitud.objects.filter(
        dias_estimados__isnull=False)
    if sols_con_tiempo.exists():
        promedio_dias = sum(
            s.dias_estimados for s in sols_con_tiempo
        ) / sols_con_tiempo.count()
    else:
        promedio_dias = 0

    # Solicitudes recientes
    recientes = Solicitud.objects.select_related(
        'cliente', 'equipo', 'detalle__tecnico'
    ).order_by('-creado_en')[:10]

    return render(request, 'core/reportes/index.html', {
        'total_sol':      total_sol,
        'pendientes':     pendientes,
        'en_proceso':     en_proceso,
        'finalizadas':    finalizadas,
        'entregadas':     entregadas,
        'tipos':          tipos,
        'carga_tecnicos': carga_tecnicos,
        'total_ingresos': total_ingresos,
        'total_mano_obra':total_mano_obra,
        'promedio_dias':  round(promedio_dias, 1),
        'recientes':      recientes,
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