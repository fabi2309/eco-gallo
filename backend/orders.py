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
    query = f"UPDATE orders SET {','.join(sets)} WHERE id=? AND status IN ({q})"  # nosec B608 - claves de extra las fija el código, valores parametrizados
    cur = db.execute(query, (to, now(), *extra.values(), order_id, *allowed))
    if cur.rowcount != 1:
        raise Conflict("El estado de la orden cambió. Actualiza la página.")
    return dict(db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())


def actions_for(order: dict, user: dict) -> list[str]:
    st, acts = order["status"], []

    if user["id"] == order["buyer_id"]:
        if st in ("HELD", "DELIVERED", "RELEASING"):
            acts.append("confirm")
        if st in ("HELD", "DELIVERED"):
            acts.append("dispute")

    if user["id"] == order["seller_id"]:
        if st == "HELD":
            acts.append("deliver")
        if st in ("HELD", "DELIVERED", "REFUNDING"):
            acts.append("refund")

    if user["role"] == "admin":
        if st == "DISPUTED":
            acts += ["resolve_release", "resolve_refund"]
        elif st == "RELEASING":
            acts.append("resolve_release")
        elif st == "REFUNDING":
            acts.append("resolve_refund")

    return acts


SELECT_ORDER = """
SELECT o.*, p.title AS post_title, p.tipo AS post_tipo,
       b.name AS buyer_name, s.name AS seller_name,
       s.stripe_account_id AS seller_stripe_account_id,
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
    is_stripe = provider.name == "stripe"

    with tx(db):
        post = db.execute(
            "SELECT * FROM posts WHERE id=?", (pid,)
        ).fetchone()

        if not post or post["status"] != "active":
            return api_error(
                "Este artículo ya no está disponible.", 409
            )

        if post["tipo"] != "venta" or post["price_cents"] <= 0:
            return api_error(
                "Solo las ventas usan pago protegido. Contacta al autor por mensaje.",
                400,
            )

        if post["author_id"] == g.user["id"]:
            return api_error(
                "No puedes comprar tu propia publicación.", 400
            )

        cur = db.execute(
            "UPDATE posts SET status='reserved' "
            "WHERE id=? AND status='active'",
            (pid,),
        )

        if cur.rowcount != 1:
            return api_error(
                "Alguien más acaba de reservar este artículo.", 409
            )

        t = now()

        if is_stripe:
            payment_ref = ""
            status = "PENDING_PAYMENT"
        else:
            payment_ref = provider.hold(
                pid, post["price_cents"], g.user["email"]
            )
            status = "HELD"

        cur = db.execute(
            """INSERT INTO orders(
                post_id, buyer_id, seller_id, amount_cents,
                status, payment_ref, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                pid,
                g.user["id"],
                post["author_id"],
                post["price_cents"],
                status,
                payment_ref,
                t,
                t,
            ),
        )

        oid = cur.lastrowid

        if is_stripe:
            log_event(
                db,
                oid,
                g.user["id"],
                "payment_pending",
                "Orden creada. Esperando el pago mediante Stripe Checkout.",
            )
        else:
            log_event(
                db,
                oid,
                g.user["id"],
                "paid_held",
                "Pago realizado y retenido por ECO-GALLO hasta que confirmes la recepción.",
            )
            notify(
                db,
                post["author_id"],
                f"{g.user['name']} pagó «{post['title']}». "
                "El dinero está retenido: entrega el artículo y espera la confirmación.",
                f"#/order/{oid}",
            )

    if not is_stripe:
        return jsonify({"ok": True, "id": oid}), 201

    try:
        checkout = provider.start_checkout(
            oid,
            post["price_cents"],
            g.user["email"],
        )

        if not checkout.get("checkout_url"):
            raise RuntimeError("Stripe no devolvió una URL de Checkout.")

        with tx(db):
            db.execute(
                """UPDATE orders
                   SET payment_ref=?, stripe_session_id=?, updated_at=?
                   WHERE id=? AND status='PENDING_PAYMENT'""",
                (
                    checkout["payment_ref"],
                    checkout["session_id"],
                    now(),
                    oid,
                ),
            )

        return jsonify({
            "ok": True,
            "id": oid,
            "checkout_url": checkout["checkout_url"],
        }), 201

    except Exception:
        with tx(db):
            db.execute(
                """UPDATE orders
                   SET status='CANCELLED', updated_at=?
                   WHERE id=? AND status='PENDING_PAYMENT'""",
                (now(), oid),
            )
            db.execute(
                "UPDATE posts SET status='active' "
                "WHERE id=? AND status='reserved'",
                (pid,),
            )
            log_event(
                db,
                oid,
                g.user["id"],
                "payment_failed",
                "No se pudo iniciar la sesión de pago.",
            )

        return api_error(
            "No se pudo iniciar el pago con Stripe. Inténtalo nuevamente.",
            502,
        )


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
    """Ejecuta las acciones de una orden sin mantener abierta una transacción durante llamadas a Stripe."""
    db = get_db()
    data = request.get_json(silent=True) or {}
    provider = get_provider()
    u = g.user

    target_status = (
        "RELEASING"
        if action in ("confirm", "resolve_release")
        else "REFUNDING"
    )

    payment_action = action in (
        "confirm", "refund", "resolve_release", "resolve_refund"
    )

    with tx(db):
        row = db.execute(
            f"{SELECT_ORDER} WHERE o.id=?", (oid,)
        ).fetchone()

        if not row or not _can_view(dict(row), u):
            return api_error("Orden no encontrada.", 404)

        o = dict(row)

        if action not in actions_for(o, u):
            return api_error(
                "No puedes hacer esto en el estado actual de la orden.",
                403,
            )

        title = o["post_title"]
        link = f"#/order/{oid}"

        if action == "deliver":
            move(db, oid, ("HELD",), "DELIVERED")
            log_event(
                db, oid, u["id"], "delivered",
                "El vendedor indica que entregó el artículo.",
            )
            notify(
                db, o["buyer_id"],
                f"{o['seller_name']} marcó «{title}» como entregado. "
                "Si ya lo tienes, confirma la recepción.",
                link,
            )
            return jsonify({"ok": True})

        if action == "dispute":
            reason = clean_text(data.get("reason"), 500)

            if not reason or len(reason) < 10:
                return api_error(
                    "Cuéntanos qué pasó (mínimo 10 caracteres)."
                )

            move(
                db, oid, ("HELD", "DELIVERED"),
                "DISPUTED", dispute_reason=reason,
            )
            log_event(db, oid, u["id"], "disputed", reason)

            notify(
                db, o["seller_id"],
                f"{o['buyer_name']} abrió una disputa en «{title}». "
                "El dinero sigue retenido mientras la administración revisa.",
                link,
            )

            for admin in rows(
                db.execute("SELECT id FROM users WHERE role='admin'")
            ):
                notify(
                    db, admin["id"],
                    f"Nueva disputa en la orden #{oid} («{title}»).",
                    "#/admin",
                )

            return jsonify({"ok": True})

        if not payment_action:
            return api_error("Acción no reconocida.", 400)

        retrying = o["status"] == target_status
        previous_status = None if retrying else o["status"]

        if not retrying:
            allowed = (
                ("HELD", "DELIVERED")
                if action in ("confirm", "refund")
                else ("DISPUTED",)
            )

            try:
                move(db, oid, allowed, target_status)
            except Conflict as e:
                return api_error(str(e), 409)

    # La llamada externa se realiza fuera de la transacción SQLite.
    try:
        if target_status == "RELEASING":
            transfer_id = provider.release(
                oid,
                o.get("stripe_charge_id") or "",
                o.get("seller_stripe_account_id") or "",
                o["amount_cents"],
            )
        else:
            provider.refund(
                oid,
                o.get("stripe_payment_intent_id") or "",
                o["amount_cents"],
            )

    except Exception:
        # Si es el primer intento, restauramos el estado anterior.
        # Si es un reintento, conservamos el estado temporal para
        # permitir otro intento sin perder la operación pendiente.
        with tx(db):
            if not retrying:
                db.execute(
                    """UPDATE orders
                       SET status=?, updated_at=?
                       WHERE id=? AND status=?""",
                    (previous_status, now(), oid, target_status),
                )

            log_event(
                db,
                oid,
                u["id"],
                "payment_operation_failed",
                "No se pudo completar la operación de pago. "
                "Se puede volver a intentar.",
            )

        return api_error(
            "No se pudo completar la operación con Stripe. "
            "La orden conserva su estado para permitir un reintento.",
            502,
        )

    # Stripe respondió correctamente. Ahora confirmamos el resultado
    # en la base de datos.
    with tx(db):
        current = db.execute(
            f"{SELECT_ORDER} WHERE o.id=?", (oid,)
        ).fetchone()

        if not current or current["status"] != target_status:
            return api_error(
                "La operación de pago se procesó, pero el estado de "
                "la orden cambió. Se requiere revisión.",
                409,
            )

        o = dict(current)

        if target_status == "RELEASING":
            if action == "confirm":
                event = "confirmed"
                note = (
                    "El comprador confirmó que recibió el artículo. "
                    "Fondos liberados al vendedor."
                )
            else:
                event = "admin_released"
                note = (
                    "La administración liberó el pago al vendedor. "
                    + (
                        clean_text(data.get("note"), 300, required=False)
                        or ""
                    )
                ).strip()

            _release(
                db, o, transfer_id, u["id"], event, note
            )

            notify(
                db, o["seller_id"],
                f"{o['buyer_name']} confirmó la recepción de «{title}». "
                "Se liberó tu pago.",
                link,
            )

        else:
            if action == "refund":
                event = "refunded_by_seller"
                note = "El vendedor devolvió el pago al comprador."
            else:
                event = "admin_refunded"
                note = (
                    "La administración devolvió el pago al comprador. "
                    + (
                        clean_text(data.get("note"), 300, required=False)
                        or ""
                    )
                ).strip()

            _refund(db, o, u["id"], event, note)

            notify(
                db, o["buyer_id"],
                f"Te devolvieron el pago de «{title}».",
                link,
            )

            if action == "resolve_refund":
                notify(
                    db, o["seller_id"],
                    f"La administración resolvió la disputa de «{title}».",
                    link,
                )

    return jsonify({"ok": True})


def _release(db, o, transfer_id, actor_id, event, note):
    move(
        db, o["id"], ("RELEASING",), "RELEASED",
        stripe_transfer_id=transfer_id or "",
    )

    db.execute(
        """INSERT INTO wallet_entries(
            user_id, order_id, amount_cents, kind, created_at
        ) VALUES(?,?,?,?,?)""",
        (
            o["seller_id"],
            o["id"],
            o["amount_cents"],
            "release",
            now(),
        ),
    )

    db.execute(
        "UPDATE posts SET status='sold' WHERE id=?",
        (o["post_id"],),
    )

    log_event(db, o["id"], actor_id, event, note)


def _refund(db, o, actor_id, event, note):
    move(db, o["id"], ("REFUNDING",), "REFUNDED")

    db.execute(
        """UPDATE posts SET status='active'
           WHERE id=? AND status='reserved'""",
        (o["post_id"],),
    )

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
           WHERE seller_id=? AND status IN ('HELD','DELIVERED','DISPUTED','RELEASING','REFUNDING')""", (uid,)
    ).fetchone()["s"]
    held_buyer = db.execute(
        """SELECT COALESCE(SUM(amount_cents),0) s FROM orders
           WHERE buyer_id=? AND status IN ('HELD','DELIVERED','DISPUTED','RELEASING','REFUNDING')""", (uid,)
    ).fetchone()["s"]
    return jsonify({"ok": True, "available_cents": released, "pending_cents": pending,
                    "buyer_held_cents": held_buyer})
