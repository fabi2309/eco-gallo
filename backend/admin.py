"""Panel administrativo: disputas, reportes, usuarios y estadísticas."""
from flask import Blueprint, g, jsonify, request, send_from_directory

import config
from auth import drop_document_file
from db import get_db, now, rows, tx
from orders import SELECT_ORDER, serialize as serialize_order
from security import admin_required, api_error, clean_text, notify
from social import impact_numbers

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/overview")
@admin_required
def overview():
    db = get_db()
    disputes = [serialize_order(db, o, g.user, with_events=True) for o in rows(db.execute(
        f"{SELECT_ORDER} WHERE o.status='DISPUTED' ORDER BY o.updated_at"))]
    reports = rows(db.execute(
        """SELECT r.id, r.target_type, r.target_id, r.reason, r.created_at, u.name AS reporter,
                  CASE r.target_type WHEN 'post' THEN (SELECT title FROM posts WHERE id=r.target_id)
                       ELSE (SELECT email FROM users WHERE id=r.target_id) END AS target_label
           FROM reports r JOIN users u ON u.id=r.reporter_id WHERE r.status='open' ORDER BY r.id"""))
    held = db.execute(
        "SELECT COALESCE(SUM(amount_cents),0) s, COUNT(*) c FROM orders WHERE status IN ('HELD','DELIVERED','DISPUTED')"
    ).fetchone()
    users = rows(db.execute(
        "SELECT id,email,name,carrera,centro,role,suspended,created_at,kind,verif_status "
        "FROM users ORDER BY id DESC LIMIT 100"))
    verifications = rows(db.execute(
        """SELECT v.id, v.doc_type, v.filename, v.created_at, u.id AS user_id, u.name, u.email,
                  u.carrera, u.centro
           FROM alumni_verifications v JOIN users u ON u.id=v.user_id
           WHERE v.status='pending' ORDER BY v.id"""))
    for v in verifications:
        v["doc_label"] = config.VERIF_DOC_TYPES.get(v["doc_type"], v["doc_type"])
        v["is_pdf"] = v.pop("filename").lower().endswith(".pdf")
    return jsonify({"ok": True, "stats": impact_numbers(db), "disputes": disputes, "reports": reports,
                    "held": {"cents": held["s"], "orders": held["c"]}, "users": users,
                    "verifications": verifications})


@bp.get("/verifications/<int:vid>/file")
@admin_required
def verification_file(vid):
    """Documento privado de un egresado: solo lo ve un administrador."""
    row = get_db().execute(
        "SELECT filename FROM alumni_verifications WHERE id=? AND status='pending'", (vid,)).fetchone()
    if not row or not row["filename"]:
        return api_error("Documento no disponible.", 404)
    resp = send_from_directory(config.VERIF_DIR, row["filename"])
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Disposition"] = "inline"
    return resp


@bp.post("/verifications/<int:vid>/review")
@admin_required
def review_verification(vid):
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    note = clean_text(data.get("note"), 300, required=False) or ""
    if action not in ("approve", "reject"):
        return api_error("Acción inválida.", 400)
    if action == "reject" and len(note) < 5:
        return api_error("Escribe el motivo del rechazo para que el egresado sepa qué corregir.", 400)

    db = get_db()
    resp, to_delete = None, ""
    with tx(db):
        v = db.execute("SELECT * FROM alumni_verifications WHERE id=? AND status='pending'", (vid,)).fetchone()
        if not v:
            resp = api_error("Solicitud no encontrada o ya resuelta.", 404)
        else:
            status = "approved" if action == "approve" else "rejected"
            to_delete = v["filename"]
            # El documento tiene datos personales: se borra en cuanto hay decisión.
            db.execute(
                "UPDATE alumni_verifications SET status=?, note=?, reviewer_id=?, reviewed_at=?, filename='' WHERE id=?",
                (status, note, g.user["id"], now(), vid))
            db.execute("UPDATE users SET verif_status=? WHERE id=?", (status, v["user_id"]))
            if action == "approve":
                notify(db, v["user_id"], "¡Listo! Verificamos que eres egresado de la UAA. Ya puedes usar ECO-GALLO.", "#/")
            else:
                notify(db, v["user_id"], f"No pudimos verificar tu documento: {note}", "#/")
            resp = jsonify({"ok": True, "status": status})
    drop_document_file(to_delete)
    return resp


@bp.post("/reports/<int:rid>/resolve")
@admin_required
def resolve_report(rid):
    action = (request.get_json(silent=True) or {}).get("action")
    db = get_db()
    resp = None
    with tx(db):
        r = db.execute("SELECT * FROM reports WHERE id=? AND status='open'", (rid,)).fetchone()
        if not r:
            resp = api_error("Reporte no encontrado.", 404)
        elif action == "remove_post" and r["target_type"] == "post":
            post = db.execute("SELECT * FROM posts WHERE id=?", (r["target_id"],)).fetchone()
            if post and post["status"] == "reserved":
                resp = api_error("Hay un pago retenido en esa publicación; resuélvelo primero.", 409)
            else:
                db.execute("UPDATE posts SET status='removed' WHERE id=?", (r["target_id"],))
                if post:
                    notify(db, post["author_id"], f"Tu publicación «{post['title']}» fue retirada por moderación.", "")
        elif action == "suspend_user" and r["target_type"] == "user":
            if r["target_id"] == g.user["id"]:
                resp = api_error("No puedes suspenderte a ti mismo.", 400)
            else:
                db.execute("UPDATE users SET suspended=1 WHERE id=?", (r["target_id"],))
                db.execute("DELETE FROM sessions WHERE user_id=?", (r["target_id"],))
        elif action != "dismiss":
            resp = api_error("Acción inválida.", 400)
        if resp is None:
            db.execute("UPDATE reports SET status='resolved' WHERE id=?", (rid,))
            resp = jsonify({"ok": True})
    return resp


@bp.post("/users/<int:uid>/suspend")
@admin_required
def suspend(uid):
    suspended = 1 if (request.get_json(silent=True) or {}).get("suspended", True) else 0
    if uid == g.user["id"]:
        return api_error("No puedes suspenderte a ti mismo.", 400)
    db = get_db()
    db.execute("UPDATE users SET suspended=? WHERE id=?", (suspended, uid))
    if suspended:
        db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    return jsonify({"ok": True})


# ------------------------------------------------------------- Respaldos
@bp.get("/backups")
@admin_required
def get_backups():
    from backups import list_backups
    return jsonify({
        "ok": True,
        "backups": list_backups(),
        "config": {
            "enabled": config.BACKUP_ENABLED,
            "interval_hours": config.BACKUP_INTERVAL_HOURS,
            "keep": config.BACKUP_KEEP,
        },
    })


@bp.post("/backups")
@admin_required
def trigger_backup():
    from backups import create_backup
    tag = (request.get_json(silent=True) or {}).get("tag", "manual")
    info = create_backup(tag=tag)
    return jsonify({"ok": True, "backup": info})


@bp.get("/backups/<filename>/download")
@admin_required
def download_backup(filename):
    from backups import get_backup_path
    path = get_backup_path(filename)
    if not path:
        return api_error("Archivo de respaldo no encontrado.", 404)
    resp = send_from_directory(config.BACKUPS_DIR, path.name, as_attachment=True)
    resp.headers["Cache-Control"] = "no-store, private"
    return resp


@bp.delete("/backups/<filename>")
@admin_required
def remove_backup(filename):
    from backups import delete_backup
    if not delete_backup(filename):
        return api_error("No se pudo eliminar el archivo de respaldo.", 404)
    return jsonify({"ok": True})


@bp.post("/backups/<filename>/restore")
@admin_required
def restore_system_backup(filename):
    from backups import get_backup_path, restore_backup
    path = get_backup_path(filename)
    if not path:
        return api_error("Archivo de respaldo no encontrado.", 404)

    token = request.cookies.get(config.COOKIE_NAME)
    try:
        result = restore_backup(filename, session_token=token, admin_user=g.user)
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception as e:
        import logging
        logging.getLogger("ecogallo.backups").exception("Error al restaurar respaldo: %s", e)
        return api_error("Error interno al restaurar el respaldo.", 500)

    return jsonify({"ok": True, "restore": result, "message": "Respaldo restaurado exitosamente."})


@bp.post("/backups/upload")
@admin_required
def upload_backup_file():
    file = request.files.get("backup_file")
    if not file or not file.filename:
        return api_error("No se seleccionó ningún archivo de respaldo.", 400)
    if not file.filename.lower().endswith(".zip"):
        return api_error("El archivo debe ser un paquete .zip.", 400)

    from backups import save_uploaded_backup
    try:
        info = save_uploaded_backup(file)
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception as e:
        import logging
        logging.getLogger("ecogallo.backups").exception("Error al guardar respaldo subido: %s", e)
        return api_error("Error interno al procesar el archivo subido.", 500)

    return jsonify({"ok": True, "backup": info, "message": "Respaldo subido y verificado exitosamente."})
