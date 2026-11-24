"""Derechos ARCO (LFPDPPP): consentimiento, acceso (descarga de datos) y cancelación (baja de cuenta).

- Acceso: GET /api/me/export entrega un JSON con todos los datos personales de la cuenta.
- Rectificación: PUT /api/me (auth.py) permite corregir nombre, carrera y biografía.
- Cancelación: DELETE /api/me anonimiza la cuenta con el mismo procedimiento que usa administración.
- Oposición: el aviso de privacidad indica el correo del responsable para ejercerla.
"""
import json

from flask import Blueprint, Response, g, jsonify, request

import config
from db import get_db, now, rows, tx
from payment_states import OPEN_SQL
from security import (
    api_error, check_password, decrypt_totp_secret, hash_token, login_required, verify_totp_counter,
)

bp = Blueprint("accounts", __name__, url_prefix="/api")

DELETE_WORD = "ELIMINAR"


def legal_info() -> dict:
    """Datos públicos del responsable que se muestran en el aviso de privacidad."""
    return {
        "version": config.LEGAL_VERSION,
        "operator": config.OPERATOR_NAME,
        "email": config.PRIVACY_EMAIL,
        "address": config.OPERATOR_ADDRESS,
    }


def needs_terms(user: dict) -> bool:
    return user.get("terms_version", "") != config.LEGAL_VERSION


def record_terms(db, user_id: int):
    db.execute("UPDATE users SET terms_version=?, terms_accepted_at=? WHERE id=?",
               (config.LEGAL_VERSION, now(), user_id))


# ------------------------------------------------------------------ cuenta de administración inicial
ADMIN_NAME = "Administrador ECO-GALLO"


def bootstrap_admin() -> str | None:
    """Deja lista la cuenta de ECOGALLO_ADMINS (la primera) para entrar con ECOGALLO_ADMIN_PASSWORD.

    - Si no existe, la crea con perfil completo.
    - Si ya existía (por ejemplo, creada antes entrando con código), completa lo que le falte: nombre,
      carrera, centro, rol de administración, correo verificado y aceptación de términos.
    - Contraseña: en desarrollo siempre queda la configurada (la de .env o la de demostración), para que
      las credenciales documentadas funcionen aunque la base venga de una versión anterior. En producción
      solo se pone si la cuenta no tiene ninguna; nunca se sobrescribe.
    Devuelve el correo si hizo algún cambio.
    """
    from catalog import centro_de
    from db import connect
    from security import check_password, hash_password, password_problem
    email, pw = config.ADMIN_EMAIL, config.ADMIN_PASSWORD
    if not email or not pw or password_problem(pw):
        return None
    carrera = "Ingeniería en Sistemas Computacionales"
    centro = centro_de(carrera) or "General"
    con = connect()
    try:
        t = now()
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row is None:
            con.execute(
                """INSERT INTO users(email,name,carrera,centro,role,password_hash,email_verified,created_at,
                                     terms_version,terms_accepted_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (email, ADMIN_NAME, carrera, centro, "admin", hash_password(pw), 1, t, config.LEGAL_VERSION, t))
            return email
        u, changes = dict(row), {}
        placeholder = (u.get("name") or "").strip().lower() in ("", email.split("@")[0].lower(), "admin")
        if placeholder:
            changes["name"] = ADMIN_NAME
        if not u.get("carrera"):
            changes["carrera"] = carrera
        if not u.get("centro"):
            changes["centro"] = centro
        if u.get("role") != "admin":
            changes["role"] = "admin"
        if not u.get("email_verified"):
            changes["email_verified"] = 1
        if u.get("terms_version") != config.LEGAL_VERSION:
            changes.update(terms_version=config.LEGAL_VERSION, terms_accepted_at=t)
        if not u.get("password_hash") or (config.DEV and not config.PRODUCTION
                                          and not check_password(u, pw)):
            changes["password_hash"] = hash_password(pw)
        if u.get("suspended"):
            changes["suspended"] = 0
        if not changes:
            return None
        sets = ",".join(f"{k}=?" for k in changes)
        con.execute(f"UPDATE users SET {sets} WHERE id=?", (*changes.values(), u["id"]))  # nosec B608 - claves fijas
        return email
    finally:
        con.close()


# ------------------------------------------------------------------ anonimización
def anonymize_account(db, uid: int, email: str) -> dict:
    """Borra los datos personales de una cuenta dentro de una transacción abierta.

    No se hace DELETE de la fila porque órdenes, mensajes y reportes de *otras* personas la
    referencian. Se borran correo, nombre, carrera, bio, foto, contraseña, sesiones, notificaciones,
    deseos, favoritos, documentos de egresado, códigos y fotos de publicaciones; los mensajes enviados
    pierden el texto. Se conserva solo lo necesario para el historial (ids, montos, estados).
    Devuelve los archivos que hay que borrar del disco después del COMMIT.
    """
    u = db.execute("SELECT avatar FROM users WHERE id=?", (uid,)).fetchone()
    doc_files = [r["filename"] for r in db.execute(
        "SELECT filename FROM alumni_verifications WHERE user_id=?", (uid,)) if r["filename"]]
    files = [r["filename"] for r in db.execute(
        "SELECT i.filename FROM post_images i JOIN posts p ON p.id=i.post_id WHERE p.author_id=?", (uid,))]
    db.execute("DELETE FROM post_images WHERE post_id IN (SELECT id FROM posts WHERE author_id=?)", (uid,))
    db.execute("UPDATE posts SET status='removed', description='' WHERE author_id=?", (uid,))
    db.execute("UPDATE messages SET content='[mensaje eliminado]' WHERE sender_id=?", (uid,))
    for table in ("sessions", "notifications", "wishlist", "alumni_verifications",
                  "favorites", "auth_challenges", "totp_recovery_codes"):
        db.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))  # nosec B608 - tabla tomada de tupla fija
    db.execute("DELETE FROM login_codes WHERE email=?", (email,))
    db.execute("UPDATE reports SET status='resolved' WHERE target_type='user' AND target_id=?", (uid,))
    db.execute(
        """UPDATE users SET email=?, name='Cuenta eliminada', carrera='', centro='General', bio='', avatar='',
           password_hash='', totp_enabled=0, totp_secret='', totp_pending_secret='',
           totp_pending_expires_at=0, suspended=1, kind='estudiante', verif_status='approved', email_verified=0,
           failed_logins=0, locked_until=0, stripe_account_id='', phone='', phone_verified_at=0,
           payout_kind='', payout_last4='', payout_holder='', deleted_at=? WHERE id=?""",
        (f"eliminado-{uid}@eliminado.invalid", now(), uid))
    return {"avatar": u["avatar"] if u else "", "files": files, "doc_files": doc_files}


def drop_account_files(removed: dict):
    from auth import _drop_avatar_file, drop_document_file
    _drop_avatar_file(removed.get("avatar", ""))
    for name in removed.get("files", []):
        try:
            (config.UPLOADS / name).unlink(missing_ok=True)
        except OSError:
            pass
    for name in removed.get("doc_files", []):
        drop_document_file(name)


def has_open_orders(db, uid: int) -> bool:
    """Operaciones abiertas o ventas que la plataforma aún debe liquidar al vendedor."""
    return bool(db.execute(
        f"SELECT 1 FROM orders WHERE ((buyer_id=? OR seller_id=?) AND status IN {OPEN_SQL}) "  # nosec B608 - constante
        "OR (seller_id=? AND payout_status='pending')",
        (uid, uid, uid)).fetchone())


# ------------------------------------------------------------------ consentimiento
@bp.get("/legal")
def legal():
    from legal_documents import documents
    info = legal_info()
    return jsonify({"ok": True, **info, "documents": documents(info)})


@bp.post("/me/terms")
@login_required
def accept_terms():
    data = request.get_json(silent=True) or {}
    if data.get("accept") is not True or data.get("version") != config.LEGAL_VERSION:
        return api_error("Para continuar debes aceptar el aviso de privacidad y los términos vigentes.", 400)
    record_terms(get_db(), g.user["id"])
    return jsonify({"ok": True, "version": config.LEGAL_VERSION})


# ------------------------------------------------------------------ acceso (descarga)
def _export(db, uid: int) -> dict:
    u = dict(db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
    profile = {k: u[k] for k in ("id", "email", "name", "carrera", "centro", "kind", "verif_status", "bio",
                                 "role", "created_at", "terms_version", "terms_accepted_at")}
    profile["avatar"] = f"/uploads/{u['avatar']}" if u["avatar"] else ""
    profile["has_password"] = bool(u["password_hash"])
    profile["totp_enabled"] = bool(u["totp_enabled"])
    profile["phone"] = u["phone"]
    profile["phone_verified_at"] = u["phone_verified_at"]
    profile["payout_account"] = ({"kind": u["payout_kind"], "last4": u["payout_last4"], "holder": u["payout_holder"]}
                                 if u["payout_kind"] else None)

    posts = rows(db.execute(
        "SELECT id,title,description,category,centro,tipo,price_cents,condition,status,views_count,created_at "
        "FROM posts WHERE author_id=? ORDER BY id", (uid,)))
    for p in posts:
        p["images"] = [f"/uploads/{r['filename']}" for r in db.execute(
            "SELECT filename FROM post_images WHERE post_id=? ORDER BY position,id", (p["id"],))]
    messages = rows(db.execute(
        """SELECT m.id, m.post_id, p.title AS post_title,
                  CASE WHEN m.sender_id=? THEN 'enviado' ELSE 'recibido' END AS direction,
                  CASE WHEN m.sender_id=? THEN r.name ELSE s.name END AS other_person,
                  m.content, m.created_at, m.read_at
           FROM messages m JOIN users s ON s.id=m.sender_id JOIN users r ON r.id=m.receiver_id
           LEFT JOIN posts p ON p.id=m.post_id
           WHERE m.sender_id=? OR m.receiver_id=? ORDER BY m.id""", (uid, uid, uid, uid)))
    orders = rows(db.execute(
        """SELECT o.id, o.post_id, p.title AS post_title,
                  CASE WHEN o.buyer_id=? THEN 'compra' ELSE 'venta' END AS role,
                  o.amount_cents, o.status, o.payment_provider, o.dispute_reason, o.created_at, o.updated_at
           FROM orders o LEFT JOIN posts p ON p.id=o.post_id
           WHERE o.buyer_id=? OR o.seller_id=? ORDER BY o.id""", (uid, uid, uid)))
    return {
        "generated_at": now(),
        "notice": "Copia de tus datos personales en ECO-GALLO UAA (derecho de acceso, LFPDPPP). "
                  "No incluye contraseñas ni secretos de autenticación, que se guardan cifrados o como hash.",
        "profile": profile,
        "posts": posts,
        "messages": messages,
        "orders": orders,
        "favorites": rows(db.execute(
            "SELECT f.post_id, p.title, f.created_at FROM favorites f LEFT JOIN posts p ON p.id=f.post_id "
            "WHERE f.user_id=? ORDER BY f.id", (uid,))),
        "wishlist": rows(db.execute(
            "SELECT term, category, centro, created_at FROM wishlist WHERE user_id=? ORDER BY id", (uid,))),
        "notifications": rows(db.execute(
            "SELECT text, link, created_at, read_at FROM notifications WHERE user_id=? ORDER BY id", (uid,))),
        "reports_made": rows(db.execute(
            "SELECT target_type, target_id, reason, status, created_at FROM reports WHERE reporter_id=? ORDER BY id",
            (uid,))),
        "alumni_verifications": rows(db.execute(
            "SELECT doc_type, status, note, created_at, reviewed_at FROM alumni_verifications WHERE user_id=? "
            "ORDER BY id", (uid,))),
        "wallet": rows(db.execute(
            "SELECT order_id, amount_cents, kind, created_at FROM wallet_entries WHERE user_id=? ORDER BY id",
            (uid,))),
        "active_sessions": db.execute("SELECT COUNT(*) FROM sessions WHERE user_id=? AND expires_at>?",
                                      (uid, now())).fetchone()[0],
    }


@bp.get("/me/export")
@login_required
def export_data():
    data = _export(get_db(), g.user["id"])
    body = json.dumps(data, ensure_ascii=False, indent=2)
    resp = Response(body, mimetype="application/json")
    resp.headers["Content-Disposition"] = 'attachment; filename="mis-datos-ecogallo.json"'
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


# ------------------------------------------------------------------ cancelación (baja)
@bp.delete("/me")
@login_required
def delete_me():
    """Baja voluntaria. Exige la palabra de confirmación y volver a demostrar identidad:
    contraseña (si la cuenta tiene) o un acceso reciente por código al correo, más 2FA si está activo."""
    data = request.get_json(silent=True) or {}
    if str(data.get("confirm", "")).strip().upper() != DELETE_WORD:
        return api_error(f"Escribe {DELETE_WORD} para confirmar.", 400)
    db = get_db()
    token_hash = hash_token(request.cookies.get(config.COOKIE_NAME, ""))
    removed, resp = None, None
    with tx(db):
        u = dict(db.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone())
        session = db.execute("SELECT reset_until FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
        recent_code = bool(session and session["reset_until"] > now())
        if u["role"] == "admin":
            resp = api_error("Una cuenta de administración no puede darse de baja sola. "
                             "Pide que te retiren el rol primero.", 400)
        elif u["password_hash"] and not check_password(u, data.get("password")):
            resp = api_error("La contraseña no es correcta.", 400)
        elif not u["password_hash"] and not recent_code:
            resp = api_error("Por seguridad, cierra sesión y vuelve a entrar con un código a tu correo; "
                             "después tendrás 10 minutos para eliminar la cuenta.", 403, needs_recent_login=True)
        elif u["totp_enabled"] and not _totp_ok(db, u, str(data.get("code", "")).strip()):
            resp = api_error("El código de tu autenticador no es correcto.", 400)
        elif has_open_orders(db, u["id"]):
            resp = api_error("Tienes compras o ventas en curso (pago retenido, entrega, disputa o un pago "
                             "pendiente de recibir). Termínalas antes de eliminar tu cuenta.", 409)
        else:
            removed = anonymize_account(db, u["id"], u["email"])
    if resp is not None:
        return resp
    drop_account_files(removed)
    out = jsonify({"ok": True, "message": "Tu cuenta y tus datos personales fueron eliminados."})
    out.delete_cookie(config.COOKIE_NAME, path="/")
    return out


def _totp_ok(db, user: dict, code: str) -> bool:
    if not (code.isdigit() and len(code) == 6):
        return False
    try:
        secret = decrypt_totp_secret(user["totp_secret"])
    except Exception:  # noqa: BLE001 - secreto ilegible: no se acepta
        return False
    counter = verify_totp_counter(secret, code, user["totp_last_counter"])
    if counter is None:
        return False
    db.execute("UPDATE users SET totp_last_counter=? WHERE id=?", (counter, user["id"]))
    return True
