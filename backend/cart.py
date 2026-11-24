"""Carrito de compras (US-04): varios artículos, un solo pago.

Cada artículo sigue siendo una orden independiente con su propio pago retenido, entrega, confirmación y
posible disputa o reembolso (los vendedores pueden ser distintos). Lo que comparten es el `checkout_group`:
con Mercado Pago se paga todo en una sola preferencia; en la demostración todo queda retenido al instante.
Con Stripe cada artículo se paga por separado (su Checkout está ligado a una sola orden).
"""
from flask import Blueprint, g, jsonify, request

from db import get_db, now, rows, tx
from orders import OrderRefused, SELECT_ORDER, checkout_response, place_order
from payments import get_provider
from security import api_error, login_required

bp = Blueprint("cart", __name__, url_prefix="/api")
MAX_ITEMS = 10


def _items(db, uid):
    items = rows(db.execute(
        """SELECT c.post_id, c.added_at, p.title, p.price_cents, p.status, p.tipo, p.author_id, u.name AS seller_name,
                  (u.phone_verified_at>0 AND u.payout_last4!='') AS accepts_card,
                  (SELECT filename FROM post_images WHERE post_id=p.id ORDER BY position,id LIMIT 1) AS image
           FROM cart_items c JOIN posts p ON p.id=c.post_id JOIN users u ON u.id=p.author_id
           WHERE c.user_id=? ORDER BY c.added_at""", (uid,)))
    for i in items:
        i["available"] = i["status"] == "active" and i["tipo"] == "venta" and i["price_cents"] > 0
        i["image"] = f"/uploads/{i['image']}" if i["image"] else None
        i["accepts_card"] = bool(i["accepts_card"])
    return items


@bp.get("/cart")
@login_required
def get_cart():
    items = _items(get_db(), g.user["id"])
    total = sum(i["price_cents"] for i in items if i["available"])
    return jsonify({"ok": True, "items": items, "total_cents": total,
                    "count": sum(1 for i in items if i["available"])})


@bp.post("/cart")
@login_required
def add_to_cart():
    try:
        pid = int((request.get_json(silent=True) or {}).get("post_id"))
    except (TypeError, ValueError):
        return api_error("Publicación inválida.")
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
    if not post or post["status"] != "active" or post["tipo"] != "venta" or post["price_cents"] <= 0:
        return api_error("Solo puedes agregar artículos en venta y disponibles.", 409)
    if post["author_id"] == g.user["id"]:
        return api_error("No puedes comprar tu propia publicación.", 400)
    if db.execute("SELECT COUNT(*) FROM cart_items WHERE user_id=?", (g.user["id"],)).fetchone()[0] >= MAX_ITEMS:
        return api_error(f"Tu carrito admite hasta {MAX_ITEMS} artículos.", 409)
    db.execute("INSERT OR IGNORE INTO cart_items(user_id, post_id, added_at) VALUES(?,?,?)", (g.user["id"], pid, now()))
    return jsonify({"ok": True})


@bp.delete("/cart/<int:pid>")
@login_required
def remove_from_cart(pid):
    get_db().execute("DELETE FROM cart_items WHERE user_id=? AND post_id=?", (g.user["id"], pid))
    return jsonify({"ok": True})


@bp.post("/cart/checkout")
@login_required
def checkout():
    """Todo o nada: si un artículo ya no está disponible, no se reserva ninguno."""
    db = get_db()
    method = (request.get_json(silent=True) or {}).get("method") or "en_linea"
    if method not in ("en_linea", "efectivo"):
        return api_error("Forma de pago inválida.")
    items = [i for i in _items(db, g.user["id"]) if i["available"]]
    if not items:
        return api_error("Tu carrito no tiene artículos disponibles.", 409)
    if method == "efectivo":
        oids, current = [], None
        try:
            with tx(db):
                for current in items:
                    oids.append(place_order(db, current["post_id"], None, method="efectivo"))
        except OrderRefused as exc:
            return api_error(f"«{current['title']}»: {exc.message} No se apartó ningún artículo; actualiza tu carrito.",
                             exc.status)
        return jsonify({"ok": True, "ids": oids}), 201
    try:
        provider = get_provider()
    except RuntimeError as exc:
        return api_error(str(exc), 503)
    card = None
    if (request.get_json(silent=True) or {}).get('simulation_only') is True and provider.name != 'simulado':
        return api_error('El móvil solo ejecuta pagos simulados. Usa la web para proveedores externos.', 409)
    if provider.name == "simulado":
        from phone import parse_card
        card, err = parse_card((request.get_json(silent=True) or {}).get("card"))
        if err:
            return api_error(err)
    if provider.name == "stripe" and len(items) > 1:
        return api_error("Con el proveedor de pagos actual cada artículo se paga por separado. "
                         "Ábrelos desde el carrito y cómpralos uno por uno.", 409)
    if provider.name == "stripe":
        from payments import seller_ready
        seller = db.execute("SELECT stripe_account_id FROM users WHERE id=?", (items[0]["author_id"],)).fetchone()
        try:
            if not seller or not seller_ready(seller[0]):
                return api_error("El vendedor debe completar su cuenta de pagos antes de aceptar compras.", 409)
        except Exception:
            return api_error("No pudimos comprobar la cuenta del vendedor. Intenta más tarde.", 503)
    oids, current = [], None
    try:
        with tx(db):
            group = None
            for current in items:
                oid = place_order(db, current["post_id"], provider, group, card=card)
                if group is None:
                    group = db.execute("SELECT checkout_group FROM orders WHERE id=?", (oid,)).fetchone()[0]
                oids.append(oid)
    except OrderRefused as exc:
        return api_error(f"«{current['title']}»: {exc.message} No se reservó ningún artículo; actualiza tu carrito.",
                         exc.status)
    if provider.name not in ("stripe", "mercadopago"):
        return jsonify({"ok": True, "ids": oids}), 201
    row = dict(db.execute(f"{SELECT_ORDER} WHERE o.id=?", (oids[0],)).fetchone())
    resp, code = checkout_response(row, 201)
    data = resp.get_json()
    data["ids"] = oids
    return jsonify(data), code
