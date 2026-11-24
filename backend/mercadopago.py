"""Pagos con Mercado Pago Checkout Pro (alternativa a PayPal, US-09).

En México acepta tarjeta de crédito y débito, saldo de Mercado Pago, OXXO y SPEI. El dinero entra a la
cuenta de Mercado Pago de la plataforma y queda **retenido** igual que con Stripe; cuando el comprador
confirma la recepción, la orden pasa a «por liquidar» y administración paga al vendedor y registra la
referencia (liquidación manual). Los reembolsos se hacen por la API, totales o parciales por artículo.

Principios:
- La fuente de verdad es la API de Mercado Pago: una notificación solo dispara una consulta
  (`sync_group`), nunca se confía en su contenido.
- Las notificaciones se validan con la firma `x-signature` (HMAC-SHA256 con la clave secreta).
- Idempotencia: claves `X-Idempotency-Key` estables por grupo/orden.
- Varias órdenes del mismo carrito comparten un `checkout_group` y una sola preferencia.

Variables: MERCADOPAGO_ACCESS_TOKEN, MERCADOPAGO_WEBHOOK_SECRET, MERCADOPAGO_TEST (1 = cuentas de prueba).
"""
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, redirect, request

import config
from db import get_db, now, rows, tx
from security import notify

log = logging.getLogger("ecogallo.payments")
bp = Blueprint("mercadopago", __name__, url_prefix="/api/mercadopago")

API = "https://api.mercadopago.com"
PREFERENCE_HOURS = 24          # la preferencia (y la reserva sin pago iniciado) vence en 24 h
PENDING_STATES = ("pending", "in_process", "authorized")


class MPError(RuntimeError):
    pass


def _api(method: str, path: str, body: dict | None = None, idempotency: str | None = None) -> dict:
    """Llamada HTTP a la API. Separada para poder simularla en pruebas."""
    if not config.MP_ACCESS_TOKEN:
        raise MPError("Falta MERCADOPAGO_ACCESS_TOKEN.")
    headers = {"Authorization": f"Bearer {config.MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    if idempotency:
        headers["X-Idempotency-Key"] = idempotency
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310 - URL fija https de Mercado Pago
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise MPError(f"Mercado Pago respondió {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise MPError(f"Sin respuesta confiable de Mercado Pago: {exc}") from exc


def _cents(amount) -> int:
    return int(round(float(amount) * 100))


def _base_url() -> str:
    return config.PUBLIC_URL or "http://localhost:8080"


# ------------------------------------------------------------------ preferencia (Checkout Pro)
def create_preference(group: str, orders: list[dict], buyer_email: str) -> dict:
    expires = datetime.now(timezone.utc) + timedelta(hours=PREFERENCE_HOURS)
    first = orders[0]["id"]
    body = {
        "items": [{"id": f"orden-{o['id']}", "title": o["post_title"][:120], "quantity": 1,
                   "currency_id": "MXN", "unit_price": o["amount_cents"] / 100} for o in orders],
        "payer": {"email": buyer_email},
        "external_reference": group,
        "statement_descriptor": "ECOGALLO UAA",
        "back_urls": {k: f"{_base_url()}/api/mercadopago/return/{first}" for k in ("success", "failure", "pending")},
        "expires": True,
        "expiration_date_to": expires.isoformat(timespec="milliseconds"),
        "metadata": {"ecogallo_group": group},
    }
    if config.PUBLIC_URL.startswith("https://"):
        body["auto_return"] = "approved"
        body["notification_url"] = f"{config.PUBLIC_URL}/api/mercadopago/webhook"
    pref = _api("POST", "/checkout/preferences", body, idempotency=f"ecogallo-pref-{group}")
    url = pref.get("sandbox_init_point") if config.MP_TEST and pref.get("sandbox_init_point") else pref.get("init_point")
    if not pref.get("id") or not url:
        raise MPError("Mercado Pago no devolvió el enlace de pago.")
    return {"preference_id": pref["id"], "checkout_url": url}


def search_payments(group: str) -> list[dict]:
    q = urllib.parse.urlencode({"external_reference": group, "sort": "date_created", "criteria": "desc", "limit": 50})
    return _api("GET", f"/v1/payments/search?{q}").get("results", [])


def get_payment(payment_id: str) -> dict:
    return _api("GET", f"/v1/payments/{urllib.parse.quote(str(payment_id))}")


def refund(order_id: int, payment_id: str, amount_cents: int) -> dict:
    """Reembolso (parcial si el pago cubría varias órdenes). Devuelve {'id', 'status'} al estilo Stripe."""
    if not payment_id:
        raise MPError("La orden no tiene un pago de Mercado Pago asociado.")
    if amount_cents <= 0:
        raise ValueError("El importe del reembolso no es válido.")
    r = _api("POST", f"/v1/payments/{urllib.parse.quote(str(payment_id))}/refunds",
             {"amount": amount_cents / 100}, idempotency=f"ecogallo-refund-{order_id}")
    status = {"approved": "succeeded", "rejected": "failed", "cancelled": "canceled"}.get(r.get("status"), "pending")
    return {"id": str(r.get("id", "")), "status": status}


# ------------------------------------------------------------------ conciliación
def _notify_admins(db, oid, message):
    for u in db.execute("SELECT id FROM users WHERE role='admin' AND suspended=0"):
        notify(db, u["id"], message, f"#/order/{oid}")


def _event(db, oid, event, note):
    db.execute("INSERT INTO order_events(order_id,event,note,created_at) VALUES(?,?,?,?)", (oid, event, note, now()))


def sync_group(group: str) -> str:
    """Aplica el estado real de Mercado Pago a las órdenes del grupo. Devuelve un resumen."""
    payments = search_payments(group)
    db = get_db()
    with tx(db):
        orders = rows(db.execute(
            "SELECT o.*, p.title AS post_title FROM orders o JOIN posts p ON p.id=o.post_id "
            "WHERE o.checkout_group=? AND o.payment_provider='mercadopago' ORDER BY o.id", (group,)))
        if not orders:
            return "sin-ordenes"
        total = sum(o["amount_cents"] for o in orders)
        approved = [p for p in payments if p.get("status") == "approved"]
        linked = {o["provider_payment_id"] for o in orders if o["provider_payment_id"]}
        # 1) Pago aprobado: las órdenes pendientes quedan retenidas.
        if approved:
            p = approved[0]
            ok_amount = _cents(p.get("transaction_amount", 0)) == total and p.get("currency_id") == "MXN"
            for o in orders:
                if o["status"] == "PENDING_PAYMENT":
                    if ok_amount:
                        db.execute("UPDATE orders SET status='HELD', provider_payment_id=?, updated_at=? WHERE id=?",
                                   (str(p["id"]), now(), o["id"]))
                        _event(db, o["id"], "paid_held", "Mercado Pago confirmó el pago. Pendiente de entrega.")
                        notify(db, o["seller_id"], f"Se pagó «{o['post_title']}». Coordina la entrega.",
                               f"#/order/{o['id']}")
                    else:
                        db.execute("UPDATE orders SET status='PAYMENT_REVIEW', provider_payment_id=?, updated_at=? "
                                   "WHERE id=?", (str(p["id"]), now(), o["id"]))
                        _notify_admins(db, o["id"], "El importe pagado en Mercado Pago no coincide. Revisa el pago.")
                elif o["status"] == "CANCELLED":
                    db.execute("UPDATE orders SET status='PAYMENT_REVIEW', provider_payment_id=?, updated_at=? "
                               "WHERE id=?", (str(p["id"]), now(), o["id"]))
                    _notify_admins(db, o["id"], "Llegó un pago de Mercado Pago después de cancelar. Reembólsalo.")
            return "aprobado" if ok_amount else "revision"
        # 2) Un pago ya asociado cambió después (contracargo, mediación o reembolso externo).
        for p in payments:
            if str(p.get("id")) not in linked:
                continue
            st = p.get("status")
            if st in ("charged_back", "in_mediation", "refunded"):
                for o in orders:
                    if o["status"] in ("HELD", "DELIVERED", "DISPUTED", "RELEASING", "RELEASED"):
                        db.execute("UPDATE orders SET status='PAYMENT_REVIEW', updated_at=? WHERE id=?", (now(), o["id"]))
                        _notify_admins(db, o["id"], f"Mercado Pago reporta el pago como «{st}». Requiere conciliación.")
                return "revision"
        # 3) Pago en proceso (por ejemplo, ficha OXXO generada): se conserva la reserva.
        if any(p.get("status") in PENDING_STATES for p in payments):
            return "pendiente"
        # 4) Sin pago válido y la preferencia ya venció: se libera la reserva sin cobrar.
        if all(o["status"] != "PENDING_PAYMENT" for o in orders):
            return "sin-cambios"
        if now() - min(o["created_at"] for o in orders) > PREFERENCE_HOURS * 3600 + 300:
            for o in orders:
                if o["status"] == "PENDING_PAYMENT":
                    db.execute("UPDATE orders SET status='CANCELLED', updated_at=? WHERE id=?", (now(), o["id"]))
                    db.execute("UPDATE posts SET status='active' WHERE id=? AND status='reserved'", (o["post_id"],))
                    _event(db, o["id"], "payment_cancelled", "El enlace de pago venció sin un pago aprobado.")
            return "vencido"
        return "esperando"


def cancel_group(group: str, actor_id: int) -> str:
    """Cancela una compra sin pagar. Si ya hay un pago aprobado o en proceso, no se cancela."""
    payments = search_payments(group)
    if any(p.get("status") == "approved" for p in payments):
        sync_group(group)
        return "pagado"
    if any(p.get("status") in PENDING_STATES for p in payments):
        return "en-proceso"
    db = get_db()
    with tx(db):
        for o in rows(db.execute("SELECT * FROM orders WHERE checkout_group=? AND status='PENDING_PAYMENT'", (group,))):
            db.execute("UPDATE orders SET status='CANCELLED', updated_at=? WHERE id=?", (now(), o["id"]))
            db.execute("UPDATE posts SET status='active' WHERE id=? AND status='reserved'", (o["post_id"],))
            db.execute("INSERT INTO order_events(order_id,actor_id,event,note,created_at) VALUES(?,?,?,?,?)",
                       (o["id"], actor_id, "cancelled", "Compra cancelada antes de pagar.", now()))
    return "cancelado"


# ------------------------------------------------------------------ notificaciones (webhook)
def valid_signature(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """Firma de Mercado Pago: v1 = HMAC-SHA256(secret, 'id:<data.id>;request-id:<x-request-id>;ts:<ts>;')."""
    if not config.MP_WEBHOOK_SECRET or not x_signature:
        return False
    parts = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = parts.get("ts", ""), parts.get("v1", "")
    if not ts or not v1:
        return False
    data_id = data_id.lower() if data_id.isalnum() else data_id
    manifest = ""
    if data_id:
        manifest += f"id:{data_id};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    expected = hmac.new(config.MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


@bp.post("/webhook")
def webhook():
    if config.PAYMENT_PROVIDER != "mercadopago":
        return jsonify({"ok": False}), 404
    data_id = request.args.get("data.id") or str(((request.get_json(silent=True) or {}).get("data") or {}).get("id", ""))
    if not valid_signature(request.headers.get("x-signature", ""), request.headers.get("x-request-id", ""), data_id):
        return jsonify({"ok": False, "message": "Firma inválida."}), 401
    topic = request.args.get("type") or request.args.get("topic") or (request.get_json(silent=True) or {}).get("type")
    if topic != "payment" or not data_id:
        return jsonify({"ok": True, "ignored": True})
    try:
        ref = str(get_payment(data_id).get("external_reference") or "")
        if ref.startswith("eg-"):
            sync_group(ref)
    except MPError:
        log.exception("No se pudo procesar la notificación de Mercado Pago %s", data_id)
        return jsonify({"ok": False}), 503   # Mercado Pago reintenta
    return jsonify({"ok": True})


@bp.get("/return/<int:oid>")
def back(oid):
    """Regreso desde Checkout Pro: se consulta el estado real y se vuelve a la orden."""
    row = get_db().execute("SELECT checkout_group FROM orders WHERE id=? AND payment_provider='mercadopago'",
                           (oid,)).fetchone()
    if row and row["checkout_group"]:
        try:
            sync_group(row["checkout_group"])
        except MPError:
            log.exception("Sincronización al regresar de Mercado Pago (orden %s)", oid)
    return redirect(f"/#/order/{oid}", 302)
