"""Pago retenido: el dinero queda en custodia hasta que el comprador confirma que recibió."""
from flask import Blueprint, g, jsonify, request

from db import get_db, now, rows, tx
from payments import get_provider, seller_ready
from pagination import pagination
from payment_states import OPEN_STATES
from security import api_error, clean_text, login_required, notify

bp = Blueprint("orders", __name__, url_prefix="/api")

LIVE = OPEN_STATES


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
       b.name AS buyer_name, b.email AS buyer_email, s.name AS seller_name,
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
        "payment_provider": o["payment_provider"],
        "simulated": o["payment_provider"] == "simulado",
        "checkout_url": o["checkout_url"] if o["buyer_id"] == user["id"] and o["status"] == "PENDING_PAYMENT" else None,
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
    try:
        provider = get_provider()
    except RuntimeError as exc:
        return api_error(str(exc), 503)
    is_stripe = provider.name == "stripe"
    if data.get('simulation_only') is True and provider.name != 'simulado':
        return api_error('Este cliente solo permite pedidos con pagos simulados.', 409)

    if is_stripe:
        seller = db.execute("SELECT u.stripe_account_id FROM users u JOIN posts p ON p.author_id=u.id WHERE p.id=? AND u.suspended=0", (pid,)).fetchone()
        try:
            if not seller or not seller_ready(seller[0]):
                return api_error("El vendedor debe completar su cuenta de pagos antes de aceptar compras.", 409)
        except Exception:
            return api_error("No pudimos comprobar la cuenta del vendedor. Intenta más tarde.", 503)
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
        db.execute("UPDATE orders SET payment_provider=? WHERE id=?", (provider.name, oid))

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

    row = dict(db.execute(f"{SELECT_ORDER} WHERE o.id=?", (oid,)).fetchone())
    return checkout_response(row, 201)


def ensure_checkout(o):
    """Stable idempotency key recovers a lost Checkout response on the same order."""
    provider = get_provider(o['payment_provider'])
    checkout = None
    if o.get('stripe_session_id'):
        session = provider.stripe.checkout.Session.retrieve(o['stripe_session_id'])
        if session.status != 'open':
            raise RuntimeError('Checkout cerrado. Actualiza el estado de la compra.')
        checkout = {'payment_ref': session.id, 'session_id': session.id, 'checkout_url': session.url}
    elif now() - o['created_at'] > 60:
        sessions = provider.stripe.checkout.Session.list(created={'gte': o['created_at'] - 5}, limit=100)
        for session in sessions.auto_paging_iter():
            if (session.to_dict() if hasattr(session, 'to_dict') else session)['metadata'].get('order_id') == str(o['id']):
                checkout = {'payment_ref': session.id, 'session_id': session.id, 'checkout_url': session.url or ''}
                break
        if checkout is None and now() - o['created_at'] > 23 * 3600:
            raise RuntimeError('Reserva antigua: requiere cancelar mediante conciliación.')
    if checkout is None:
        checkout = provider.start_checkout(o['id'], o['amount_cents'], o['buyer_email'])
    if not checkout.get('checkout_url') or not checkout.get('session_id'):
        raise RuntimeError('Checkout no disponible.')
    db = get_db()
    with tx(db):
        db.execute("""UPDATE orders SET payment_ref=?, stripe_session_id=?, checkout_url=?, updated_at=?
                      WHERE id=? AND status='PENDING_PAYMENT' AND (stripe_session_id='' OR stripe_session_id=?)""",
                   (checkout['payment_ref'], checkout['session_id'], checkout['checkout_url'], now(), o['id'], checkout['session_id']))
    return checkout


def checkout_response(o, code=200):
    try:
        checkout = ensure_checkout(o)
        return jsonify({'ok': True, 'id': o['id'], 'checkout_url': checkout['checkout_url']}), code
    except Exception:
        # Result is uncertain: keep the reservation and recover this exact order.
        return api_error('No se pudo abrir el pago. Puedes reintentarlo desde Compras y ventas.', 502, id=o['id'])


@bp.post('/orders/<int:oid>/checkout')
@login_required
def resume_checkout(oid):
    row = get_db().execute(f"{SELECT_ORDER} WHERE o.id=? AND o.buyer_id=?", (oid, g.user['id'])).fetchone()
    if not row or row['status'] != 'PENDING_PAYMENT':
        return api_error('No hay un pago pendiente para continuar.', 409)
    return checkout_response(dict(row))


@bp.post('/orders/<int:oid>/cancel')
@login_required
def cancel_checkout(oid):
    db = get_db()
    row = db.execute(f"{SELECT_ORDER} WHERE o.id=? AND o.buyer_id=?", (oid, g.user['id'])).fetchone()
    if not row or row['status'] != 'PENDING_PAYMENT':
        return api_error('La compra ya no se puede cancelar.', 409)
    try:
        o = dict(row)
        checkout = ensure_checkout(o)
        provider = get_provider(o['payment_provider'])
        session = provider.stripe.checkout.Session.retrieve(checkout['session_id'])
        if session.status == 'complete' or session.payment_status == 'paid':
            return api_error('El pago ya se procesó. Actualiza la orden.', 409)
        if session.status != 'expired':
            provider.stripe.checkout.Session.expire(session.id)
        with tx(db):
            current = db.execute('SELECT status FROM orders WHERE id=?', (oid,)).fetchone()
            if current['status'] == 'PENDING_PAYMENT':
                move(db, oid, ('PENDING_PAYMENT',), 'CANCELLED')
                db.execute("UPDATE posts SET status='active' WHERE id=? AND status='reserved'", (o['post_id'],))
                log_event(db, oid, g.user['id'], 'cancelled', 'Checkout cancelado sin cobrar.')
        return jsonify({'ok': True})
    except Exception:
        return api_error('No se pudo confirmar la cancelación. El artículo sigue reservado para evitar un doble cobro.', 502)


@bp.get("/orders")
@login_required
def list_orders():
    db = get_db()
    try:
        page, size, offset = pagination()
    except ValueError as exc:
        return api_error(str(exc))
    total = db.execute("SELECT COUNT(*) FROM orders WHERE buyer_id=? OR seller_id=?", (g.user['id'], g.user['id'])).fetchone()[0]
    rs = rows(db.execute(
        f"{SELECT_ORDER} WHERE o.buyer_id=? OR o.seller_id=? ORDER BY o.id DESC LIMIT ? OFFSET ?",
        (g.user["id"], g.user["id"], size, offset)))
    return jsonify({"ok": True, "orders": [serialize(db, o, g.user) for o in rs], 'page': page, 'pages': max(1, (total + size - 1) // size)})


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

        if data.get('simulation_only') is True and o['payment_provider'] != 'simulado':
            return api_error('Este cliente solo permite operaciones simuladas.', 409)

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
        # Keep the operation direction durable after any ambiguous external failure.

        if not retrying:
            allowed = (
                ("HELD", "DELIVERED")
                if action in ("confirm", "refund")
                else ("DISPUTED",)
            )

            try:
                move(db, oid, allowed, target_status, operation_actor_id=u["id"], payment_operation_at=now(),
                     operation_note=clean_text(data.get("note"), 300, required=False) or "")
            except Conflict as e:
                return api_error(str(e), 409)

    # La llamada externa se realiza fuera de la transacción SQLite.
    try:
        provider = get_provider(o["payment_provider"])
        if target_status == "RELEASING":
            transfer_id = provider.release(
                oid,
                o.get("stripe_charge_id") or "",
                o.get("seller_stripe_account_id") or "",
                o["amount_cents"],
            )
        else:
            refund_result = provider.refund(oid, o.get("stripe_payment_intent_id") or "", o["amount_cents"])
            with tx(db):
                db.execute("UPDATE orders SET stripe_refund_id=? WHERE id=? AND status='REFUNDING'",
                           (refund_result['id'], oid))
            if refund_result['status'] in ('failed', 'canceled'):
                with tx(db):
                    db.execute("UPDATE orders SET status='PAYMENT_REVIEW', updated_at=? WHERE id=? AND status='REFUNDING'", (now(), oid))
                    from stripe_webhook import notify_admins
                    notify_admins(db, oid, 'Stripe rechazó o canceló el reembolso. Requiere conciliación.')
                return api_error('Stripe no completó el reembolso. La administración debe revisar la operación.', 409)
            if refund_result['status'] != 'succeeded':
                return jsonify({'ok': True, 'pending': True, 'message': 'Stripe aún no confirma el reembolso.'}), 202

    except Exception:
        # A timeout is not a rejection: never unlock an opposite financial operation.
        with tx(db):
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

        if current and current['status'] == ('RELEASED' if target_status == 'RELEASING' else 'REFUNDED'):
            return jsonify({'ok': True})
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
