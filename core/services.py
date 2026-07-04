"""
Lógica de negocio pura de TechRepair (sin request/render/redirect).

Contiene el motor de estimación de tiempos de reparación y el cálculo
de fechas dentro del horario laboral del taller.
"""
import datetime
import math

# ── HORARIO LABORAL ────────────────────────────────────────────
HORA_INICIO = 9   # 9am
HORA_FIN    = 22  # 10pm


def _siguiente_dia_laboral(fecha):
    """Avanza la fecha al siguiente día que no sea sábado (5) ni domingo (6)."""
    siguiente = fecha + datetime.timedelta(days=1)
    while siguiente.weekday() >= 5:
        siguiente += datetime.timedelta(days=1)
    return siguiente


def calcular_fecha_libre_laboral(now, total_horas):
    """Distribuye total_horas dentro del horario 9am-10pm, saltando fines de semana."""
    hora_actual = now.hour + now.minute / 60

    if hora_actual < HORA_INICIO:
        inicio = now.replace(hour=HORA_INICIO, minute=0, second=0, microsecond=0)
    elif hora_actual >= HORA_FIN or now.weekday() >= 5:
        inicio = datetime.datetime.combine(
            _siguiente_dia_laboral(now.date()),
            datetime.time(HORA_INICIO, 0)
        )
    else:
        inicio = now

    current         = inicio
    horas_restantes = total_horas

    while horas_restantes > 0:
        # Si el día actual es fin de semana, saltar al siguiente día laboral
        while current.weekday() >= 5:
            current = datetime.datetime.combine(
                _siguiente_dia_laboral(current.date()),
                datetime.time(HORA_INICIO, 0)
            )

        fin_dia   = current.replace(hour=HORA_FIN, minute=0, second=0, microsecond=0)
        horas_hoy = (fin_dia - current).total_seconds() / 3600

        if horas_restantes <= horas_hoy:
            current = current + datetime.timedelta(hours=horas_restantes)
            break
        else:
            horas_restantes -= horas_hoy
            current = datetime.datetime.combine(
                _siguiente_dia_laboral(current.date()),
                datetime.time(HORA_INICIO, 0)
            )

    return current


# ── MOTOR DE ESTIMACIÓN DE TIEMPO ─────────────────────────────
def calcular_tiempo_estimado(tipo, estado_fisico, fecha_ingreso):
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
