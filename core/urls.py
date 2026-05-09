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

    # ── EQUIPOS ──
    path('equipos/', views.consultar_equipos, name='consultar_equipos'),
    path('equipos/registrar/', views.registrar_equipo, name='registrar_equipo'),

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

    # ── USUARIOS ──
    path('usuarios/registrar/', views.registrar_usuario, name='registrar_usuario'),

    # ── REPORTES ──
    path('reportes/', views.reportes, name='reportes'),

    # ── AJAX ──
    path('api/equipos/<int:cliente_id>/', views.equipos_por_cliente, name='equipos_por_cliente'),

    
]