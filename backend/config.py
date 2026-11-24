"""Configuración de ECO-GALLO UAA (todo por variables de entorno)."""
import os
import pathlib
import secrets

import envfile

envfile.load()   # .env en la raíz del proyecto (opcional)

PRODUCTION = os.environ.get("ECOGALLO_ENV", "development") == "production"
PUBLIC_URL = os.environ.get("ECOGALLO_PUBLIC_URL", "").rstrip("/")
AUTH_LIMIT = int(os.environ.get("ECOGALLO_AUTH_LIMIT", "60"))
LIVE_PAYMENTS = os.environ.get("ECOGALLO_LIVE_PAYMENTS", "0") == "1"

BASE = pathlib.Path(__file__).resolve().parent
ROOT = BASE.parent

DATA = pathlib.Path(os.environ.get("ECOGALLO_DATA", ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)
UPLOADS = DATA / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA / "ecogallo.sqlite"


def _load_secret() -> bytes:
    env = os.environ.get("ECOGALLO_SECRET")
    if env:
        return env.encode()
    f = DATA / "secret.key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
        try:
            f.chmod(0o600)
        except OSError:
            pass
    return f.read_text().strip().encode()


SECRET = _load_secret()

# --- Responsable de los datos personales (aviso de privacidad, LFPDPPP) ---
# Se muestran en el aviso de privacidad. Complétalos antes de publicar el sistema.
LEGAL_VERSION = "2026-11-b"   # súbelo cuando cambien el aviso o los términos: se vuelve a pedir aceptación
OPERATOR_NAME = os.environ.get("ECOGALLO_OPERATOR_NAME") or "Equipo ECO-GALLO UAA"
PRIVACY_EMAIL = os.environ.get("ECOGALLO_PRIVACY_EMAIL", "")
OPERATOR_ADDRESS = os.environ.get("ECOGALLO_OPERATOR_ADDRESS") or (
    "Universidad Autónoma de Aguascalientes, Av. Universidad 940, Ciudad Universitaria, Aguascalientes, Ags.")

# --- Entrar con Microsoft (cuenta institucional UAA en Microsoft Entra ID) ---
# Registra una aplicación web en Entra ID con la URL de retorno <ECOGALLO_PUBLIC_URL>/api/auth/microsoft/callback.
MS_CLIENT_ID = os.environ.get("ECOGALLO_MS_CLIENT_ID", "").strip()
MS_CLIENT_SECRET = os.environ.get("ECOGALLO_MS_CLIENT_SECRET", "").strip()
MS_TENANT = os.environ.get("ECOGALLO_MS_TENANT", "").strip().lower()   # GUID del inquilino de la UAA

# --- Correo (códigos de acceso) ---
SMTP_HOST = os.environ.get("ECOGALLO_SMTP_HOST", "")
# SMS para confirmar teléfonos (Twilio). Sin configurar, en desarrollo el código se muestra en pantalla.
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM = os.environ.get("TWILIO_FROM", "").strip()          # número de Twilio, p. ej. +15551234567
SMS_ENABLED = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM)
SMTP_PORT = int(os.environ.get("ECOGALLO_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("ECOGALLO_SMTP_USER", "")
SMTP_PASS = os.environ.get("ECOGALLO_SMTP_PASS", "")
SMTP_FROM = os.environ.get("ECOGALLO_SMTP_FROM", SMTP_USER or "ecogallo@localhost")
SMTP_SSL = os.environ.get("ECOGALLO_SMTP_SSL", "0") == "1"  # 1 = SMTPS (465)

# --- Stripe (pagos y Stripe Connect) ---
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

STRIPE_SUCCESS_URL = os.environ.get(
    "STRIPE_SUCCESS_URL",
    (PUBLIC_URL or "http://localhost:8080") + "/#/payment-success"
)
STRIPE_CANCEL_URL = os.environ.get(
    "STRIPE_CANCEL_URL",
    (PUBLIC_URL or "http://localhost:8080") + "/#/payment-cancel"
)

STRIPE_CONNECT_REFRESH_URL = os.environ.get(
    "STRIPE_CONNECT_REFRESH_URL",
    (PUBLIC_URL or "http://localhost:8080") + "/#/profile"
)
STRIPE_CONNECT_RETURN_URL = os.environ.get(
    "STRIPE_CONNECT_RETURN_URL",
    (PUBLIC_URL or "http://localhost:8080") + "/#/profile"
)

# --- Mercado Pago (Checkout Pro: tarjeta, OXXO, SPEI, saldo MP) ---
MP_ACCESS_TOKEN = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "").strip()
MP_WEBHOOK_SECRET = os.environ.get("MERCADOPAGO_WEBHOOK_SECRET", "").strip()
MP_TEST = os.environ.get("MERCADOPAGO_TEST", "0" if PRODUCTION else "1") == "1"

PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "disabled" if PRODUCTION else "simulado").lower()

# DEV: sin SMTP el código se imprime en la consola del servidor y, solo si
# ECOGALLO_DEV=1, también se devuelve a la pantalla para poder probar.
DEV = os.environ.get("ECOGALLO_DEV", "0") == "1"

CONNECT_SIMULATED = (
    DEV and os.environ.get("ECOGALLO_CONNECT_SIMULATED", "0") == "1"
)

# En desarrollo, Mercado Pago sin credenciales no detiene la app: se usa el pago de prueba (simulado).
if DEV and not PRODUCTION and PAYMENT_PROVIDER == "mercadopago" and not MP_ACCESS_TOKEN:
    import sys
    print("  Aviso: PAYMENT_PROVIDER=mercadopago sin MERCADOPAGO_ACCESS_TOKEN; se usa el pago de prueba.",
          file=sys.stderr, flush=True)
    PAYMENT_PROVIDER = "simulado"

# --- Reglas de acceso ---
# Dominios que cuentan como "correo institucional" (se pueden cambiar sin tocar código):
#   ECOGALLO_EMAIL_DOMAINS="edu.uaa.mx,alumnos.uaa.mx"
EMAIL_DOMAINS = tuple(d.strip().lower().lstrip("@") for d in
                      os.environ.get("ECOGALLO_EMAIL_DOMAINS", "edu.uaa.mx,alumnos.uaa.mx").split(",") if d.strip())
EMAIL_DOMAIN = EMAIL_DOMAINS[0]
# Operaciones concluidas para ganar la insignia «Vendedor verificado».
VERIFIED_SELLER_MIN_DEALS = int(os.environ.get("ECOGALLO_VERIFIED_MIN_DEALS", "1"))
CODE_TTL_SECONDS = 10 * 60
CODE_MAX_ATTEMPTS = 5
CODE_COOLDOWN_SECONDS = 45
CODE_MAX_PER_HOUR_EMAIL = 5
CODE_MAX_PER_HOUR_IP = 20
SESSION_DAYS = 30

# --- Contraseña ---
PASSWORD_MIN = 8
PASSWORD_MAX = 128
LOGIN_MAX_FAILS = 5            # intentos fallidos seguidos antes de bloquear
LOGIN_LOCK_SECONDS = 15 * 60

# --- Egresados: documento (kárdex o título) para revisión manual ---
VERIF_DIR = DATA / "private" / "verificaciones"   # NO se sirve públicamente
VERIF_DIR.mkdir(parents=True, exist_ok=True)
VERIF_MAX_BYTES = 6 * 1024 * 1024
VERIF_DOC_TYPES = {"kardex": "Kárdex", "titulo": "Título profesional"}
COOKIE_NAME = "eg_session"
COOKIE_SECURE = os.environ.get("ECOGALLO_SECURE", "0") == "1"

_ADMIN_LIST = [e.strip().lower() for e in os.environ.get("ECOGALLO_ADMINS", "").split(",") if e.strip()]
ADMINS = set(_ADMIN_LIST)
# Cuenta de administración con contraseña, creada al arrancar (la primera de ECOGALLO_ADMINS).
# En desarrollo tiene una contraseña conocida para la demostración; en producción es obligatorio
# elegir una propia (ver validate_runtime). Si la cuenta ya tiene contraseña, no se sobrescribe.
DEFAULT_DEV_ADMIN_PASSWORD = "EcoGallo2026"
ADMIN_EMAIL = _ADMIN_LIST[0] if _ADMIN_LIST else ""
ADMIN_PASSWORD = os.environ.get("ECOGALLO_ADMIN_PASSWORD", "").strip() or (
    DEFAULT_DEV_ADMIN_PASSWORD if DEV and not PRODUCTION else "")

# --- Publicaciones ---
AVATAR_MAX_BYTES = 2 * 1024 * 1024
BIO_MAX = 200
WISHLIST_MAX = 10
MAX_IMAGES = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PRICE_CENTS = 10_000_00  # $10,000 MXN tope por artículo (marketplace estudiantil)

CATEGORIES = [
    "Libros", "Apuntes", "Laboratorio", "Tecnología", "Arquitectura",
    "Uniformes", "Deportes", "Electrónica", "Otros",
]
# Centros y carreras: ver catalog.py (una sola fuente de verdad).
from catalog import CENTROS_POST as CENTROS  # noqa: E402  (incluye "General" para publicaciones)

TIPOS = ["venta", "trueque", "donacion"]
CONDITIONS = ["Nuevo", "Como nuevo", "Usado", "Con detalles"]

# Estimación orientativa de CO2e evitado por artículo reutilizado (kg).
CO2_KG = {
    "Libros": 2.5, "Apuntes": 0.5, "Laboratorio": 3.0, "Tecnología": 20.0,
    "Arquitectura": 3.0, "Uniformes": 6.0, "Deportes": 4.0, "Electrónica": 10.0,
    "Otros": 2.0,
}

# Precio de referencia de un artículo NUEVO por categoría (MXN, en centavos). Solo se usa cuando el vendedor
# no declara el precio nuevo al publicar. Son valores conservadores: ajústalos con precios reales de la UAA.
NEW_PRICE_EST_CENTS = {
    "Libros": 650_00, "Apuntes": 150_00, "Laboratorio": 450_00, "Tecnología": 3500_00,
    "Arquitectura": 900_00, "Uniformes": 500_00, "Deportes": 600_00, "Electrónica": 800_00,
    "Otros": 300_00,
}

# Publicaciones destacadas (US-14): gratuitas y limitadas para que sean justas entre estudiantes.
FEATURE_HOURS = int(os.environ.get("ECOGALLO_FEATURE_HOURS", "72"))      # cuánto dura destacada
FEATURE_COOLDOWN_DAYS = int(os.environ.get("ECOGALLO_FEATURE_COOLDOWN_DAYS", "7"))  # espera para volver a destacar la misma
FEATURE_MAX_ACTIVE = 1                                                    # destacadas a la vez por persona

SAFE_MEETING_POINTS = ["La Velaria", "Cafetería CCB", "Punto de Encuentro Central"]

# --- Respaldos automáticos ---
BACKUPS_DIR = DATA / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_ENABLED = os.environ.get("ECOGALLO_BACKUP_ENABLED", "1") == "1"
BACKUP_INTERVAL_HOURS = float(os.environ.get("ECOGALLO_BACKUP_INTERVAL_HOURS", "24"))
BACKUP_KEEP = int(os.environ.get("ECOGALLO_BACKUP_KEEP", "7"))


def validate_runtime():
    import re
    if MS_CLIENT_ID or MS_TENANT:
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", MS_TENANT):
            raise RuntimeError("ECOGALLO_MS_TENANT debe ser el GUID del inquilino de la UAA "
                               "(no 'common' ni 'organizations': aceptaría cuentas de otras organizaciones).")
        if not MS_CLIENT_ID or not MS_CLIENT_SECRET:
            raise RuntimeError("Entrar con Microsoft requiere ECOGALLO_MS_CLIENT_ID y ECOGALLO_MS_CLIENT_SECRET.")
    if BACKUP_KEEP < 1:
        raise RuntimeError("ECOGALLO_BACKUP_KEEP debe ser al menos 1.")
    if PAYMENT_PROVIDER not in ("disabled", "simulado", "stripe", "mercadopago"):
        raise RuntimeError("Proveedor de pagos inválido.")
    live_key = STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))
    if live_key and (not PRODUCTION or not LIVE_PAYMENTS or DEV or CONNECT_SIMULATED):
        raise RuntimeError("Las claves live requieren habilitación explícita y desactivar simulación y DEV.")
    if PRODUCTION:
        if DEV or PAYMENT_PROVIDER == "simulado" or CONNECT_SIMULATED:
            raise RuntimeError("No se permite modo de demostración en producción.")
        if not COOKIE_SECURE or not PUBLIC_URL.startswith("https://"):
            raise RuntimeError("Producción requiere HTTPS, ECOGALLO_PUBLIC_URL y ECOGALLO_SECURE=1.")
        if not SMTP_HOST or not os.environ.get("ECOGALLO_SECRET") or len(SECRET) < 32:
            raise RuntimeError("Producción requiere SMTP y ECOGALLO_SECRET persistente de al menos 32 caracteres.")
        if ADMIN_PASSWORD and (ADMIN_PASSWORD == DEFAULT_DEV_ADMIN_PASSWORD or len(ADMIN_PASSWORD) < 12):
            raise RuntimeError("En producción ECOGALLO_ADMIN_PASSWORD debe ser propia y de al menos 12 caracteres.")
        if "@" not in PRIVACY_EMAIL:
            raise RuntimeError("Producción requiere ECOGALLO_PRIVACY_EMAIL: el aviso de privacidad debe indicar "
                               "dónde ejercer los derechos ARCO.")
    if (TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN or TWILIO_FROM) and not SMS_ENABLED:
        raise RuntimeError("Para enviar SMS llena TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_FROM.")
    if PRODUCTION and PAYMENT_PROVIDER != "disabled" and not SMS_ENABLED:
        raise RuntimeError("Los pagos con tarjeta en producción requieren SMS (Twilio) para confirmar teléfonos.")
    if PAYMENT_PROVIDER == "mercadopago":
        if not MP_ACCESS_TOKEN or not MP_WEBHOOK_SECRET:
            raise RuntimeError("Mercado Pago requiere MERCADOPAGO_ACCESS_TOKEN y MERCADOPAGO_WEBHOOK_SECRET.")
        if PRODUCTION and MP_TEST:
            raise RuntimeError("Las credenciales de prueba de Mercado Pago solo se permiten fuera de producción.")
        if not MP_TEST and (not PRODUCTION or not LIVE_PAYMENTS or DEV):
            raise RuntimeError("Cobros reales con Mercado Pago requieren producción, ECOGALLO_LIVE_PAYMENTS=1 y sin DEV.")
    if PAYMENT_PROVIDER == "stripe":
        if not STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_", "sk_live_", "rk_live_")):
            raise RuntimeError("Falta una clave Stripe válida.")
        if not STRIPE_WEBHOOK_SECRET:
            raise RuntimeError("Stripe requiere STRIPE_WEBHOOK_SECRET.")
        if PRODUCTION and not live_key:
            raise RuntimeError("Stripe Test solo está permitido fuera de producción.")


validate_runtime()
