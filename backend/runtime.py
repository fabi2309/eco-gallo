"""Request hardening and single-process maintenance coordination."""
import contextlib
import hmac
import threading
import time
from urllib.parse import urlsplit

from flask import g, request

import config
from security import api_error, client_ip, hash_token

CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' "
       "https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
       "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
_condition = threading.Condition()
_active = set()
_maintenance = False
_rates = {}
_rate_lock = threading.Lock()


def csrf_token(token=None):
    token = token or request.cookies.get(config.COOKIE_NAME)
    return hash_token('csrf:' + token) if token else ''


def enter_request():
    if request.path == "/api/admin/backups/upload":
        request.max_content_length = 210 * 1024 * 1024
    with _condition:
        if _maintenance:
            return api_error('Mantenimiento en curso. Intenta nuevamente en unos segundos.', 503)
        _active.add(threading.get_ident())
        g.runtime_entered = True


def leave_request(_error=None):
    if g.pop('runtime_entered', False):
        with _condition:
            _active.discard(threading.get_ident())
            _condition.notify_all()


@contextlib.contextmanager
def exclusive():
    """Drain requests before touching DB plus files; official server uses one process."""
    global _maintenance
    with _condition:
        if _maintenance:
            raise ValueError('Ya hay una operación de mantenimiento en curso.')
        _maintenance = True
        deadline = time.monotonic() + 35
        while _active - {threading.get_ident()}:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _maintenance = False
                _condition.notify_all()
                raise ValueError('Hay operaciones en curso. Intenta nuevamente más tarde.')
            _condition.wait(remaining)
    try:
        yield
    finally:
        with _condition:
            _maintenance = False
            _condition.notify_all()


def protect_request():
    if request.path == '/api/stripe/webhook':
        return
    if request.is_json and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not isinstance(request.get_json(silent=True), dict):
            return api_error('Se esperaba un objeto JSON válido.', 400)
    if request.path.startswith('/api/auth/'):
        key = client_ip()
        with _rate_lock:
            stamp = int(time.time() // 60)
            if len(_rates) > 10000:
                _rates.clear()
            window, hits = _rates.get(key, (stamp, 0))
            hits = hits + 1 if window == stamp else 1
            _rates[key] = (stamp, hits)
        if hits > config.AUTH_LIMIT:
            return api_error('Demasiadas solicitudes. Espera un minuto.', 429)
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    origin = request.headers.get('Origin')
    expected = urlsplit(config.PUBLIC_URL or request.host_url)
    if origin:
        actual = urlsplit(origin)
        if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
            return api_error('Origen de solicitud no permitido.', 403)
    if request.headers.get('Sec-Fetch-Site') == 'cross-site':
        return api_error('Origen de solicitud no permitido.', 403)
    if request.cookies.get(config.COOKIE_NAME):
        supplied = request.headers.get('X-CSRF-Token', '')
        if not hmac.compare_digest(supplied, csrf_token()):
            return api_error('Actualiza la página para renovar la protección de tu sesión.', 403)


def response_headers(response):
    response.headers['Content-Security-Policy'] = CSP
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if config.PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, private'
    return response
