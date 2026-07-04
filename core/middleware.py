import time
from django.contrib.auth import logout
from django.shortcuts import redirect

TIMEOUT_POR_ROL = {
    'recep': 5  * 60,
    'tec':   10 * 60,
    'admin': 20 * 60,
}
TIMEOUT_DEFAULT   = 20 * 60
THROTTLE_SEGUNDOS = 60


class SesionActivaMiddleware:
    """Cierra la sesión por inactividad según el rol del usuario."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            ahora  = time.time()
            ultima = request.session.get('_ultima_actividad')
            rol    = getattr(request.user, 'rol', 'admin')
            limite = TIMEOUT_POR_ROL.get(rol, TIMEOUT_DEFAULT)

            if ultima and (ahora - ultima) > limite:
                logout(request)
                from django.contrib import messages
                messages.warning(request, 'Tu sesión se cerró por inactividad.')
                return redirect('login')

            if not ultima or (ahora - ultima) > THROTTLE_SEGUNDOS:
                request.session['_ultima_actividad'] = ahora

        return self.get_response(request)
