from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def rol_requerido(*roles):
    """Restringe el acceso a los roles indicados."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.rol not in roles:
                messages.error(request, 'No tienes permiso para esta acción.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def tecnico_asignado_o_staff(user, solicitud):
    """True si el usuario es admin/recep, o si es el técnico asignado."""
    from .models import Usuario
    if user.rol in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.RECEPCIONISTA):
        return True
    detalle = getattr(solicitud, 'detalle', None)
    return detalle is not None and detalle.tecnico_id == user.id
