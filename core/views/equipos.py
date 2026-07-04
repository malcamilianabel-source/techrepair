"""Vistas de gestión de equipos."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import EquipoForm, EquipoUpdateForm
from ..models import Cliente, Equipo, Solicitud, Usuario
from .helpers import paginar


# ── CONSULTAR EQUIPOS ──────────────────────────────────────────
@login_required
def consultar_equipos(request):
    query   = request.GET.get('q', '')
    tipo    = request.GET.get('tipo', '')
    equipos = Equipo.objects.select_related('cliente').order_by('-creado_en')
    if query:
        equipos = equipos.filter(
            Q(marca__icontains=query) | Q(modelo__icontains=query) |
            Q(serie__icontains=query)
        )
    if tipo:
        equipos = equipos.filter(tipo=tipo)
    page_obj = paginar(request, equipos)
    return render(request, 'core/equipos/consultar.html', {
        'equipos': page_obj, 'page_obj': page_obj,
        'query': query, 'tipo': tipo, 'tipos': Equipo.TIPOS,
    })


# ── REGISTRAR EQUIPO ───────────────────────────────────────────
@login_required
def registrar_equipo(request):
    if request.user.rol == Usuario.Rol.TECNICO:
        return redirect('dashboard')

    cliente_id = request.GET.get('cliente_id') or request.POST.get('cliente_id_hidden')
    cliente_fijo = None
    if cliente_id:
        try:
            cliente_fijo = Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            cliente_fijo = None

    if request.method == 'POST':
        form = EquipoForm(request.POST)
        if form.is_valid():
            equipo = form.save()
            messages.success(request, 'Equipo registrado correctamente.')
            if cliente_fijo:
                return redirect(
                    f'/solicitudes/registrar/?cliente_id={cliente_fijo.pk}&equipo_id={equipo.pk}'
                )
            return redirect('consultar_equipos')
    else:
        initial = {}
        if cliente_fijo:
            initial['cliente'] = cliente_fijo
        form = EquipoForm(initial=initial)

    return render(request, 'core/equipos/registrar.html', {
        'form':         form,
        'cliente_fijo': cliente_fijo,
    })


# ── ACTUALIZAR EQUIPO ──────────────────────────────────────────
@login_required
def actualizar_equipo(request, pk):
    if request.user.rol == Usuario.Rol.TECNICO:
        return redirect('dashboard')
    equipo = get_object_or_404(Equipo.objects.select_related('cliente'), pk=pk)
    if request.method == 'POST':
        form = EquipoUpdateForm(request.POST, instance=equipo)
        if form.is_valid():
            if request.user.rol != Usuario.Rol.ADMINISTRADOR:
                campos_identidad = ['tipo', 'marca', 'modelo', 'serie']
                equipo_actual = Equipo.objects.get(pk=pk)
                for campo in campos_identidad:
                    setattr(form.instance, campo, getattr(equipo_actual, campo))
            form.save()
            messages.success(request, 'Equipo actualizado correctamente.')
            return redirect('consultar_equipos')
    else:
        form = EquipoUpdateForm(instance=equipo)
    return render(request, 'core/equipos/actualizar.html', {
        'form':   form,
        'equipo': equipo,
    })


# ── ELIMINAR EQUIPO ─────────────────────────────────────────────
@login_required
def eliminar_equipo(request, pk):
    if request.user.rol != Usuario.Rol.ADMINISTRADOR:
        messages.error(request, 'Solo el administrador puede eliminar equipos.')
        return redirect('consultar_equipos')
    equipo = get_object_or_404(Equipo.objects.select_related('cliente'), pk=pk)
    if request.method == 'POST':
        try:

            desc = f'{equipo.get_marca_display()} {equipo.modelo}'
            equipo.delete()
            messages.success(request, f'Equipo {desc} eliminado correctamente.')
            return redirect('consultar_equipos')
        except ProtectedError:
            messages.error(request,
                'No se puede eliminar este equipo porque tiene solicitudes '
                'registradas. Elimínalas primero.')
            return redirect('consultar_equipos')
    return render(request, 'core/equipos/eliminar.html', {'equipo': equipo})


# ── HISTORIAL DEL EQUIPO ───────────────────────────────────────
@login_required
def historial_equipo(request, pk):
    equipo      = get_object_or_404(Equipo, pk=pk)
    solicitudes = Solicitud.objects.filter(
        equipo=equipo
    ).select_related('cliente', 'detalle__tecnico').order_by('-creado_en')
    return render(request, 'core/equipos/historial.html', {
        'equipo':      equipo,
        'solicitudes': solicitudes,
    })


# ── API: EQUIPOS POR CLIENTE ───────────────────────────────────
@login_required
def equipos_por_cliente(request, cliente_id):
    equipos = Equipo.objects.filter(cliente_id=cliente_id).values(
        'id', 'tipo', 'marca', 'modelo', 'serie'
    )
    TIPO_LABELS = dict(Equipo.TIPOS)
    data = []
    for e in equipos:
        tipo_label = TIPO_LABELS.get(e['tipo'], e['tipo'])
        data.append({
            'id':    e['id'],
            'texto': f"{tipo_label} — {e['marca'].upper()} {e['modelo']} — Serie: {e['serie']}"
        })
    return JsonResponse({'equipos': data})
