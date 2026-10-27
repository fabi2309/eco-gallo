"""Configuración de ECO-GALLO UAA (todo por variables de entorno)."""
import os
import pathlib
import secrets

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

# --- Correo (códigos de acceso) ---
SMTP_HOST = os.environ.get("ECOGALLO_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("ECOGALLO_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("ECOGALLO_SMTP_USER", "")
SMTP_PASS = os.environ.get("ECOGALLO_SMTP_PASS", "")
SMTP_FROM = os.environ.get("ECOGALLO_SMTP_FROM", SMTP_USER or "ecogallo@localhost")
SMTP_SSL = os.environ.get("ECOGALLO_SMTP_SSL", "0") == "1"  # 1 = SMTPS (465)

# DEV: sin SMTP el código se imprime en la consola del servidor y, solo si
# ECOGALLO_DEV=1, también se devuelve a la pantalla para poder probar.
DEV = os.environ.get("ECOGALLO_DEV", "0") == "1"

# --- Reglas de acceso ---
EMAIL_DOMAIN = "edu.uaa.mx"
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

ADMINS = {
    e.strip().lower()
    for e in os.environ.get("ECOGALLO_ADMINS", "").split(",")
    if e.strip()
}

# --- Publicaciones ---
AVATAR_MAX_BYTES = 2 * 1024 * 1024
BIO_MAX = 200
WISHLIST_MAX = 10
MAX_IMAGES = 4
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

SAFE_MEETING_POINTS = ["La Velaria", "Cafetería CCB", "Punto de Encuentro Central"]

# --- Respaldos automáticos ---
BACKUPS_DIR = DATA / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_ENABLED = os.environ.get("ECOGALLO_BACKUP_ENABLED", "1") == "1"
BACKUP_INTERVAL_HOURS = float(os.environ.get("ECOGALLO_BACKUP_INTERVAL_HOURS", "24"))
BACKUP_KEEP = int(os.environ.get("ECOGALLO_BACKUP_KEEP", "7"))
