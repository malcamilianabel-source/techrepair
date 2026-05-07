from django import forms
from .models import Cliente, Equipo, Solicitud, Usuario, DetalleSolicitud, Avance

# ── FORMULARIO CLIENTE ─────────────────────────────────────────
class ClienteForm(forms.ModelForm):
    class Meta:
        model  = Cliente
        fields = ['nombre', 'dni', 'telefono', 'direccion', 'correo']
        widgets = {
            'nombre':    forms.TextInput(attrs={
                'class':'fc', 'placeholder':'Juan Carlos Pérez Ríos'}),
            'dni':       forms.TextInput(attrs={
                'class':'fc', 'placeholder':'12345678', 'maxlength':'8'}),
            'telefono':  forms.TextInput(attrs={
                'class':'fc', 'placeholder':'987654321', 'maxlength':'9'}),
            'direccion': forms.TextInput(attrs={
                'class':'fc', 'placeholder':'Av. Principal 123, Lima'}),
            'correo':    forms.EmailInput(attrs={
                'class':'fc', 'placeholder':'cliente@correo.com'}),
        }
        labels = {
            'nombre':    'Nombre completo',
            'dni':       'DNI',
            'telefono':  'Teléfono',
            'direccion': 'Dirección',
            'correo':    'Correo electrónico',
        }

        # ── FORMULARIO EQUIPO ──────────────────────────────────────────
class EquipoForm(forms.ModelForm):
    class Meta:
        model  = Equipo
        fields = ['cliente', 'tipo', 'marca', 'modelo',
                  'serie', 'estado', 'falla']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'fc'}),
            'tipo':    forms.Select(attrs={'class': 'fc'}),
            'marca':   forms.Select(attrs={'class': 'fc'}),
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


# ── FORMULARIO CAMBIAR ESTADO ──────────────────────────────────
class CambiarEstadoForm(forms.Form):
    ESTADOS = [
        ('pendiente',  'Pendiente'),
        ('proceso',    'En proceso'),
        ('finalizado', 'Finalizado'),
        ('entregado',  'Entregado'),
    ]
    estado      = forms.ChoiceField(
        choices=ESTADOS,
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
        queryset=None,
        widget=forms.Select(attrs={'class': 'fc'}),
        label='Seleccionar técnico')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tecnico'].queryset = Usuario.objects.filter(rol='tec')


# ── FORMULARIO USUARIO ─────────────────────────────────────────
class UsuarioForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'fc', 'placeholder': 'Mínimo 8 caracteres'}))
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'fc', 'placeholder': 'Repite la contraseña'}))

    class Meta:
        model  = Usuario
        fields = ['username', 'first_name', 'last_name',
                  'email', 'telefono', 'dni', 'rol']
        widgets = {
            'username':   forms.TextInput(attrs={
                'class': 'fc', 'placeholder': 'Ej: cmendoza'}),
            'first_name': forms.TextInput(attrs={
                'class': 'fc', 'placeholder': 'Carlos'}),
            'last_name':  forms.TextInput(attrs={
                'class': 'fc', 'placeholder': 'Mendoza Ríos'}),
            'email':      forms.EmailInput(attrs={
                'class': 'fc', 'placeholder': 'usuario@taller.com'}),
            'telefono':   forms.TextInput(attrs={
                'class': 'fc', 'placeholder': '987654321'}),
            'dni':        forms.TextInput(attrs={
                'class': 'fc', 'placeholder': '12345678'}),
            'rol':        forms.Select(attrs={'class': 'fc'}),
        }
        labels = {
            'username':   'Nombre de usuario',
            'first_name': 'Nombre',
            'last_name':  'Apellido',
            'email':      'Correo electrónico',
            'telefono':   'Teléfono',
            'dni':        'DNI',
            'rol':        'Rol',
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
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