"""Vistas del trabajo del técnico: diagnóstico, bitácora, repuestos, costos, informe."""
import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..decorators import tecnico_asignado_o_staff
from ..forms import (
    AmpliacionTiempoForm, AvanceForm, CostoForm, DiagnosticoForm,
    NotaBitacoraForm, RepuestoForm,
)
from ..models import (
    AmpliacionTiempo, Avance, Costo, DetalleSolicitud, HistorialEstado,
    Solicitud, Usuario,
)
from .helpers import ETAPA_ORDEN


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


# ── INFORME PDF ────────────────────────────────────────────────
@login_required
def informe_pdf(request, pk):
    if request.user.rol not in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA):
        messages.error(request, 'No tienes permiso para generar informes.')
        return redirect('detalle_solicitud', pk=pk)

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


# ── AMPLIACIÓN DE TIEMPO ────────────────────────────────────────
@login_required
def solicitar_ampliacion(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)

    if request.user.rol == Usuario.Rol.TECNICO:
        try:
            if solicitud.detalle.tecnico != request.user:
                messages.error(request, 'Solo el técnico asignado puede solicitar ampliación.')
                return redirect('detalle_solicitud', pk=pk)
        except (DetalleSolicitud.DoesNotExist, AttributeError):
            messages.error(request, 'Esta solicitud no tiene técnico asignado.')
            return redirect('detalle_solicitud', pk=pk)
    elif request.user.rol not in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.TECNICO):
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
