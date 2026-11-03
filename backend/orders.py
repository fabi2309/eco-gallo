"""Pago retenido: el dinero queda en custodia hasta que el comprador confirma que recibió."""
from flask import Blueprint, g, jsonify, request

from db import get_db, now, rows, tx
from payments import get_provider
from security import api_error, clean_text, login_required, notify

bp = Blueprint("orders", __name__, url_prefix="/api")

LIVE = ("HELD", "DELIVERED", "DISPUTED")


class Conflict(Exception):
    pass


def log_event(db, order_id, actor_id, event, note=""):
    db.execute(
        "INSERT INTO order_events(order_id,actor_id,event,note,created_at) VALUES(?,?,?,?,?)",
        (order_id, actor_id, event, note, now()),
    )


def move(db, order_id: int, allowed: tuple, to: str, **extra) -> dict:
    """Transición atómica de estado; falla si otro proceso ya la cambió."""
    sets = ["status=?", "updated_at=?"] + [f"{k}=?" for k in extra]
    q = ",".join("?" * len(allowed))
    query = f"UPDATE orders SET {','.join(sets)} WHERE id=? AND status IN ({q})"
    cur = db.execute(query, (to, now(), *extra.values(), order_id, *allowed))  # nosec B608
    if cur.rowcount != 1:
        raise Conflict("El estado de la orden cambió. Actualiza la página.")
    return dict(db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())


def actions_for(order: dict, user: dict) -> list[str]:
    st, acts = order["status"], []
    if user["id"] == order["buyer_id"] and st in ("HELD", "DELIVERED"):
        acts += ["confirm", "dispute"]
    if user["id"] == order["seller_id"]:
        if st == "HELD":
            acts.append("deliver")
        if st in ("HELD", "DELIVERED"):
            acts.append("refund")
    if user["role"] == "admin" and st == "DISPUTED":
        acts += ["resolve_release", "resolve_refund"]
    return acts


SELECT_ORDER = """
SELECT o.*, p.title AS post_title, p.tipo AS post_tipo,
       b.name AS buyer_name, s.name AS seller_name,
       (SELECT filename FROM post_images WHERE post_id=p.id ORDER BY position,id LIMIT 1) AS image
FROM orders o
JOIN posts p ON p.id=o.post_id
JOIN users b ON b.id=o.buyer_id
JOIN users s ON s.id=o.seller_id
"""


def serialize(db, o: dict, user: dict, with_events=False) -> dict:
    out = {
        "id": o["id"], "post_id": o["post_id"], "post_title": o["post_title"],
        "amount_cents": o["amount_cents"], "status": o["status"],
        "image": f"/uploads/{o['image']}" if o["image"] else None,
        "buyer": {"id": o["buyer_id"], "name": o["buyer_name"]},
        "seller": {"id": o["seller_id"], "name": o["seller_name"]},
        "role": "buyer" if o["buyer_id"] == user["id"] else
                "seller" if o["seller_id"] == user["id"] else "admin",
        "dispute_reason": o["dispute_reason"], "payment_ref": o["payment_ref"],
        "created_at": o["created_at"], "updated_at": o["updated_at"],
        "actions": actions_for(o, user),
    }
    if with_events:
        out["events"] = rows(db.execute(
            """SELECT e.event, e.note, e.created_at, u.name AS actor
               FROM order_events e LEFT JOIN users u ON u.id=e.actor_id
               WHERE e.order_id=? ORDER BY e.id""", (o["id"],)))
    return out


def _can_view(o, user):
    return user["role"] == "admin" or user["id"] in (o["buyer_id"], o["seller_id"])


@bp.post("/orders")
@login_required
def create_order():
    data = request.get_json(silent=True) or {}
    try:
        pid = int(data.get("post_id"))
    except (TypeError, ValueError):
        return api_error("Publicación inválida.")
    db = get_db()
    provider = get_provider()
    result = None
    with tx(db):
        post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if not post or post["status"] != "active":
            result = api_error("Este artículo ya no está disponible.", 409)
        elif post["tipo"] != "venta" or post["price_cents"] <= 0:
            result = api_error("Solo las ventas usan pago protegido. Contacta al autor por mensaje.", 400)
        elif post["author_id"] == g.user["id"]:
            result = api_error("No puedes comprar tu propia publicación.", 400)
        else:
            # Reserva atómica: solo una persona puede comprar.
            cur = db.execute(
                "UPDATE posts SET status='reserved' WHERE id=? AND status='active'", (pid,)
            )
            if cur.rowcount != 1:
                result = api_error("Alguien más acaba de reservar este artículo.", 409)
            else:
                t = now()
                ref = provider.hold(pid, post["price_cents"], g.user["email"])
                cur = db.execute(
                    """INSERT INTO orders(post_id,buyer_id,seller_id,amount_cents,status,payment_ref,
                                          created_at,updated_at) VALUES(?,?,?,?, 'HELD', ?,?,?)""",
                    (pid, g.user["id"], post["author_id"], post["price_cents"], ref, t, t),
                )
                oid = cur.lastrowid
                log_event(db, oid, g.user["id"], "paid_held",
                          "Pago realizado y retenido por ECO-GALLO hasta que confirmes la recepción.")
                notify(db, post["author_id"],
                       f"{g.user['name']} pagó «{post['title']}». El dinero está retenido: "
                       "entrega el artículo y espera la confirmación.", f"#/order/{oid}")
                result = jsonify({"ok": True, "id": oid}), 201
    return result


@bp.get("/orders")
@login_required
def list_orders():
    db = get_db()
    rs = rows(db.execute(
        f"{SELECT_ORDER} WHERE o.buyer_id=? OR o.seller_id=? ORDER BY o.id DESC LIMIT 100",
        (g.user["id"], g.user["id"])))
    return jsonify({"ok": True, "orders": [serialize(db, o, g.user) for o in rs]})


@bp.get("/orders/<int:oid>")
@login_required
def get_order(oid):
    db = get_db()
    row = db.execute(f"{SELECT_ORDER} WHERE o.id=?", (oid,)).fetchone()
    if not row or not _can_view(dict(row), g.user):
        return api_error("Orden no encontrada.", 404)
    return jsonify({"ok": True, "order": serialize(db, dict(row), g.user, with_events=True)})


def _act(oid, action):
    """Ejecuta una acción del escrow dentro de una transacción."""
    db = get_db()
    data = request.get_json(silent=True) or {}
    provider = get_provider()
    u = g.user
    with tx(db):
        row = db.execute(f"{SELECT_ORDER} WHERE o.id=?", (oid,)).fetchone()
        if not row or not _can_view(dict(row), u):
            return api_error("Orden no encontrada.", 404)
        o = dict(row)
        if action not in actions_for(o, u):
            return api_error("No puedes hacer esto en el estado actual de la orden.", 403)
        title = o["post_title"]
        link = f"#/order/{oid}"
        try:
            if action == "deliver":
                move(db, oid, ("HELD",), "DELIVERED")
                log_event(db, oid, u["id"], "delivered", "El vendedor indica que entregó el artículo.")
                notify(db, o["buyer_id"],
                       f"{o['seller_name']} marcó «{title}» como entregado. Si ya lo tienes, confirma la recepción.", link)
            elif action == "confirm":
                _release(db, o, provider, u["id"], "confirmed",
                         "El comprador confirmó que recibió el artículo. Fondos liberados al vendedor.")
                notify(db, o["seller_id"],
                       f"{o['buyer_name']} confirmó la recepción de «{title}». Se liberó tu pago.", link)
            elif action == "dispute":
                reason = clean_text(data.get("reason"), 500)
                if not reason or len(reason) < 10:
                    return api_error("Cuéntanos qué pasó (mínimo 10 caracteres).")
                move(db, oid, ("HELD", "DELIVERED"), "DISPUTED", dispute_reason=reason)
                log_event(db, oid, u["id"], "disputed", reason)
                notify(db, o["seller_id"], f"{o['buyer_name']} abrió una disputa en «{title}». "
                       "El dinero sigue retenido mientras la administración revisa.", link)
                for a in rows(db.execute("SELECT id FROM users WHERE role='admin'")):
                    notify(db, a["id"], f"Nueva disputa en la orden #{oid} («{title}»).", "#/admin")
            elif action == "refund":
                _refund(db, o, provider, u["id"], "refunded_by_seller",
                        "El vendedor devolvió el pago al comprador.")
                notify(db, o["buyer_id"], f"Te devolvieron el pago de «{title}».", link)
            elif action in ("resolve_release", "resolve_refund"):
                note = clean_text(data.get("note"), 300, required=False) or ""
                if action == "resolve_release":
                    _release(db, o, provider, u["id"], "admin_released",
                             f"La administración liberó el pago al vendedor. {note}".strip())
                else:
                    _refund(db, o, provider, u["id"], "admin_refunded",
                            f"La administración devolvió el pago al comprador. {note}".strip())
                for uid in (o["buyer_id"], o["seller_id"]):
                    notify(db, uid, f"La administración resolvió la disputa de «{title}».", link)
        except Conflict as e:
            return api_error(str(e), 409)
    return jsonify({"ok": True})


def _release(db, o, provider, actor_id, event, note):
    move(db, o["id"], ("HELD", "DELIVERED", "DISPUTED"), "RELEASED")
    provider.release(o["payment_ref"], "", o["amount_cents"])
    db.execute(
        "INSERT INTO wallet_entries(user_id,order_id,amount_cents,kind,created_at) VALUES(?,?,?,?,?)",
        (o["seller_id"], o["id"], o["amount_cents"], "release", now()),
    )
    db.execute("UPDATE posts SET status='sold' WHERE id=?", (o["post_id"],))
    log_event(db, o["id"], actor_id, event, note)


def _refund(db, o, provider, actor_id, event, note):
    move(db, o["id"], ("HELD", "DELIVERED", "DISPUTED"), "REFUNDED")
    provider.refund(o["payment_ref"], o["amount_cents"])
    db.execute("UPDATE posts SET status='active' WHERE id=? AND status='reserved'", (o["post_id"],))
    log_event(db, o["id"], actor_id, event, note)


def _make(action):
    def view(oid):
        return _act(oid, action)
    view.__name__ = f"order_{action}"
    return view


for _a in ("deliver", "confirm", "dispute", "refund", "resolve_release", "resolve_refund"):
    bp.add_url_rule(f"/orders/<int:oid>/{_a.replace('_', '-')}", view_func=login_required(_make(_a)),
                    methods=["POST"], endpoint=f"order_{_a}")


@bp.get("/wallet")
@login_required
def wallet():
    db = get_db()
    uid = g.user["id"]
    released = db.execute(
        "SELECT COALESCE(SUM(amount_cents),0) s FROM wallet_entries WHERE user_id=?", (uid,)
    ).fetchone()["s"]
    pending = db.execute(
        """SELECT COALESCE(SUM(amount_cents),0) s FROM orders
           WHERE seller_id=? AND status IN ('HELD','DELIVERED','DISPUTED')""", (uid,)
    ).fetchone()["s"]
    held_buyer = db.execute(
        """SELECT COALESCE(SUM(amount_cents),0) s FROM orders
           WHERE buyer_id=? AND status IN ('HELD','DELIVERED','DISPUTED')""", (uid,)
    ).fetchone()["s"]
    return jsonify({"ok": True, "available_cents": released, "pending_cents": pending,
                    "buyer_held_cents": held_buyer})
