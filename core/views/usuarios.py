"""Vistas de administración de usuarios (solo rol administrador)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import UsuarioForm
from ..models import DetalleSolicitud, Usuario
from .helpers import paginar


# ── REGISTRAR USUARIO ──────────────────────────────────────────
@login_required
def registrar_usuario(request):
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario registrado correctamente.')
            return redirect('registrar_usuario')
    else:
        form = UsuarioForm()
    return render(request, 'core/usuarios/registrar.html', {'form': form})


# ── CONSULTAR USUARIO ──────────────────────────────────────────
@login_required
def consultar_usuarios(request):
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
        return redirect('dashboard')
    query    = request.GET.get('q', '')
    usuarios = Usuario.objects.exclude(pk=request.user.pk).order_by('rol', 'first_name')
    if query:
        usuarios = usuarios.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(username__icontains=query)
        )
    page_obj = paginar(request, usuarios)
    return render(request, 'core/usuarios/consultar.html', {
        'usuarios': page_obj, 'page_obj': page_obj, 'query': query,
    })


# ── ELIMINAR USUARIO ────────────────────────────────────────────
@login_required
def eliminar_usuario(request, pk):
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
        return redirect('dashboard')

    usuario = get_object_or_404(Usuario, pk=pk)

    if usuario.pk == request.user.pk:
        messages.error(request, 'No puedes eliminar tu propio usuario.')
        return redirect('consultar_usuarios')

    if request.method == 'POST':
        # Verificar si el técnico tiene trabajos en curso asignados
        trabajos_activos = DetalleSolicitud.objects.filter(
            tecnico=usuario,
            solicitud__estado__in=['pendiente', 'proceso']
        ).count()

        if trabajos_activos > 0:
            messages.error(
                request,
                f'No se puede eliminar a "{usuario.get_full_name() or usuario.username}" '
                f'porque tiene {trabajos_activos} solicitud(es) activa(s) asignada(s). '
                f'Reasigna esos trabajos a otro técnico antes de eliminarlo, '
                f'o desactiva su cuenta en su lugar.'
            )
            return redirect('consultar_usuarios')

        nombre = usuario.get_full_name() or usuario.username
        usuario.delete()
        messages.success(request, f'Usuario "{nombre}" eliminado correctamente.')
        return redirect('consultar_usuarios')

    return redirect('consultar_usuarios')
