"""Vistas de reportes (HTML y PDF): solicitudes, tiempos e ingresos."""
import datetime
import io
import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.units import cm

from ..models import Costo, DetalleSolicitud, Equipo, Solicitud, Usuario
from .helpers import filtrar_por_rango, parsear_rango_fechas
from .pdf_helpers import (
    ANCHO_UTIL, crear_doc_pdf, estilos_base, formato_periodo, tabla_base,
)


# ── REPORTES — ÍNDICE ──────────────────────────────────────────
@login_required
def reportes(request):
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
        return redirect('dashboard')
    return render(request, 'core/reportes/index.html', {})


# ── REPORTE SOLICITUDES ────────────────────────────────────────
@login_required
def reporte_solicitudes(request):
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
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
    for tec in Usuario.objects.filter(rol=Usuario.Rol.TECNICO):
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
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
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
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
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
    for tec in Usuario.objects.filter(rol=Usuario.Rol.TECNICO):
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
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
        return redirect('dashboard')

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
        for tec in Usuario.objects.filter(rol=Usuario.Rol.TECNICO)
    ]
    resueltas = estados['Finalizado'] + estados['Entregado']
    tasa = round((resueltas / total * 100), 1) if total else 0

    buffer  = io.BytesIO()
    doc     = crear_doc_pdf(buffer)
    estilos = estilos_base()
    W       = ANCHO_UTIL
    alinear_izq = [('ALIGN', (0, 0), (-1, -1), 'LEFT')]

    periodo = formato_periodo(fecha_inicio, fecha_fin)

    story = [
        Paragraph('TechRepair — Reporte de Solicitudes', estilos['titulo']),
        Paragraph(f'Generado el {timezone.localdate().strftime("%d/%m/%Y")}{periodo}', estilos['subtitulo']),
        Spacer(1, 0.4*cm),
        Paragraph('RESUMEN GENERAL', estilos['seccion']),
        tabla_base([['Total solicitudes', 'Resueltas', 'Tasa de resolución'],
                    [total, resueltas, f'{tasa}%']], [W/3]*3, extra_style=alinear_izq),
        Spacer(1, 0.3*cm),
        Paragraph('POR ESTADO', estilos['seccion']),
        tabla_base([['Estado', 'Cantidad']] + list(estados.items()), [W*0.6, W*0.4],
                   extra_style=alinear_izq),
        Spacer(1, 0.3*cm),
        Paragraph('POR TIPO DE REPARACIÓN', estilos['seccion']),
        tabla_base([['Tipo', 'Cantidad']] + list(tipos.items()), [W*0.6, W*0.4],
                   extra_style=alinear_izq),
    ]
    if por_tecnico:
        story += [
            Spacer(1, 0.3*cm),
            Paragraph('POR TÉCNICO', estilos['seccion']),
            tabla_base([['Técnico', 'Solicitudes']] + por_tecnico, [W*0.6, W*0.4],
                       extra_style=alinear_izq),
        ]

    if total == 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('No hay solicitudes en el período seleccionado.', estilos['subtitulo']))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_solicitudes.pdf"'
    return response


# ── PDF REPORTE TIEMPOS ────────────────────────────────────────
@login_required
def reporte_tiempos_pdf(request):
    if request.user.rol not in [Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA]:
        return redirect('dashboard')

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

    buffer  = io.BytesIO()
    doc     = crear_doc_pdf(buffer)
    estilos = estilos_base()
    W       = ANCHO_UTIL
    centrar_datos = [('ALIGN', (1, 0), (-1, -1), 'CENTER')]

    periodo = formato_periodo(fecha_inicio, fecha_fin)

    rows = [['Tipo de reparación', 'Solicitudes', 'Prom. horas', 'Total horas']]
    for label, v in tiempos_por_tipo.items():
        rows.append([label, v['cantidad'], f"{v['promedio']}h", f"{v['total_horas']}h"])

    story = [
        Paragraph('TechRepair — Reporte de Tiempos de Reparación', estilos['titulo']),
        Paragraph(f'Generado el {timezone.localdate().strftime("%d/%m/%Y")}{periodo}', estilos['subtitulo']),
        Spacer(1, 0.4*cm),
        Paragraph('RESUMEN GENERAL', estilos['seccion']),
        tabla_base([['Total solicitudes', 'Promedio general', 'Total horas acum.'],
                    [qs.count(), f'{promedio_general}h', f'{total_horas_acum}h']], [W/3]*3,
                   extra_style=centrar_datos),
        Spacer(1, 0.3*cm),
        Paragraph('TIEMPOS POR TIPO DE REPARACIÓN', estilos['seccion']),
        tabla_base(rows, [W*0.4, W*0.2, W*0.2, W*0.2], extra_style=centrar_datos),
    ]

    if qs.count() == 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('Sin datos finalizados en el período.', estilos['subtitulo']))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_tiempos.pdf"'
    return response


# ── PDF REPORTE INGRESOS ───────────────────────────────────────
@login_required
def reporte_ingresos_pdf(request):
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
        return redirect('dashboard')

    fecha_inicio, fecha_fin, fecha_inicio_str, fecha_fin_str, error_fecha = parsear_rango_fechas(request)

    costos_qs = Costo.objects.select_related(
        'solicitud__cliente', 'solicitud__equipo', 'solicitud__detalle__tecnico'
    ).all()
    costos_qs = filtrar_por_rango(costos_qs, 'solicitud__fecha_ingreso', fecha_inicio, fecha_fin)

    agg = costos_qs.aggregate(
        total_ingresos=Sum('total'),
        total_mano_obra=Sum('mano_obra'),
    )
    total_ingresos  = agg['total_ingresos']  or Decimal('0')
    total_mano_obra = agg['total_mano_obra'] or Decimal('0')
    total_repuestos = total_ingresos - total_mano_obra
    n_costos = costos_qs.count()
    ticket_promedio = round(total_ingresos / n_costos, 2) if n_costos else 0

    ingresos_tipo = {}
    for t, label in Solicitud.TIPOS_REP:
        agg_t = costos_qs.filter(solicitud__tipo_reparacion=t).aggregate(total=Sum('total'))
        ingresos_tipo[label] = float(agg_t['total'] or 0)

    tec_ingresos = []
    for tec in Usuario.objects.filter(rol=Usuario.Rol.TECNICO):
        agg_tec = costos_qs.filter(solicitud__detalle__tecnico=tec).aggregate(total=Sum('total'))
        tec_ingresos.append((tec.get_full_name() or tec.username, float(agg_tec['total'] or 0)))
    tec_ingresos.sort(key=lambda x: x[1], reverse=True)

    buffer  = io.BytesIO()
    doc     = crear_doc_pdf(buffer)
    estilos = estilos_base()
    W       = ANCHO_UTIL

    periodo = formato_periodo(fecha_inicio, fecha_fin)

    story = [
        Paragraph('TechRepair — Reporte de Ingresos', estilos['titulo']),
        Paragraph(f'Generado el {timezone.localdate().strftime("%d/%m/%Y")}{periodo}', estilos['subtitulo']),
        Spacer(1, 0.4*cm),
        Paragraph('RESUMEN DE INGRESOS', estilos['seccion']),
        tabla_base([
            ['Total ingresos', 'Mano de obra', 'Repuestos', 'Ticket promedio'],
            [f'S/ {total_ingresos:.2f}', f'S/ {total_mano_obra:.2f}',
             f'S/ {total_repuestos:.2f}', f'S/ {ticket_promedio:.2f}'],
        ], [W/4]*4, align_right_cols=[0, 1, 2, 3]),
        Spacer(1, 0.3*cm),
        Paragraph('INGRESOS POR TIPO DE REPARACIÓN', estilos['seccion']),
        tabla_base(
            [['Tipo', 'Total (S/)']] + [[k, f'S/ {v:.2f}'] for k, v in ingresos_tipo.items()],
            [W*0.6, W*0.4], align_right_cols=[1]
        ),
    ]

    if tec_ingresos:
        story += [
            Spacer(1, 0.3*cm),
            Paragraph('INGRESOS POR TÉCNICO', estilos['seccion']),
            tabla_base(
                [['Técnico', 'Total generado (S/)']] +
                [[n, f'S/ {v:.2f}'] for n, v in tec_ingresos],
                [W*0.6, W*0.4], align_right_cols=[1]
            ),
        ]

    if costos_qs.count() == 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('Sin ingresos en el período seleccionado.', estilos['subtitulo']))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_ingresos.pdf"'
    return response
