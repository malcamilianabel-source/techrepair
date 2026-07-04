"""Vistas de gestión de clientes."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ClienteForm, ClienteUpdateForm
from ..models import Cliente, Solicitud, Usuario
from .helpers import paginar


# ── LISTAR CLIENTES ────────────────────────────────────────────
@login_required
def consultar_clientes(request):
    query    = request.GET.get('q', '')
    clientes = Cliente.objects.all().order_by('-creado_en')
    if query:
        clientes = clientes.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query) |
            Q(dni__icontains=query)    | Q(telefono__icontains=query)
        )
    page_obj = paginar(request, clientes)
    return render(request, 'core/clientes/consultar.html', {
        'clientes': page_obj, 'page_obj': page_obj, 'query': query,
    })


# ── REGISTRAR CLIENTE ──────────────────────────────────────────
@login_required
def registrar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(
                request,
                f'Cliente {cliente.nombre_completo} registrado. Ahora registra su equipo.'
            )
            return redirect(f'/equipos/registrar/?cliente_id={cliente.pk}')
    else:
        form = ClienteForm()
    return render(request, 'core/clientes/registrar.html', {'form': form})


# ── ACTUALIZAR CLIENTE ─────────────────────────────────────────
@login_required
def actualizar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteUpdateForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado correctamente.')
            return redirect('consultar_clientes')
    else:
        form = ClienteUpdateForm(instance=cliente)
    return render(request, 'core/clientes/actualizar.html', {
        'form':    form,
        'cliente': cliente,
    })


# ── ELIMINAR CLIENTE ────────────────────────────────────────────
@login_required
def eliminar_cliente(request, pk):
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
        messages.error(request, 'Solo el administrador puede eliminar clientes.')
        return redirect('consultar_clientes')
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        try:

            nombre = cliente.nombre_completo
            cliente.delete()
            messages.success(request, f'Cliente {nombre} eliminado correctamente.')
            return redirect('consultar_clientes')
        except ProtectedError:
            messages.error(request,
                f'No se puede eliminar a {cliente.nombre_completo} porque tiene '
                f'equipos o solicitudes registradas. Elimínalos primero.')
            return redirect('consultar_clientes')
    return render(request, 'core/clientes/eliminar.html', {'cliente': cliente})


# ── HISTORIAL DEL CLIENTE ──────────────────────────────────────
@login_required
def historial_cliente(request, pk):
    cliente    = get_object_or_404(Cliente, pk=pk)
    solicitudes = Solicitud.objects.filter(
        cliente=cliente
    ).select_related('equipo', 'detalle__tecnico').order_by('-creado_en')
    return render(request, 'core/clientes/historial.html', {
        'cliente':     cliente,
        'solicitudes': solicitudes,
    })
