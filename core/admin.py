from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (Usuario, Cliente, Equipo, Solicitud,
                     DetalleSolicitud, Avance, Repuesto,
                     Costo, HistorialEstado, Notificacion)
#nuevo registro
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display  = ('username', 'get_full_name', 'rol', 'email')
    list_filter   = ('rol',)
    fieldsets     = UserAdmin.fieldsets + (
        ('Datos adicionales', {'fields': ('rol', 'telefono', 'dni')}),
    )
#nuevo registro cliente
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'dni', 'telefono', 'correo')
    search_fields = ('nombre', 'dni', 'telefono')
#nuevo registro equipo
@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display  = ('marca', 'modelo', 'serie', 'tipo', 'cliente')
    search_fields = ('marca', 'modelo', 'serie')
    list_filter   = ('tipo', 'estado')
#nuevo registro equipo solicitud
@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display  = ('id', 'cliente', 'equipo', 'estado', 'prioridad', 'fecha_ingreso')
    search_fields = ('cliente__nombre',)
    list_filter   = ('estado', 'prioridad', 'tipo_reparacion')
#nuevo registro equipo Detallesolicitud

@admin.register(DetalleSolicitud)
class DetalleSolicitudAdmin(admin.ModelAdmin):
    list_display  = ('solicitud', 'tecnico')
#nuevo registro equipo avance

@admin.register(Avance)
class AvanceAdmin(admin.ModelAdmin):
    list_display  = ('solicitud', 'etapa', 'usuario', 'fecha_hora')
    list_filter   = ('etapa',)
#nuevo registro equipo repuesto

@admin.register(Repuesto)
class RepuestoAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'cantidad', 'precio_unit', 'solicitud')
#nuevo registro costo

@admin.register(Costo)
class CostoAdmin(admin.ModelAdmin):
    list_display  = ('solicitud', 'mano_obra', 'total')
#nuevo registro HistorialEstado

@admin.register(HistorialEstado)
class HistorialEstadoAdmin(admin.ModelAdmin):
    list_display  = ('solicitud', 'estado_antes', 'estado_nuevo',
                     'usuario', 'fecha_hora')

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display  = ('solicitud', 'medio', 'enviado', 'fecha_hora')
