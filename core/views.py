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
    if request.method == 'POST':
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