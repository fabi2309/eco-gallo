"""Mensajería, notificaciones, reportes e impacto ambiental."""
import time

from flask import Blueprint, g, jsonify, request

import config
from badges import user_badges
from db import get_db, now, rows
from security import api_error, clean_text, login_required

bp = Blueprint("social", __name__, url_prefix="/api")


# ------------------------------------------------------------ mensajes
@bp.get("/threads")
@login_required
def threads():
    db = get_db()
    uid = g.user["id"]
    rs = rows(db.execute(
        """
        SELECT m.post_id, p.title AS post_title,
               CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END AS other_id,
               MAX(m.id) AS last_id
        FROM messages m JOIN posts p ON p.id=m.post_id
        WHERE m.sender_id=? OR m.receiver_id=?
        GROUP BY m.post_id, other_id ORDER BY last_id DESC LIMIT 60
        """, (uid, uid, uid)))
    out = []
    for r in rs:
        last = db.execute("SELECT content, created_at, sender_id FROM messages WHERE id=?", (r["last_id"],)).fetchone()
        other = db.execute("SELECT id, name, avatar FROM users WHERE id=?", (r["other_id"],)).fetchone()
        unread = db.execute(
            """SELECT COUNT(*) c FROM messages WHERE post_id=? AND sender_id=? AND receiver_id=?
               AND read_at IS NULL""", (r["post_id"], r["other_id"], uid)).fetchone()["c"]
        out.append({"post_id": r["post_id"], "post_title": r["post_title"],
                    "other": {"id": other["id"], "name": other["name"] or "Usuario",
                              "avatar": f"/uploads/{other['avatar']}" if other["avatar"] else "",
                              "badges": user_badges(db, other["id"])},
                    "last": {"content": last["content"][:120], "created_at": last["created_at"],
                             "mine": last["sender_id"] == uid},
                    "unread": unread})
    return jsonify({"ok": True, "threads": out})


@bp.get("/threads/<int:post_id>/<int:other_id>")
@login_required
def thread(post_id, other_id):
    db = get_db()
    uid = g.user["id"]
    post = db.execute("SELECT id, title, author_id, status, tipo, price_cents FROM posts WHERE id=?", (post_id,)).fetchone()
    other = db.execute("SELECT id, name, carrera, avatar FROM users WHERE id=?", (other_id,)).fetchone()
    if not post or not other or (post["status"] == "pending" and post["author_id"] != uid and g.user["role"] != "admin"):
        return api_error("Conversación no encontrada.", 404)
    msgs = rows(db.execute(
        """SELECT id, sender_id, content, created_at FROM messages WHERE post_id=?
           AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) ORDER BY id""",
        (post_id, uid, other_id, other_id, uid)))
    db.execute(
        "UPDATE messages SET read_at=? WHERE post_id=? AND sender_id=? AND receiver_id=? AND read_at IS NULL",
        (now(), post_id, other_id, uid))
    other = dict(other)
    other["avatar"] = f"/uploads/{other['avatar']}" if other["avatar"] else ""
    other["badges"] = user_badges(db, other["id"])
    return jsonify({"ok": True, "post": dict(post), "other": other, "messages": msgs,
                    "meeting_points": config.SAFE_MEETING_POINTS})


@bp.get("/threads/<int:post_id>/<int:other_id>/since")
@login_required
def thread_since(post_id, other_id):
    """Sondeo ligero del chat (cada ~1 s): solo los mensajes con id mayor a `after`.

    Una sola consulta indexada; así el chat se actualiza en menos de 2 s sin ocupar un hilo
    del servidor por cada conversación abierta (Waitress atiende con un número fijo de hilos).
    """
    try:
        after = max(0, int(request.args.get("after", "0")))
    except ValueError:
        return api_error("Parámetro inválido.")
    db = get_db()
    uid = g.user["id"]
    msgs = rows(db.execute(
        """SELECT id, sender_id, content, created_at FROM messages WHERE post_id=? AND id>?
           AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) ORDER BY id LIMIT 200""",
        (post_id, after, uid, other_id, other_id, uid)))
    if any(m["sender_id"] == other_id for m in msgs):
        db.execute(
            "UPDATE messages SET read_at=? WHERE post_id=? AND sender_id=? AND receiver_id=? AND read_at IS NULL",
            (now(), post_id, other_id, uid))
    # Hasta dónde leyó la otra persona mis mensajes (para el indicador «Visto»).
    seen = db.execute(
        "SELECT COALESCE(MAX(id),0) FROM messages WHERE post_id=? AND sender_id=? AND receiver_id=? AND read_at IS NOT NULL",
        (post_id, uid, other_id)).fetchone()[0]
    return jsonify({"ok": True, "messages": msgs, "seen_up_to": seen, "server_time": now()})


def _cart_count(db, uid):
    return db.execute(
        "SELECT COUNT(*) FROM cart_items c JOIN posts p ON p.id=c.post_id WHERE c.user_id=? AND p.status='active'",
        (uid,)).fetchone()[0]


@bp.get("/pulse")
@login_required
def pulse():
    """Contadores para los avisos globales (campana y mensajes). Consulta barata, pensada para cada 5 s."""
    db = get_db()
    uid = g.user["id"]
    m = db.execute("SELECT COUNT(*), COALESCE(MAX(id),0) FROM messages WHERE receiver_id=? AND read_at IS NULL",
                   (uid,)).fetchone()
    n = db.execute("SELECT COUNT(*), COALESCE(MAX(id),0) FROM notifications WHERE user_id=? AND read_at IS NULL",
                   (uid,)).fetchone()
    latest = db.execute(
        "SELECT text, link FROM notifications WHERE user_id=? AND read_at IS NULL ORDER BY id DESC LIMIT 1",
        (uid,)).fetchone()
    last_msg = db.execute(
        """SELECT m.post_id, m.sender_id, u.name, m.content FROM messages m JOIN users u ON u.id=m.sender_id
           WHERE m.receiver_id=? AND m.read_at IS NULL ORDER BY m.id DESC LIMIT 1""", (uid,)).fetchone()
    return jsonify({
        "ok": True, "unread_messages": m[0], "last_message_id": m[1],
        "unread_notifications": n[0], "last_notification_id": n[1],
        "latest_notification": dict(latest) if latest else None,
        "cart_count": _cart_count(db, uid),
        "latest_message": {"post_id": last_msg["post_id"], "sender_id": last_msg["sender_id"],
                           "name": last_msg["name"], "preview": last_msg["content"][:80]} if last_msg else None,
    })


@bp.post("/messages")
@login_required
def send_message():
    data = request.get_json(silent=True) or {}
    try:
        post_id, receiver_id = int(data.get("post_id")), int(data.get("receiver_id"))
    except (TypeError, ValueError):
        return api_error("Datos inválidos.")
    content = clean_text(data.get("content"), 1000)
    if not content:
        return api_error("Escribe un mensaje.")
    db = get_db()
    uid = g.user["id"]
    post = db.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
    recv = db.execute("SELECT id FROM users WHERE id=? AND suspended=0", (receiver_id,)).fetchone()
    if not post or post["status"] in ("removed", "pending") or not recv or receiver_id == uid:
        return api_error("No se puede enviar este mensaje.", 400)
    # Un lado de la conversación debe ser el autor de la publicación.
    if uid != post["author_id"] and receiver_id != post["author_id"]:
        return api_error("Solo puedes escribirle al autor de la publicación.", 403)
    recent = db.execute(
        "SELECT COUNT(*) c FROM messages WHERE sender_id=? AND created_at>?", (uid, now() - 60)
    ).fetchone()["c"]
    if recent >= 20:
        return api_error("Vas muy rápido. Espera un momento.", 429)
    t = now()
    cur = db.execute(
        "INSERT INTO messages(post_id,sender_id,receiver_id,content,created_at) VALUES(?,?,?,?,?)",
        (post_id, uid, receiver_id, content, t))
    return jsonify({"ok": True, "id": cur.lastrowid,
                    "message": {"id": cur.lastrowid, "sender_id": uid, "content": content, "created_at": t}}), 201


# ------------------------------------------------------- notificaciones
@bp.get("/notifications")
@login_required
def notifications():
    db = get_db()
    rs = rows(db.execute(
        "SELECT id,text,link,created_at,read_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50",
        (g.user["id"],)))
    return jsonify({"ok": True, "notifications": rs})


@bp.post("/notifications/read")
@login_required
def notifications_read():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids')
    if ids is not None:
        if (not isinstance(ids, list) or len(ids) > 50
                or any(type(item) is not int or not 0 < item <= 9223372036854775807 for item in ids)):
            return api_error('Selecciona hasta 50 notificaciones válidas.', 400)
        stamp, uid = now(), g.user['id']
        get_db().executemany(
            "UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL AND id=?",
            [(stamp, uid, item) for item in ids])
    else:
        get_db().execute(
            "UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL", (now(), g.user["id"]))
    return jsonify({"ok": True})


# ------------------------------------------------------------- reportes
@bp.post("/reports")
@login_required
def report():
    data = request.get_json(silent=True) or {}
    ttype = data.get("target_type")
    try:
        tid = int(data.get("target_id"))
    except (TypeError, ValueError):
        return api_error("Datos inválidos.")
    reason = clean_text(data.get("reason"), 400)
    if ttype not in ("post", "user") or not reason or len(reason) < 5:
        return api_error("Cuéntanos el motivo del reporte.")
    db = get_db()
    if ttype == "post":
        exists = db.execute("SELECT 1 FROM posts WHERE id=?", (tid,)).fetchone()
    else:
        exists = db.execute("SELECT 1 FROM users WHERE id=?", (tid,)).fetchone()
    if not exists:
        return api_error("No encontrado.", 404)
    db.execute(
        "INSERT INTO reports(reporter_id,target_type,target_id,reason,created_at) VALUES(?,?,?,?,?)",
        (g.user["id"], ttype, tid, reason, now()))
    return jsonify({"ok": True, "message": "Gracias, la administración revisará el reporte."}), 201


# -------------------------------------------------------------- impacto
def impact_numbers(db) -> dict:
    """Dashboard de impacto (objetivo 5). Ahorro = precio nuevo de referencia − lo que se pagó.

    El precio nuevo sale de lo que declaró el vendedor; si no lo declaró, de NEW_PRICE_EST_CENTS por categoría.
    `declared_share` indica qué parte del ahorro se basa en datos declarados y no en estimaciones.
    """
    users = db.execute("SELECT COUNT(*) c FROM users WHERE name != '' AND deleted_at=0").fetchone()["c"]
    active = db.execute("SELECT COUNT(*) c FROM posts WHERE status IN ('active','reserved')").fetchone()["c"]
    done = rows(db.execute("SELECT category, tipo, price_cents, new_price_cents, closed_at FROM posts WHERE status='sold'"))
    co2 = sum(config.CO2_KG.get(p["category"], 2.0) for p in done)
    money = sum(p["price_cents"] for p in done)
    savings = declared = 0
    months: dict[str, dict] = {}
    for p in done:
        ref = p["new_price_cents"] or config.NEW_PRICE_EST_CENTS.get(p["category"], 300_00)
        saved = max(0, ref - p["price_cents"])
        savings += saved
        declared += saved if p["new_price_cents"] else 0
        if p["closed_at"]:
            key = time.strftime("%Y-%m", time.localtime(p["closed_at"]))
            m = months.setdefault(key, {"month": key, "items": 0, "savings_cents": 0, "co2_kg": 0.0})
            m["items"] += 1
            m["savings_cents"] += saved
            m["co2_kg"] = round(m["co2_kg"] + config.CO2_KG.get(p["category"], 2.0), 1)
    by_cat: dict[str, int] = {}
    for r in rows(db.execute("SELECT category, COUNT(*) c FROM posts WHERE status!='removed' GROUP BY category")):
        by_cat[r["category"]] = r["c"]
    by_tipo = {r["tipo"]: r["c"] for r in rows(db.execute(
        "SELECT tipo, COUNT(*) c FROM posts WHERE status='sold' GROUP BY tipo"))}
    return {"users": users, "active_posts": active, "reused_items": len(done),
            "money_cents": money, "savings_cents": savings,
            "declared_share": round(declared / savings, 3) if savings else 0,
            "co2_kg": round(co2, 1), "posts_by_category": by_cat,
            "reused_by_tipo": by_tipo, "monthly": [months[k] for k in sorted(months)][-12:],
            "updated_at": now(),
            "co2_note": "Estimación orientativa por categoría, no una medición."}


@bp.get("/impact")
@login_required
def impact():
    return jsonify({"ok": True, **impact_numbers(get_db())})
