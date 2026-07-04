from django.urls import path
from . import views

urlpatterns = [
    # ── AUTH ──
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ── DASHBOARD ──
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── CLIENTES ──
    path('clientes/', views.consultar_clientes, name='consultar_clientes'),
    path('clientes/registrar/', views.registrar_cliente, name='registrar_cliente'),
    path('clientes/actualizar/<int:pk>/', views.actualizar_cliente, name='actualizar_cliente'),
    path('clientes/<int:pk>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),
    path('clientes/<int:pk>/historial/', views.historial_cliente, name='historial_cliente'),
    

    # ── EQUIPOS ──
    path('equipos/', views.consultar_equipos, name='consultar_equipos'),
    path('equipos/registrar/', views.registrar_equipo, name='registrar_equipo'),
    path('equipos/<int:pk>/actualizar/', views.actualizar_equipo, name='actualizar_equipo'),
    path('equipos/<int:pk>/historial/', views.historial_equipo, name='historial_equipo'),
    path('equipos/<int:pk>/eliminar/',   views.eliminar_equipo,  name='eliminar_equipo'),

    # ── SOLICITUDES ──
    path('solicitudes/', views.consultar_solicitudes, name='consultar_solicitudes'),
    path('solicitudes/registrar/', views.registrar_solicitud, name='registrar_solicitud'),
    path('solicitudes/<int:pk>/', views.detalle_solicitud, name='detalle_solicitud'),
    path('solicitudes/<int:pk>/estado/', views.cambiar_estado, name='cambiar_estado'),
    path('solicitudes/<int:pk>/tecnico/', views.asignar_tecnico, name='asignar_tecnico'),
    path('solicitudes/<int:pk>/diagnostico/', views.diagnostico, name='diagnostico'),
    path('solicitudes/<int:pk>/avance/', views.avance, name='avance'),
    path('solicitudes/<int:pk>/repuestos/', views.repuestos, name='repuestos'),
    path('solicitudes/<int:pk>/costos/', views.costos, name='costos'),
    path('solicitudes/<int:pk>/entrega/', views.entrega, name='entrega'),
    path('solicitudes/<int:pk>/pdf/', views.informe_pdf, name='informe_pdf'),
    path('solicitudes/<int:pk>/eliminar/', views.eliminar_solicitud, name='eliminar_solicitud'),
    path('solicitudes/<int:pk>/prioritaria/', views.marcar_prioritaria, name='marcar_prioritaria'),
    path('solicitudes/<int:pk>/quitar-prioritaria/', views.quitar_prioritaria, name='quitar_prioritaria'),
    path('solicitudes/<int:pk>/reasignar/', views.reasignar_tecnico, name='reasignar_tecnico'),
    path('solicitudes/<int:pk>/ampliacion/', views.solicitar_ampliacion, name='solicitar_ampliacion'),

    # ── USUARIOS ──
    path('usuarios/registrar/', views.registrar_usuario, name='registrar_usuario'),
    path('usuarios/consultar/', views.consultar_usuarios, name='consultar_usuarios'),
    path('usuarios/<int:pk>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),

    # ── REPORTES ──
    path('reportes/', views.reportes, name='reportes'),
    path('reportes/solicitudes/', views.reporte_solicitudes, name='reporte_solicitudes'),
    path('reportes/solicitudes/pdf/', views.reporte_solicitudes_pdf, name='reporte_solicitudes_pdf'),
    path('reportes/tiempos/', views.reporte_tiempos, name='reporte_tiempos'),
    path('reportes/tiempos/pdf/', views.reporte_tiempos_pdf, name='reporte_tiempos_pdf'),
    path('reportes/ingresos/', views.reporte_ingresos, name='reporte_ingresos'),
    path('reportes/ingresos/pdf/', views.reporte_ingresos_pdf, name='reporte_ingresos_pdf'),

    # ── SEGUIMIENTO PÚBLICO ──
    path('seguimiento/<uuid:token>/', views.seguimiento, name='seguimiento'),

    # ── AJAX ──
    path('api/equipos/<int:cliente_id>/', views.equipos_por_cliente, name='equipos_por_cliente'),

    
]