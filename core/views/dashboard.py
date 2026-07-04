"""Dashboard por rol: técnico vs. admin/recepcionista."""
from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, IntegerField, Q, Sum, When
from django.shortcuts import render

from ..models import Solicitud, Usuario


# ── DASHBOARD ─────────────────────────────────────────────────
@login_required
def dashboard(request):
    if request.user.rol == Usuario.Rol.TECNICO:
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
        tecnicos_data = Usuario.objects.filter(rol=Usuario.Rol.TECNICO).annotate(
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
