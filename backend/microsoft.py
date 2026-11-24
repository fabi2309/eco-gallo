"""Entrar con la cuenta Microsoft institucional de la UAA (US-01).

Flujo OpenID Connect con código de autorización + PKCE contra Microsoft Entra ID:

  1. GET /api/auth/microsoft/start     -> redirige a login.microsoftonline.com
  2. GET /api/auth/microsoft/callback  -> canjea el código, valida el id_token y abre sesión

Seguridad:
- Solo se acepta el inquilino (tenant) de la universidad: `tid` e `iss` deben coincidir con
  ECOGALLO_MS_TENANT (un GUID; "common"/"organizations" se rechazan al configurar).
- El correo (`preferred_username`) debe ser institucional (ECOGALLO_EMAIL_DOMAINS).
- `state` de un solo uso (10 min) contra CSRF, `nonce` contra repetición y PKCE (S256).
- El id_token llega directo del endpoint de tokens por TLS con autenticación de cliente, por lo que
  OpenID Connect Core §3.1.3.7 permite validar sus claims sin verificar la firma; aun así se revisan
  aud, iss, tid, nonce y vencimiento.

Variables: ECOGALLO_MS_CLIENT_ID, ECOGALLO_MS_CLIENT_SECRET, ECOGALLO_MS_TENANT.
La URL de retorno que se registra en Entra ID es <ECOGALLO_PUBLIC_URL>/api/auth/microsoft/callback.
"""
import base64
import hashlib
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request

from flask import Blueprint, redirect, request

import config
from db import get_db, now, tx
from security import create_session, hash_token, is_institutional, normalize_email

log = logging.getLogger("ecogallo")
bp = Blueprint("microsoft", __name__, url_prefix="/api/auth/microsoft")

AUTHORITY = "https://login.microsoftonline.com"
STATE_TTL = 600


def enabled() -> bool:
    return bool(config.MS_CLIENT_ID and config.MS_CLIENT_SECRET and config.MS_TENANT)


def _redirect_uri() -> str:
    base = config.PUBLIC_URL or request.host_url.rstrip("/")
    return base + "/api/auth/microsoft/callback"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _fail(code: str):
    """Vuelve a la pantalla de acceso con un motivo legible por el frontend."""
    return redirect(f"/#/oauth-error/{urllib.parse.quote(code)}", code=302)


@bp.get("/start")
def start():
    if not enabled():
        return _fail("no-configurado")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    t = now()
    db = get_db()
    db.execute("DELETE FROM oauth_states WHERE expires_at < ?", (t,))
    db.execute("INSERT INTO oauth_states(state_hash, nonce, verifier, expires_at, created_at) VALUES(?,?,?,?,?)",
               (hash_token("oauth:" + state), nonce, verifier, t + STATE_TTL, t))
    params = {
        "client_id": config.MS_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": _redirect_uri(),
        "response_mode": "query",
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
        "prompt": "select_account",
        "domain_hint": config.EMAIL_DOMAIN,
    }
    return redirect(f"{AUTHORITY}/{config.MS_TENANT}/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}", 302)


def exchange_code(code: str, verifier: str) -> dict:
    """Canjea el código por tokens. Separado para poder simularlo en pruebas."""
    body = urllib.parse.urlencode({
        "client_id": config.MS_CLIENT_ID,
        "client_secret": config.MS_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _redirect_uri(),
        "code_verifier": verifier,
        "scope": "openid profile email",
    }).encode()
    req = urllib.request.Request(f"{AUTHORITY}/{config.MS_TENANT}/oauth2/v2.0/token", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310 - URL fija https de Microsoft
        return json.loads(resp.read().decode())


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return {}


def validate_claims(claims: dict, nonce: str) -> str | None:
    """Devuelve el correo institucional si el id_token es válido para esta app; si no, None."""
    tenant = config.MS_TENANT.lower()
    if claims.get("aud") != config.MS_CLIENT_ID:
        return None
    if str(claims.get("tid", "")).lower() != tenant:
        return None
    if str(claims.get("iss", "")).lower() != f"{AUTHORITY}/{tenant}/v2.0":
        return None
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        return None
    if int(claims.get("exp", 0)) < now() - 60:
        return None
    email = normalize_email(claims.get("preferred_username") or claims.get("email") or "")
    if not email or not is_institutional(email):
        return None
    return email


@bp.get("/callback")
def callback():
    if not enabled():
        return _fail("no-configurado")
    if request.args.get("error"):
        return _fail("cancelado")
    state, code = request.args.get("state", ""), request.args.get("code", "")
    if not state or not code:
        return _fail("invalido")
    db = get_db()
    with tx(db):
        row = db.execute("SELECT * FROM oauth_states WHERE state_hash=? AND expires_at>=?",
                         (hash_token("oauth:" + state), now())).fetchone()
        if row:
            db.execute("DELETE FROM oauth_states WHERE state_hash=?", (row["state_hash"],))
    if not row:
        return _fail("vencido")
    try:
        tokens = exchange_code(code, row["verifier"])
    except (urllib.error.URLError, ValueError, TimeoutError):
        log.exception("Fallo al canjear el código de Microsoft")
        return _fail("microsoft")
    email = validate_claims(_claims(tokens.get("id_token", "")), row["nonce"])
    if not email:
        return _fail("cuenta-no-uaa")

    t = now()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if user is None:
        role = "admin" if email in config.ADMINS else "user"
        db.execute("INSERT INTO users(email,role,created_at) VALUES(?,?,?)", (email, role, t))
    else:
        if email in config.ADMINS and user["role"] != "admin":
            db.execute("UPDATE users SET role='admin' WHERE id=?", (user["id"],))
        db.execute("UPDATE users SET email_verified=1, failed_logins=0, locked_until=0 WHERE id=?", (user["id"],))
    user = dict(db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())
    if user["suspended"]:
        return _fail("suspendida")
    if user["totp_enabled"]:
        from auth import new_totp_challenge
        return redirect(f"/#/oauth-totp/{new_totp_challenge(user, email_authenticated=True)}", 302)

    token = create_session(user["id"])
    # Microsoft ya comprobó la identidad: igual que un código al correo, abre 10 min para restablecer contraseña.
    db.execute("UPDATE sessions SET reset_until=? WHERE token_hash=?", (t + 600, hash_token(token)))
    resp = redirect("/#/", 302)
    resp.set_cookie(config.COOKIE_NAME, token, max_age=config.SESSION_DAYS * 86400, httponly=True,
                    samesite="Lax", secure=config.COOKIE_SECURE, path="/")
    return resp
