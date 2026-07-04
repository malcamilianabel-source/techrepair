"""Helpers HTTP compartidos por las vistas (parseo de filtros, paginación)."""
import datetime

from django.core.paginator import Paginator

# Re-exportadas por compatibilidad: la lógica de negocio vive en core.services
from ..services import (  # noqa: F401
    HORA_INICIO, HORA_FIN,
    _siguiente_dia_laboral, calcular_fecha_libre_laboral, calcular_tiempo_estimado,
)

# ── CONSTANTES DE BITÁCORA ─────────────────────────────────────
ETAPA_ORDEN = ['diagnostico', 'desmontaje', 'reparacion', 'prueba', 'ensamblaje', 'prueba_final']


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
