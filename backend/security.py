"""Sesiones, códigos de acceso, correo y decoradores de autorización."""
import hashlib
import hmac
import logging
import re
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from functools import wraps

from flask import g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import config
from db import get_db, now

log = logging.getLogger("ecogallo")

EMAIL_RE = re.compile(
    r"^[a-z0-9][a-z0-9._%+\-]{0,63}@[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)+$"
)
INSTITUTIONAL_RE = re.compile(r"^[a-z0-9][a-z0-9._%+\-]{0,63}@edu\.uaa\.mx$")


def api_error(message: str, status: int = 400, **extra):
    return jsonify({"ok": False, "message": message, **extra}), status


def normalize_email(raw) -> str | None:
    """Correo válido en general (los egresados pueden usar uno personal)."""
    if not isinstance(raw, str):
        return None
    email = raw.strip().lower()
    return email if len(email) <= 120 and EMAIL_RE.match(email) else None


def is_institutional(email: str) -> bool:
    return bool(INSTITUTIONAL_RE.match(email or ""))


# ---------------------------------------------------------------- contraseñas
def password_problem(pw) -> str | None:
    """Devuelve el motivo si la contraseña no es aceptable; None si está bien."""
    if not isinstance(pw, str):
        return "Escribe una contraseña."
    if len(pw) < config.PASSWORD_MIN:
        return f"La contraseña debe tener al menos {config.PASSWORD_MIN} caracteres."
    if len(pw) > config.PASSWORD_MAX:
        return f"La contraseña no puede pasar de {config.PASSWORD_MAX} caracteres."
    if not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        return "Usa letras y al menos un número."
    return None


def hash_password(pw: str) -> str:
    return generate_password_hash(pw)  # scrypt con sal propia


# Hash falso para gastar el mismo tiempo cuando el correo no existe (evita
# distinguir "correo inexistente" de "contraseña incorrecta" por latencia).
_DUMMY_HASH = generate_password_hash("no-existe-" + secrets.token_hex(8))


def check_password(user: dict | None, pw) -> bool:
    stored = user["password_hash"] if user and user.get("password_hash") else _DUMMY_HASH
    ok = check_password_hash(stored, pw if isinstance(pw, str) else "")
    return bool(ok and user and user.get("password_hash"))


# ---------------------------------------------------------------- documentos
def sniff_document(data: bytes) -> str | None:
    """Tipo real por los primeros bytes (no por la extensión que manda el cliente)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"%PDF-"):
        return "pdf"
    return None


def _hmac(value: str) -> str:
    return hmac.new(config.SECRET, value.encode(), hashlib.sha256).hexdigest()


def hash_code(email: str, code: str) -> str:
    return _hmac(f"code:{email}:{code}")


def hash_token(token: str) -> str:
    return _hmac(f"session:{token}")


def new_code() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def client_ip() -> str:
    # El gateway Java sobrescribe X-Real-IP; el backend solo escucha en 127.0.0.1.
    return request.headers.get("X-Real-IP") or request.remote_addr or ""


# ---------------------------------------------------------------- correo
def send_code_email(email: str, code: str) -> None:
    minutes = config.CODE_TTL_SECONDS // 60
    if not config.SMTP_HOST:
        log.warning("[SIN SMTP] Código para %s: %s (vence en %s min)", email, code, minutes)
        print(f"\n  >>> ECO-GALLO código para {email}: {code}  (vence en {minutes} min)\n", flush=True)
        return

    msg = EmailMessage()
    msg["Subject"] = f"ECO-GALLO UAA · tu código de acceso: {code}"
    msg["From"] = config.SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Hola,\n\nTu código para entrar a ECO-GALLO UAA es: {code}\n\n"
        f"Vence en {minutes} minutos y solo sirve una vez. "
        "Si tú no lo pediste, ignora este mensaje.\n\n— ECO-GALLO UAA"
    )
    msg.add_alternative(
        f"""<div style="font-family:Arial,sans-serif;max-width:420px;margin:auto;color:#1c2b22">
<h2 style="color:#1f5d3a;margin:0 0 4px">ECO-GALLO UAA</h2>
<p>Usa este código para iniciar sesión:</p>
<p style="font-size:34px;letter-spacing:8px;font-weight:700;background:#eef6e8;
border:2px solid #6fae4c;border-radius:12px;padding:14px;text-align:center;color:#1f5d3a">{code}</p>
<p style="font-size:13px;color:#5a6b60">Vence en {minutes} minutos y solo sirve una vez.
Si no fuiste tú, ignora este correo.</p></div>""",
        subtype="html",
    )
    ctx = ssl.create_default_context()
    if config.SMTP_SSL:
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=12, context=ctx) as s:
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)
    else:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=12) as s:
            s.starttls(context=ctx)
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASS)
            s.send_message(msg)


# ---------------------------------------------------------------- sesiones
def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db = get_db()
    t = now()
    db.execute(
        "INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(?,?,?,?)",
        (hash_token(token), user_id, t, t + config.SESSION_DAYS * 86400),
    )
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (t,))
    return token


def load_user():
    g.user = None
    token = request.cookies.get(config.COOKIE_NAME)
    if not token:
        return
    db = get_db()
    row = db.execute(
        """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ? AND u.suspended = 0""",
        (hash_token(token), now()),
    ).fetchone()
    g.user = dict(row) if row else None


# Lo único que puede hacer un egresado mientras su documento está en revisión.
PENDING_OK = ("auth.me", "auth.me_update", "auth.logout", "auth.set_password", "auth.resubmit_document")


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.get("user"):
            return api_error("Inicia sesión para continuar.", 401)
        if not g.user["name"] and request.endpoint not in ("auth.me_update", "auth.me", "auth.logout"):
            return api_error("Completa tu perfil para continuar.", 403, needs_profile=True)
        if g.user["kind"] == "egresado" and g.user["verif_status"] != "approved" \
                and request.endpoint not in PENDING_OK:
            return api_error("Tu cuenta de egresado aún no está verificada.", 403,
                             needs_verification=True, verif_status=g.user["verif_status"])
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if g.user["role"] != "admin":
            return api_error("Solo administradores.", 403)
        return fn(*a, **kw)
    return wrapper


def notify(db, user_id: int, text: str, link: str = ""):
    db.execute(
        "INSERT INTO notifications(user_id,text,link,created_at) VALUES(?,?,?,?)",
        (user_id, text, link, now()),
    )


def clean_text(value, max_len: int, required: bool = True) -> str | None:
    if not isinstance(value, str):
        return None if required else ""
    value = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", value).strip()
    if required and not value:
        return None
    return value[:max_len]
