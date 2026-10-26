"""Acceso: código de un solo uso, contraseña, y alta de egresados con documento.

Tres formas de entrar:
  1. Estudiante con @edu.uaa.mx: código al correo (crea la cuenta la primera vez).
  2. Cualquier cuenta que ya tenga contraseña: correo + contraseña (sin códigos).
  3. Egresado: se registra con cualquier correo + kárdex/título; un admin lo revisa.
"""
import hmac
import logging
import uuid

from flask import Blueprint, g, jsonify, request

import catalog
import config
from db import get_db, now, rows, tx
from security import (
    api_error, check_password, clean_text, client_ip, create_session, hash_code, hash_password,
    hash_token, is_institutional, login_required, new_code, normalize_email, notify,
    password_problem, send_code_email, sniff_document,
)

log = logging.getLogger("ecogallo")
bp = Blueprint("auth", __name__, url_prefix="/api")

GENERIC_OK = "Si el correo está registrado, te enviamos un código. Revisa tu bandeja (y spam)."
BAD_LOGIN = "Correo o contraseña incorrectos. Si aún no tienes contraseña, entra con un código."


def public_user(u: dict) -> dict:
    return {
        "id": u["id"], "email": u["email"], "name": u["name"], "carrera": u["carrera"],
        "centro": u["centro"], "role": u["role"], "created_at": u["created_at"],
        "kind": u["kind"], "verif_status": u["verif_status"],
        "has_password": bool(u["password_hash"]), "bio": u["bio"],
        "avatar": f"/uploads/{u['avatar']}" if u["avatar"] else "",
    }


def _session_response(user: dict, **extra):
    token = create_session(user["id"])
    out = jsonify({
        "ok": True, "user": public_user(user), "needs_profile": not user["name"],
        "needs_verification": user["kind"] == "egresado" and user["verif_status"] != "approved",
        **extra,
    })
    out.set_cookie(
        config.COOKIE_NAME, token, max_age=config.SESSION_DAYS * 86400, httponly=True,
        samesite="Lax", secure=config.COOKIE_SECURE, path="/",
    )
    return out


# ---------------------------------------------------------------- código por correo
def _issue_code(db, email: str):
    """Genera y envía un código. Devuelve (payload, None) o (None, respuesta_de_error)."""
    ip, t = client_ip(), now()
    last = db.execute(
        "SELECT created_at FROM login_codes WHERE email=? ORDER BY id DESC LIMIT 1", (email,)
    ).fetchone()
    if last and t - last["created_at"] < config.CODE_COOLDOWN_SECONDS:
        wait = config.CODE_COOLDOWN_SECONDS - (t - last["created_at"])
        return None, api_error(f"Espera {wait} s para pedir otro código.", 429, retry_after=wait)

    per_email = db.execute(
        "SELECT COUNT(*) c FROM login_codes WHERE email=? AND created_at>?", (email, t - 3600)
    ).fetchone()["c"]
    per_ip = db.execute(
        "SELECT COUNT(*) c FROM login_codes WHERE ip=? AND created_at>?", (ip, t - 3600)
    ).fetchone()["c"]
    if per_email >= config.CODE_MAX_PER_HOUR_EMAIL or per_ip >= config.CODE_MAX_PER_HOUR_IP:
        return None, api_error("Demasiados intentos. Intenta de nuevo en un rato.", 429)

    code = new_code()
    with tx(db):
        db.execute("UPDATE login_codes SET used=1 WHERE email=? AND used=0", (email,))
        db.execute(
            "INSERT INTO login_codes(email,code_hash,expires_at,ip,created_at) VALUES(?,?,?,?,?)",
            (email, hash_code(email, code), t + config.CODE_TTL_SECONDS, ip, t),
        )
    try:
        send_code_email(email, code)
    except Exception:  # noqa: BLE001 - no filtrar detalles SMTP al cliente
        log.exception("Fallo al enviar correo")
        return None, api_error("No pudimos enviar el correo. Intenta de nuevo en un momento.", 502)

    out = {"ok": True, "message": GENERIC_OK, "ttl": config.CODE_TTL_SECONDS,
           "cooldown": config.CODE_COOLDOWN_SECONDS}
    if config.DEV:
        out["dev_code"] = code  # SOLO modo desarrollo (ECOGALLO_DEV=1)
    return out, None


@bp.post("/auth/request-code")
def request_code():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email"))
    if not email:
        return api_error("Escribe un correo válido.", 400)

    db = get_db()
    # Solo se manda código a: correos institucionales, o egresados ya registrados.
    # Para cualquier otro correo respondemos igual, sin enviar nada (no revela quién tiene cuenta).
    if not is_institutional(email):
        known = db.execute("SELECT 1 FROM users WHERE email=? AND kind='egresado'", (email,)).fetchone()
        if not known:
            return jsonify({"ok": True, "message": GENERIC_OK, "ttl": config.CODE_TTL_SECONDS,
                            "cooldown": config.CODE_COOLDOWN_SECONDS})
    out, err = _issue_code(db, email)
    return err or jsonify(out)


@bp.post("/auth/verify")
def verify():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email"))
    code = str(data.get("code", "")).strip().replace(" ", "")
    if not email or not (code.isdigit() and len(code) == 6):
        return api_error("Ingresa el código de 6 dígitos.", 400)

    db = get_db()
    t = now()
    resp = None
    with tx(db):
        row = db.execute(
            """SELECT * FROM login_codes WHERE email=? AND used=0 AND expires_at>?
               ORDER BY id DESC LIMIT 1""", (email, t),
        ).fetchone()
        if not row:
            resp = api_error("El código venció o no existe. Pide uno nuevo.", 400)
        elif row["attempts"] >= config.CODE_MAX_ATTEMPTS:
            db.execute("UPDATE login_codes SET used=1 WHERE id=?", (row["id"],))
            resp = api_error("Demasiados intentos. Pide un código nuevo.", 429)
        elif not hmac.compare_digest(row["code_hash"], hash_code(email, code)):
            attempts = row["attempts"] + 1
            db.execute("UPDATE login_codes SET attempts=? WHERE id=?", (attempts, row["id"]))
            left = config.CODE_MAX_ATTEMPTS - attempts
            resp = api_error(f"Código incorrecto. Te quedan {left} intento(s).", 400)
        else:
            db.execute("UPDATE login_codes SET used=1 WHERE id=?", (row["id"],))
    if resp:
        # Los intentos fallidos ya quedaron confirmados (commit) arriba.
        return resp

    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if user is None:
        if not is_institutional(email):  # defensa: solo los correos UAA crean cuenta por código
            return api_error("No encontramos una cuenta con ese correo.", 400)
        role = "admin" if email in config.ADMINS else "user"
        db.execute("INSERT INTO users(email,role,created_at) VALUES(?,?,?)", (email, role, t))
    else:
        if email in config.ADMINS and user["role"] != "admin":
            db.execute("UPDATE users SET role='admin' WHERE id=?", (user["id"],))
        # Haber recibido el código demuestra que el correo es suyo.
        db.execute("UPDATE users SET email_verified=1, failed_logins=0, locked_until=0 WHERE email=?", (email,))
    user = dict(db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())
    if user["suspended"]:
        return api_error("Tu cuenta está suspendida. Contacta a la administración.", 403)
    return _session_response(user)


# ---------------------------------------------------------------- contraseña
@bp.post("/auth/login")
def login_password():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email"))
    password = data.get("password")
    if not email or not isinstance(password, str) or not password:
        return api_error("Escribe tu correo y tu contraseña.", 400)

    db = get_db()
    t = now()
    row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    user = dict(row) if row else None
    if user and user["locked_until"] > t:
        mins = max(1, (user["locked_until"] - t + 59) // 60)
        return api_error(f"Demasiados intentos fallidos. Intenta de nuevo en {mins} min "
                         "o entra con un código a tu correo.", 429)

    if not check_password(user, password):
        if user:
            fails = user["failed_logins"] + 1
            if fails >= config.LOGIN_MAX_FAILS:
                db.execute("UPDATE users SET failed_logins=0, locked_until=? WHERE id=?",
                           (t + config.LOGIN_LOCK_SECONDS, user["id"]))
            else:
                db.execute("UPDATE users SET failed_logins=? WHERE id=?", (fails, user["id"]))
        return api_error(BAD_LOGIN, 401)

    if user["suspended"]:
        return api_error("Tu cuenta está suspendida. Contacta a la administración.", 403)
    if not user["email_verified"]:
        return api_error("Falta confirmar tu correo. Entra con un código para activarlo.", 403,
                         needs_email_verification=True)
    db.execute("UPDATE users SET failed_logins=0, locked_until=0 WHERE id=?", (user["id"],))
    return _session_response(user)


@bp.put("/auth/password")
@login_required
def set_password():
    """Crear la contraseña (primera vez, ya con sesión) o cambiarla (pide la actual)."""
    data = request.get_json(silent=True) or {}
    new = data.get("new_password")
    problem = password_problem(new)
    if problem:
        return api_error(problem, 400)
    db = get_db()
    me = dict(db.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone())
    if me["password_hash"] and not check_password(me, data.get("current_password")):
        return api_error("La contraseña actual no es correcta.", 400)
    if new.lower() == me["email"]:
        return api_error("La contraseña no puede ser tu correo.", 400)
    db.execute("UPDATE users SET password_hash=?, failed_logins=0, locked_until=0 WHERE id=?",
               (hash_password(new), me["id"]))
    # Cierra las demás sesiones abiertas (por si alguien más había entrado).
    keep = hash_token(request.cookies.get(config.COOKIE_NAME, ""))
    db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash!=?", (me["id"], keep))
    return jsonify({"ok": True, "had_password": bool(me["password_hash"])})


# ---------------------------------------------------------------- egresados
def _save_document(upload):
    """Guarda el kárdex/título fuera de /uploads. Devuelve (nombre, None) o (None, error)."""
    if not upload or not upload.filename:
        return None, "Sube una captura o PDF de tu kárdex o título."
    data = upload.read(config.VERIF_MAX_BYTES + 1)
    if len(data) > config.VERIF_MAX_BYTES:
        return None, "El documento debe pesar menos de 6 MB."
    ext = sniff_document(data)
    if not ext:
        return None, "Formato no válido. Sube una imagen (JPG, PNG, WebP) o un PDF."
    name = f"{uuid.uuid4().hex}.{ext}"
    (config.VERIF_DIR / name).write_bytes(data)
    return name, None


def drop_document_file(filename: str):
    if filename:
        try:
            (config.VERIF_DIR / filename).unlink(missing_ok=True)
        except OSError:
            log.warning("No se pudo borrar %s", filename)


def _replace_pending_document(db, user_id: int, doc_type: str, filename: str):
    for old in rows(db.execute(
            "SELECT id, filename FROM alumni_verifications WHERE user_id=? AND status='pending'", (user_id,))):
        drop_document_file(old["filename"])
        db.execute("DELETE FROM alumni_verifications WHERE id=?", (old["id"],))
    db.execute(
        "INSERT INTO alumni_verifications(user_id,doc_type,filename,created_at) VALUES(?,?,?,?)",
        (user_id, doc_type, filename, now()))
    db.execute("UPDATE users SET verif_status='pending' WHERE id=?", (user_id,))
    for a in db.execute("SELECT id FROM users WHERE role='admin'").fetchall():
        notify(db, a["id"], "Hay un egresado esperando verificación de documento.", "#/admin")


@bp.post("/auth/egresado")
def register_alumni():
    form = request.form
    email = normalize_email(form.get("email"))
    name = clean_text(form.get("name"), 80)
    carrera = form.get("carrera", "")
    doc_type = form.get("doc_type", "")
    password = form.get("password")

    if not email:
        return api_error("Escribe un correo válido (puede ser personal).", 400)
    if not name or len(name) < 3:
        return api_error("Escribe tu nombre completo.", 400)
    if carrera not in catalog.CARRERA_A_CENTRO:
        return api_error("Elige tu carrera de la lista.", 400)
    if doc_type not in config.VERIF_DOC_TYPES:
        return api_error("Indica si subes tu kárdex o tu título.", 400)
    problem = password_problem(password)
    if problem:
        return api_error(problem, 400)

    db = get_db()
    existing = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    # Solo se puede volver a registrar un correo egresado que NUNCA confirmó su correo, y solo
    # cuando su código ya venció: así nadie pisa un registro ajeno mientras la persona lo confirma.
    if existing:
        stale = (existing["kind"] == "egresado" and not existing["email_verified"]
                 and now() - existing["created_at"] > config.CODE_TTL_SECONDS)
        if existing["kind"] == "egresado" and not existing["email_verified"] and not stale:
            return api_error("Ese correo ya tiene un registro por confirmar. Revisa tu bandeja "
                             "o intenta de nuevo en unos minutos.", 409)
        if not stale:
            return api_error("Ya existe una cuenta con ese correo. Inicia sesión.", 409)

    filename, err = _save_document(request.files.get("document"))
    if err:
        return api_error(err, 400)

    centro = catalog.centro_de(carrera)
    t = now()
    with tx(db):
        if existing:
            uid = existing["id"]
            db.execute(
                """UPDATE users SET name=?, carrera=?, centro=?, password_hash=?, failed_logins=0,
                   locked_until=0, created_at=? WHERE id=?""",
                (name, carrera, centro, hash_password(password), t, uid))
        else:
            role = "admin" if email in config.ADMINS else "user"
            cur = db.execute(
                """INSERT INTO users(email,name,carrera,centro,role,created_at,password_hash,kind,
                   email_verified,verif_status) VALUES(?,?,?,?,?,?,?,'egresado',0,'pending')""",
                (email, name, carrera, centro, role, t, hash_password(password)))
            uid = cur.lastrowid
        _replace_pending_document(db, uid, doc_type, filename)

    out, err = _issue_code(db, email)   # confirma que el correo es suyo
    if err:
        return err
    out["message"] = "Cuenta creada. Confirma tu correo con el código que te enviamos."
    return jsonify(out)


@bp.post("/auth/egresado/document")
@login_required
def resubmit_document():
    """Egresado con solicitud rechazada (o pendiente) que sube otro documento."""
    if g.user["kind"] != "egresado":
        return api_error("Solo aplica a cuentas de egresado.", 400)
    if g.user["verif_status"] == "approved":
        return api_error("Tu cuenta ya está verificada.", 400)
    doc_type = request.form.get("doc_type", "")
    if doc_type not in config.VERIF_DOC_TYPES:
        return api_error("Indica si subes tu kárdex o tu título.", 400)
    filename, err = _save_document(request.files.get("document"))
    if err:
        return api_error(err, 400)
    db = get_db()
    with tx(db):
        _replace_pending_document(db, g.user["id"], doc_type, filename)
    return jsonify({"ok": True, "verif_status": "pending"})


# ---------------------------------------------------------------- sesión y perfil
@bp.post("/auth/logout")
def logout():
    token = request.cookies.get(config.COOKIE_NAME)
    if token:
        db = get_db()
        db.execute("DELETE FROM sessions WHERE token_hash=?", (hash_token(token),))
    out = jsonify({"ok": True})
    out.delete_cookie(config.COOKIE_NAME, path="/")
    return out


@bp.get("/me")
def me():
    if not g.get("user"):
        return jsonify({"ok": True, "user": None})
    db = get_db()
    uid = g.user["id"]
    unread_msgs = db.execute(
        "SELECT COUNT(*) c FROM messages WHERE receiver_id=? AND read_at IS NULL", (uid,)
    ).fetchone()["c"]
    unread_notes = db.execute(
        "SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read_at IS NULL", (uid,)
    ).fetchone()["c"]
    out = {
        "ok": True, "user": public_user(g.user), "needs_profile": not g.user["name"],
        "unread_messages": unread_msgs, "unread_notifications": unread_notes,
        "needs_verification": g.user["kind"] == "egresado" and g.user["verif_status"] != "approved",
    }
    if g.user["kind"] == "egresado":
        last = db.execute(
            "SELECT doc_type, status, note, created_at FROM alumni_verifications WHERE user_id=? "
            "ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
        out["verification"] = dict(last) if last else None
    return jsonify(out)


@bp.put("/me")
@login_required
def me_update():
    data = request.get_json(silent=True) or {}
    name = clean_text(data.get("name"), 80)
    carrera = data.get("carrera", "")
    if not name or len(name) < 3:
        return api_error("Escribe tu nombre completo.", 400)
    if carrera not in catalog.CARRERA_A_CENTRO:
        return api_error("Elige tu carrera de la lista.", 400)
    centro = catalog.centro_de(carrera)  # el centro sale de la carrera: nunca quedan desalineados
    db = get_db()
    if "bio" in data:  # opcional: solo se toca si el cliente la manda
        bio = clean_text(data.get("bio"), config.BIO_MAX, required=False) or ""
    else:
        bio = g.user["bio"]
    db.execute(
        "UPDATE users SET name=?, carrera=?, centro=?, bio=? WHERE id=?",
        (name, carrera, centro, bio, g.user["id"]),
    )
    row = db.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone()
    return jsonify({"ok": True, "user": public_user(dict(row))})


# ---------------------------------------------------------------- foto de perfil
@bp.post("/me/avatar")
@login_required
def upload_avatar():
    f = request.files.get("avatar")
    if not f or not f.filename:
        return api_error("Elige una imagen.", 400)
    data = f.read(config.AVATAR_MAX_BYTES + 1)
    if len(data) > config.AVATAR_MAX_BYTES:
        return api_error("La foto debe pesar menos de 2 MB.", 400)
    ext = sniff_document(data)
    if ext not in ("jpg", "png", "webp"):
        return api_error("Solo se permiten imágenes JPG, PNG o WebP.", 400)
    name = f"avatar-{uuid.uuid4().hex}.{ext}"
    (config.UPLOADS / name).write_bytes(data)
    db = get_db()
    old = g.user["avatar"]
    db.execute("UPDATE users SET avatar=? WHERE id=?", (name, g.user["id"]))
    _drop_avatar_file(old)
    return jsonify({"ok": True, "avatar": f"/uploads/{name}"})


@bp.delete("/me/avatar")
@login_required
def delete_avatar():
    db = get_db()
    old = g.user["avatar"]
    db.execute("UPDATE users SET avatar='' WHERE id=?", (g.user["id"],))
    _drop_avatar_file(old)
    return jsonify({"ok": True})


def _drop_avatar_file(name: str):
    if name and name.startswith("avatar-"):  # nunca borra fotos de publicaciones
        try:
            (config.UPLOADS / name).unlink(missing_ok=True)
        except OSError:
            log.warning("No se pudo borrar %s", name)
