import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser



# ── MODELO 1: USUARIO ──────────────────────────────────────────
class Usuario(AbstractUser):
    ROLES = [
        ('admin', 'Administrador'),
        ('recep', 'Recepcionista'),
        ('tec',   'Técnico'),
    ]
    rol      = models.CharField(max_length=10, choices=ROLES, default='tec')
    ESPECIALIDADES = [
    ('general',     'General'),
    ('electronica', 'Reparación Electrónica'),
    ('hardware',    'Hardware'),
    ('software',    'Software'),
    ('redes',       'Redes y Conectividad'),
    ('otro',        'Otro'),
    ]
    especialidad       = models.CharField(max_length=20, choices=ESPECIALIDADES, default='general')
    especialidad_otro  = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=9, blank=True)
    dni      = models.CharField(max_length=8, blank=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_rol_display()})"


# ── MODELO 2: CLIENTE ──────────────────────────────────────────
class Cliente(models.Model):
    nombre    = models.CharField(max_length=100)
    apellido  = models.CharField(max_length=100, default='', blank=True)
    dni       = models.CharField(max_length=8, unique=True)
    telefono  = models.CharField(max_length=9)
    direccion = models.CharField(max_length=200, blank=True)
    correo    = models.EmailField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.nombre_completo} (DNI: {self.dni})"


# ── MODELO 3: EQUIPO ───────────────────────────────────────────
class Equipo(models.Model):
    TIPOS = [
        ('laptop',     'Laptop'),
        ('pc',         'PC de escritorio'),
        ('impresora',  'Impresora'),
        ('tablet',     'Tablet'),
        ('monitor',    'Monitor'),
        ('otro',       'Otro'),
    ]
    ESTADO_FISICO = [
        ('bueno',   'Bueno'),
        ('regular', 'Regular'),
        ('malo',    'Malo'),
    ]
    cliente    = models.ForeignKey(Cliente, on_delete=models.PROTECT,
                                   related_name='equipos')
    tipo       = models.CharField(max_length=20, choices=TIPOS)
    MARCAS = [
    ('hp',      'HP'),
    ('dell',    'Dell'),
    ('lenovo',  'Lenovo'),
    ('asus',    'Asus'),
    ('acer',    'Acer'),
    ('apple',   'Apple'),
    ('samsung', 'Samsung'),
    ('toshiba', 'Toshiba'),
    ('sony',    'Sony'),
    ('lg',      'LG'),
    ('epson',   'Epson'),
    ('canon',   'Canon'),
    ('otro',    'Otra'),
    ]
    marca      = models.CharField(max_length=20, choices=MARCAS)
    modelo     = models.CharField(max_length=100)
    serie      = models.CharField(max_length=100, unique=True)
    estado     = models.CharField(max_length=10, choices=ESTADO_FISICO,
                                   default='regular')
    falla      = models.TextField(blank=True)
    tipo_personalizado  = models.CharField(max_length=100, blank=True, default='')
    marca_personalizada = models.CharField(max_length=100, blank=True, default='')
    creado_en  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.get_tipo_display()} | {self.marca} {self.modelo} — {self.cliente.nombre}"


# ── MODELO 4: SOLICITUD ────────────────────────────────────────
class Solicitud(models.Model):
    ESTADOS = [
        ('pendiente',  'Pendiente'),
        ('proceso',    'En proceso'),
        ('finalizado', 'Finalizado'),
        ('entregado',  'Entregado'),
    ]
    PRIORIDADES = [
        ('alta',  'Alta'),
        ('media', 'Media'),
        ('baja',  'Baja'),
    ]
    TIPOS_REP = [
        ('hardware',   'Hardware'),
        ('software',   'Software'),
        ('preventivo', 'Mantenimiento preventivo'),
        ('revision',   'Revisión diagnóstica'),
    ]
    cliente          = models.ForeignKey(Cliente, on_delete=models.PROTECT,
                                          related_name='solicitudes')
    equipo           = models.ForeignKey(Equipo, on_delete=models.PROTECT,
                                          related_name='solicitudes')
    tipo_reparacion  = models.CharField(max_length=20, choices=TIPOS_REP)
                                         
    descripcion      = models.TextField()
    observaciones    = models.TextField(blank=True)
    prioridad        = models.CharField(max_length=10, choices=PRIORIDADES,
                                         default='media')
    estado           = models.CharField(max_length=15, choices=ESTADOS,
                                         default='pendiente', db_index=True)
    es_prioritaria    = models.BooleanField(default=False)
    prioridad_anterior= models.CharField(max_length=10, blank=True, default='')
    fecha_ingreso     = models.DateField(auto_now_add=True)
    dias_estimados        = models.IntegerField(null=True, blank=True)
    fecha_estimada        = models.DateField(null=True, blank=True)
    fecha_hora_estimada   = models.DateTimeField(null=True, blank=True)
    tiempo_estimado_texto = models.CharField(max_length=50, blank=True, default='')
    tiempo_estimado_horas = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    fecha_entrega        = models.DateField(null=True, blank=True)
    hora_entrega         = models.TimeField(null=True, blank=True)
    observaciones_entrega= models.TextField(blank=True, default='')
    confirmacion_cliente = models.BooleanField(default=False)
    creado_en        = models.DateTimeField(auto_now_add=True)
    token_seguimiento = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"#{self.id} — {self.cliente.nombre} ({self.get_estado_display()})"


# ── MODELO 5: DETALLE SOLICITUD ────────────────────────────────
class DetalleSolicitud(models.Model):
    solicitud        = models.OneToOneField(Solicitud, on_delete=models.CASCADE,
                                             related_name='detalle')
    tecnico          = models.ForeignKey(Usuario, on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='detalles')
    diagnostico      = models.TextField(blank=True)
    causa_probable   = models.TextField(blank=True)
    componentes      = models.CharField(max_length=200, blank=True)
    trabajo_realizado= models.TextField(blank=True)
    recomendaciones  = models.TextField(blank=True)
    actualizado_en   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Detalle de solicitud #{self.solicitud.id}"


# ── MODELO 6: AVANCE / BITÁCORA ────────────────────────────────
class Avance(models.Model):
    ETAPAS = [
        ('diagnostico', 'Diagnóstico inicial'),
        ('desmontaje',  'Desmontaje'),
        ('reparacion',  'Reparación'),
        ('prueba',      'Prueba de funcionamiento'),
        ('ensamblaje',  'Ensamblaje'),
        ('prueba_final','Prueba final'),
    ]
    TIPOS = [
        ('etapa', 'Avance de etapa'),
        ('nota',  'Nota / comentario'),
    ]
    solicitud   = models.ForeignKey(Solicitud, on_delete=models.CASCADE,
                                     related_name='avances')
    usuario     = models.ForeignKey(Usuario, on_delete=models.SET_NULL,
                                     null=True, related_name='avances')
    tipo        = models.CharField(max_length=10, choices=TIPOS, default='etapa')
    etapa       = models.CharField(max_length=20, choices=ETAPAS, blank=True, default='')
    descripcion = models.TextField()
    visible_cliente = models.BooleanField(default=False)
    fecha_hora  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_hora']

    def __str__(self):
        return f"{self.get_etapa_display()} — #{self.solicitud.id}"


# ── MODELO 7: REPUESTO ─────────────────────────────────────────
class Repuesto(models.Model):
    solicitud     = models.ForeignKey(Solicitud, on_delete=models.CASCADE,
                                       related_name='repuestos')
    nombre        = models.CharField(max_length=150)
    cantidad      = models.PositiveIntegerField(default=1)
    precio_unit   = models.DecimalField(max_digits=8, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unit

    def __str__(self):
        return f"{self.nombre} x{self.cantidad}"


# ── MODELO 8: COSTO ────────────────────────────────────────────
class Costo(models.Model):
    solicitud    = models.OneToOneField(Solicitud, on_delete=models.CASCADE,
                                         related_name='costo')
    mano_obra    = models.DecimalField(max_digits=8, decimal_places=2,
                                        default=0)
    total        = models.DecimalField(max_digits=8, decimal_places=2,
                                        default=0)
    registrado_en= models.DateTimeField(auto_now_add=True)

    def calcular_total(self):
        from decimal import Decimal
        from django.db.models import Sum, F
        agg = self.solicitud.repuestos.aggregate(
            total_rep=Sum(F('cantidad') * F('precio_unit'))
        )
        total_rep = agg['total_rep'] or Decimal('0')
        self.total = (self.mano_obra or Decimal('0')) + total_rep
        self.save(update_fields=['total'])
    def __str__(self):
        return f"Costo #{self.solicitud.id} — S/. {self.total}"


# ── MODELO 9: HISTORIAL DE ESTADO ─────────────────────────────
class HistorialEstado(models.Model):
    solicitud    = models.ForeignKey(Solicitud, on_delete=models.CASCADE,
                                      related_name='historial')
    usuario      = models.ForeignKey(Usuario, on_delete=models.SET_NULL,
                                      null=True, related_name='historial')
    estado_antes = models.CharField(max_length=15)
    estado_nuevo = models.CharField(max_length=15)
    observacion  = models.TextField(blank=True)
    fecha_hora   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_hora']

    def __str__(self):
        return f"#{self.solicitud.id}: {self.estado_antes} → {self.estado_nuevo}"


# ── MODELO 10: NOTIFICACIÓN ────────────────────────────────────
class Notificacion(models.Model):
    MEDIOS = [
        ('correo', 'Correo electrónico'),
        ('sms',    'SMS'),
    ]
    solicitud  = models.ForeignKey(Solicitud, on_delete=models.CASCADE,
                                    related_name='notificaciones')
    medio      = models.CharField(max_length=10, choices=MEDIOS,
                                   default='correo')
    mensaje    = models.TextField()
    enviado    = models.BooleanField(default=False)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notif. #{self.solicitud.id} — {self.get_medio_display()}"

        # ── MODELO 11: AMPLIACIÓN DE TIEMPO ───────────────────────────
class AmpliacionTiempo(models.Model):
    UNIDADES = [
        ('horas',   'Horas'),
        ('minutos', 'Minutos'),
    ]
    solicitud     = models.ForeignKey(Solicitud, on_delete=models.CASCADE,
                                       related_name='ampliaciones')
    tecnico       = models.ForeignKey(Usuario, on_delete=models.SET_NULL,
                                       null=True, related_name='ampliaciones')
    cantidad      = models.PositiveIntegerField()
    unidad        = models.CharField(max_length=10, choices=UNIDADES)
    justificacion = models.TextField()
    fecha_hora    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Ampliación #{self.solicitud.id}: +{self.cantidad} {self.unidad}'