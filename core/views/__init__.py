"""
Paquete de vistas de TechRepair, dividido por dominio.

Re-exporta todas las vistas (y las funciones de negocio usadas por tests)
para que `urls.py` y `from core import views` sigan funcionando sin cambios.
"""
from .auth import login_view, logout_view
from .dashboard import dashboard
from .clientes import (
    actualizar_cliente, consultar_clientes, eliminar_cliente,
    historial_cliente, registrar_cliente,
)
from .equipos import (
    actualizar_equipo, consultar_equipos, eliminar_equipo,
    equipos_por_cliente, historial_equipo, registrar_equipo,
)
from .solicitudes import (
    asignar_tecnico, cambiar_estado, consultar_solicitudes, detalle_solicitud,
    eliminar_solicitud, entrega, marcar_prioritaria, quitar_prioritaria,
    reasignar_tecnico, registrar_solicitud, seguimiento,
)
from .tecnico import (
    avance, costos, diagnostico, informe_pdf, repuestos, solicitar_ampliacion,
)
from .usuarios import consultar_usuarios, eliminar_usuario, registrar_usuario
from .reportes import (
    reporte_ingresos, reporte_ingresos_pdf, reporte_solicitudes,
    reporte_solicitudes_pdf, reporte_tiempos, reporte_tiempos_pdf, reportes,
)

# Helpers re-exportados por compatibilidad (tests.py importa desde core.views)
from ..services import (
    HORA_FIN, HORA_INICIO, _siguiente_dia_laboral,
    calcular_fecha_libre_laboral, calcular_tiempo_estimado,
)
from .helpers import ETAPA_ORDEN, filtrar_por_rango, paginar, parsear_rango_fechas
