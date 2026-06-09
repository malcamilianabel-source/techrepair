from django import forms
from .models import Cliente, Equipo, Solicitud, Usuario, DetalleSolicitud, Avance

# ── FORMULARIO CLIENTE ─────────────────────────────────────────
class ClienteForm(forms.ModelForm):
    class Meta:
        model  = Cliente
        fields = ['nombre', 'apellido', 'dni', 'telefono', 'direccion', 'correo']
        widgets = {
            'nombre':    forms.TextInput(attrs={
                'class':'fc', 'placeholder':'Juan Carlos'}),
            'apellido':  forms.TextInput(attrs={
                'class':'fc', 'placeholder':'Pérez Ríos'}),
            'dni':       forms.TextInput(attrs={
                'class':'fc', 'placeholder':'12345678',
                'maxlength':'8', 'inputmode':'numeric',
                'pattern': '[0-9]{8}'}),
            'telefono':  forms.TextInput(attrs={
                'class':'fc', 'placeholder':'987654321',
                'maxlength':'9', 'inputmode':'numeric',
                'pattern': '9[0-9]{8}'}),
            'direccion': forms.TextInput(attrs={
                'class':'fc', 'placeholder':'Av. Principal 123, Lima'}),
            'correo':    forms.EmailInput(attrs={
                'class':'fc', 'placeholder':'cliente@correo.com'}),
        }
        labels = {
            'nombre':    'Nombres',
            'apellido':  'Apellidos',
            'dni':       'DNI',
            'telefono':  'Teléfono',
            'direccion': 'Dirección',
            'correo':    'Correo electrónico',
        }

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI solo debe contener números.')
        if len(dni) != 8:
            raise forms.ValidationError('El DNI debe tener exactamente 8 dígitos.')
        return dni

    def clean_telefono(self):
        tel = self.cleaned_data.get('telefono', '')
        if not tel.isdigit():
            raise forms.ValidationError('El teléfono solo debe contener números.')
        if not tel.startswith('9'):
            raise forms.ValidationError('El teléfono debe empezar con 9.')
        if len(tel) != 9:
            raise forms.ValidationError('El teléfono debe tener 9 dígitos.')
        return tel


# ── FORMULARIO EQUIPO ──────────────────────────────────────────
class EquipoForm(forms.ModelForm):
    tipo_personalizado = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'fc', 'placeholder': 'Especifica el tipo de equipo...'}),
        label='Especifica el tipo')
    marca_personalizada = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'fc', 'placeholder': 'Especifica la marca...'}),
        label='Especifica la marca')

    class Meta:
        model  = Equipo
        fields = ['cliente', 'tipo', 'tipo_personalizado',
                  'marca', 'marca_personalizada',
                  'modelo', 'serie', 'estado', 'falla']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'fc'}),
            'tipo':    forms.Select(attrs={'class': 'fc', 'id': 'id_tipo'}),
            'marca':   forms.Select(attrs={'class': 'fc', 'id': 'id_marca'}),
            'modelo':  forms.TextInput(attrs={
                'class': 'fc', 'placeholder': 'Ej: Pavilion 15-eh2037la'}),
            'serie':   forms.TextInput(attrs={
                'class': 'fc', 'placeholder': 'SN-XXXXXXXXX'}),
            'estado':  forms.Select(attrs={'class': 'fc'}),
            'falla':   forms.Textarea(attrs={
                'class': 'fc', 'placeholder': 'Describe el problema reportado...'}),
        }
        labels = {
            'cliente': 'Cliente propietario',
            'tipo':    'Tipo de equipo',
            'marca':   'Marca',
            'modelo':  'Modelo',
            'serie':   'Número de serie',
            'estado':  'Estado físico',
            'falla':   'Falla reportada',
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('tipo') == 'otro' and not cleaned.get('tipo_personalizado'):
            self.add_error('tipo_personalizado', 'Debes especificar el tipo de equipo.')
        if cleaned.get('marca') == 'otro' and not cleaned.get('marca_personalizada'):
            self.add_error('marca_personalizada', 'Debes especificar la marca.')
        return cleaned


# ── FORMULARIO SOLICITUD ───────────────────────────────────────
class SolicitudForm(forms.ModelForm):
    class Meta:
        model  = Solicitud
        fields = ['cliente', 'equipo', 'tipo_reparacion',
                  'descripcion', 'observaciones', 'prioridad']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'fc'}),
            'equipo':  forms.Select(attrs={'class': 'fc'}),
            'tipo_reparacion': forms.Select(attrs={'class': 'fc'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'fc',
                'placeholder': 'Describe detalladamente el problema...'}),
            'observaciones': forms.Textarea(attrs={
                'class': 'fc',
                'placeholder': 'Indicaciones especiales del cliente...',
                'style': 'min-height:60px;'}),
            'prioridad': forms.Select(attrs={'class': 'fc'}),
        }
        labels = {
            'cliente':        'Cliente',
            'equipo':         'Equipo del cliente',
            'tipo_reparacion':'Tipo de reparación',
            'descripcion':    'Descripción del problema',
            'observaciones':  'Observaciones del cliente',
            'prioridad':      'Prioridad',
        }

    def clean_tipo_reparacion(self):
        valor = self.cleaned_data.get('tipo_reparacion')
        if not valor:
            raise forms.ValidationError('Debes seleccionar un tipo de reparación.')
        return valor


# ── FORMULARIO CAMBIAR ESTADO ──────────────────────────────────
class CambiarEstadoForm(forms.Form):
    ESTADOS_ADMIN = [
        ('pendiente',  'Pendiente'),
        ('proceso',    'En proceso'),
        ('finalizado', 'Finalizado'),
        ('entregado',  'Entregado'),
    ]
    ESTADOS_TEC = [
        ('pendiente',  'Pendiente'),
        ('proceso',    'En proceso'),
        ('finalizado', 'Finalizado'),
    ]
    estado      = forms.ChoiceField(
        choices=ESTADOS_ADMIN,
        widget=forms.Select(attrs={'class': 'fc'}),
        label='Nuevo estado')
    observacion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'fc',
            'placeholder': 'Describe el motivo del cambio...',
            'style': 'min-height:70px;'}),
        label='Observación')


# ── FORMULARIO ASIGNAR TÉCNICO ─────────────────────────────────
class AsignarTecnicoForm(forms.Form):
    tecnico = forms.ModelChoiceField(
        queryset=Usuario.objects.filter(rol='tec'),
        widget=forms.HiddenInput()
    )


# ── FORMULARIO USUARIO ─────────────────────────────────────────
class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'fc', 'placeholder': 'Contraseña'}),
        label='Contraseña'
    )
    especialidad_otro = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'fc',
            'placeholder': 'Especifica la especialidad...',
            'id': 'id_especialidad_otro',
        }),
        label='¿Cuál especialidad?'
    )

    class Meta:
        model  = Usuario
        fields = ['username', 'first_name', 'last_name', 'email',
                  'password', 'rol', 'especialidad', 'especialidad_otro']
        widgets = {
            'username':   forms.TextInput(attrs={'class': 'fc'}),
            'first_name': forms.TextInput(attrs={'class': 'fc'}),
            'last_name':  forms.TextInput(attrs={'class': 'fc'}),
            'email':      forms.EmailInput(attrs={'class': 'fc'}),
            'rol':        forms.Select(attrs={'class': 'fc'}),
            'especialidad': forms.Select(attrs={'class': 'fc', 'id': 'id_especialidad'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if self.cleaned_data.get('especialidad') != 'otro':
            user.especialidad_otro = ''
        if commit:
            user.save()
        return user

# ── FORMULARIO DIAGNÓSTICO ─────────────────────────────────────
class DiagnosticoForm(forms.ModelForm):
    class Meta:
        model  = DetalleSolicitud
        fields = ['diagnostico', 'causa_probable',
                  'componentes', 'trabajo_realizado', 'recomendaciones']
        widgets = {
            'diagnostico': forms.Textarea(attrs={
                'class': 'fc',
                'placeholder': 'Describe las fallas detectadas durante la inspección...'}),
            'causa_probable': forms.Textarea(attrs={
                'class': 'fc',
                'placeholder': 'Ej: Corto circuito por humedad, desgaste por uso...',
                'style': 'min-height:70px;'}),
            'componentes': forms.TextInput(attrs={
                'class': 'fc',
                'placeholder': 'Ej: Placa madre, RAM, Panel LCD...'}),
            'trabajo_realizado': forms.Textarea(attrs={
                'class': 'fc',
                'placeholder': 'Describe el trabajo realizado...',
                'style': 'min-height:70px;'}),
            'recomendaciones': forms.Textarea(attrs={
                'class': 'fc',
                'placeholder': 'Recomendaciones para el cliente...',
                'style': 'min-height:70px;'}),
        }
        labels = {
            'diagnostico':      'Fallas detectadas',
            'causa_probable':   'Causa probable',
            'componentes':      'Componentes afectados',
            'trabajo_realizado':'Trabajo realizado',
            'recomendaciones':  'Recomendaciones',
        }


# ── FORMULARIO AVANCE ──────────────────────────────────────────
class AvanceForm(forms.ModelForm):
    class Meta:
        model  = Avance
        fields = ['etapa', 'descripcion']
        widgets = {
            'etapa': forms.Select(attrs={'class': 'fc'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'fc',
                'placeholder': 'Describe lo que se realizó en esta etapa...'}),
        }
        labels = {
            'etapa':       'Etapa de reparación',
            'descripcion': 'Descripción del avance',
        }


# ── FORMULARIO ACTUALIZAR EQUIPO ───────────────────────────────
class EquipoUpdateForm(forms.ModelForm):
    tipo_personalizado = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'fc', 'placeholder': 'Especifica el tipo de equipo...'}),
        label='Especifica el tipo')
    marca_personalizada = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'fc', 'placeholder': 'Especifica la marca...'}),
        label='Especifica la marca')

    class Meta:
        model  = Equipo
        fields = ['tipo', 'tipo_personalizado', 'marca', 'marca_personalizada',
                  'modelo', 'serie', 'estado', 'falla']
        widgets = {
            'tipo':   forms.Select(attrs={'class': 'fc', 'id': 'id_tipo'}),
            'marca':  forms.Select(attrs={'class': 'fc', 'id': 'id_marca'}),
            'modelo': forms.TextInput(attrs={
                'class': 'fc', 'placeholder': 'Ej: Pavilion 15-eh2037la'}),
            'serie':  forms.TextInput(attrs={
                'class': 'fc', 'placeholder': 'SN-XXXXXXXXX'}),
            'estado': forms.Select(attrs={'class': 'fc'}),
            'falla':  forms.Textarea(attrs={
                'class': 'fc', 'placeholder': 'Describe el problema reportado...'}),
        }
        labels = {
            'tipo':    'Tipo de equipo',
            'marca':   'Marca',
            'modelo':  'Modelo',
            'serie':   'Número de serie',
            'estado':  'Estado físico',
            'falla':   'Falla reportada',
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('tipo') == 'otro' and not cleaned.get('tipo_personalizado'):
            self.add_error('tipo_personalizado', 'Debes especificar el tipo de equipo.')
        if cleaned.get('marca') == 'otro' and not cleaned.get('marca_personalizada'):
            self.add_error('marca_personalizada', 'Debes especificar la marca.')
        return cleaned

        # ── FORMULARIO AMPLIACIÓN DE TIEMPO ───────────────────────────
class AmpliacionTiempoForm(forms.Form):
    cantidad = forms.IntegerField(
        min_value=1, max_value=999,
        label='Tiempo adicional',
        widget=forms.NumberInput(attrs={
            'class': 'fc',
            'placeholder': 'Ej: 2',
        })
    )
    unidad = forms.ChoiceField(
        choices=[('horas', 'Horas'), ('minutos', 'Minutos')],
        label='Unidad',
        widget=forms.Select(attrs={'class': 'fc'})
    )
    justificacion = forms.CharField(
        label='Justificación',
        widget=forms.Textarea(attrs={
            'class': 'fc',
            'rows': 4,
            'placeholder': 'Explica el motivo por el que necesitas más tiempo...',
        })
    )