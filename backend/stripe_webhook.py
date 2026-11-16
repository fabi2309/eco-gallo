"""Webhook de Stripe para confirmar pagos y cancelar sesiones expiradas."""

import stripe

from flask import Blueprint, jsonify, request

import config
from db import get_db, now, tx
from security import notify


bp = Blueprint("stripe_webhook", __name__, url_prefix="/api/stripe")


def _stripe_client():
    if config.PAYMENT_PROVIDER != "stripe":
        raise RuntimeError("Stripe no está habilitado.")

    if not config.STRIPE_SECRET_KEY or not config.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Falta configurar Stripe o su secreto de webhook.")

    stripe.api_key = config.STRIPE_SECRET_KEY
    return stripe


@bp.post("/webhook")
def stripe_webhook():
    try:
        stripe_api = _stripe_client()
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 503

    signature = request.headers.get("Stripe-Signature", "")
    payload = request.get_data()

    try:
        event = stripe_api.Webhook.construct_event(
            payload,
            signature,
            config.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify({
            "ok": False,
            "message": "Firma de Stripe inválida.",
        }), 400

    event_type = event["type"]

    if event_type not in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.expired",
    ):
        return jsonify({"ok": True, "received": True})

    session_obj = event["data"]["object"]
    session = session_obj.to_dict()

    session_id = session.get("id")
    metadata = session.get("metadata") or {}

    try:
        order_id = int(metadata.get("order_id"))
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "message": "El evento no contiene un ID de orden válido.",
        }), 400

    payment_intent_id = session.get("payment_intent")
    charge_id = None

    paid_event = event_type in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    )

    if paid_event and session.get("payment_status") == "paid":
        if not payment_intent_id:
            return jsonify({
                "ok": False,
                "message": "La sesión no contiene un PaymentIntent.",
            }), 400

        try:
            payment_intent_obj = stripe_api.PaymentIntent.retrieve(
                payment_intent_id,
                expand=["latest_charge"],
            )

            # Convertimos todo el PaymentIntent a diccionario de forma segura
            pi_dict = payment_intent_obj.to_dict() if hasattr(payment_intent_obj, "to_dict") else dict(payment_intent_obj)

            raw_charge = pi_dict.get("latest_charge")

            # Extracción a prueba de diccionarios anidados
            charge_id = None
            if isinstance(raw_charge, dict):
                charge_id = raw_charge.get("id")
            elif hasattr(raw_charge, "id"):
                charge_id = raw_charge.id
            elif isinstance(raw_charge, str):
                charge_id = raw_charge

            # Si por alguna razón sigue siendo un diccionario, buscamos 'id' dentro o lo anulamos
            if isinstance(charge_id, dict):
                charge_id = charge_id.get("id")

            if not isinstance(charge_id, str):
                charge_id = None

        except stripe.StripeError:
            return jsonify({
                "ok": False,
                "message": "No se pudo consultar el pago en Stripe.",
            }), 502

    db = get_db()

    with tx(db):
        inserted = db.execute(
            """INSERT OR IGNORE INTO stripe_webhook_events
               (event_id, event_type, processed_at)
               VALUES(?,?,?)""",
            (str(event["id"]), str(event_type), str(now())),
        )

        if inserted.rowcount == 0:
            return jsonify({"ok": True, "duplicate": True})

        order_row = db.execute(
            """SELECT o.*, p.title AS post_title,
                      b.name AS buyer_name
               FROM orders o
               JOIN posts p ON p.id=o.post_id
               JOIN users b ON b.id=o.buyer_id
               WHERE o.id=?""",
            (order_id,),
        ).fetchone()

        if not order_row:
            return jsonify({"ok": True, "ignored": True})

        order = dict(order_row)

        if order["stripe_session_id"] != session_id:
            return jsonify({"ok": True, "ignored": True})

        if event_type == "checkout.session.expired":
            if order["status"] == "PENDING_PAYMENT":
                db.execute(
                    """UPDATE orders
                       SET status='CANCELLED', updated_at=?
                       WHERE id=? AND status='PENDING_PAYMENT'""",
                    (now(), order_id),
                )

                db.execute(
                    """UPDATE posts SET status='active'
                       WHERE id=? AND status='reserved'""",
                    (order["post_id"],),
                )

                db.execute(
                    """INSERT INTO order_events
                       (order_id, actor_id, event, note, created_at)
                       VALUES(?,NULL,?,?,?)""",
                    (
                        order_id,
                        "payment_expired",
                        "La sesión de pago de Stripe expiró.",
                        now(),
                    ),
                )

        elif paid_event and session.get("payment_status") == "paid":
            if (
                session.get("amount_total") != order["amount_cents"]
                or session.get("currency", "").lower() != "mxn"
            ):
                return jsonify({
                    "ok": False,
                    "message": "El importe o la moneda no coinciden con la orden.",
                }), 400

            if order["status"] == "PENDING_PAYMENT":
                # --- BLINDAJE EXTREMO PARA EL CHARGE_ID ---
                final_charge_id = None
                if isinstance(charge_id, str):
                    final_charge_id = charge_id
                elif isinstance(charge_id, dict):
                    final_charge_id = charge_id.get("id")
                elif hasattr(charge_id, "id"):
                    final_charge_id = charge_id.id

                if not isinstance(final_charge_id, str):
                    final_charge_id = None

                safe_pi_id = str(payment_intent_id) if payment_intent_id else None

                db.execute(
                    """UPDATE orders
                       SET status='HELD',
                           stripe_payment_intent_id=?,
                           stripe_charge_id=?,
                           updated_at=?
                       WHERE id=? AND status='PENDING_PAYMENT'""",
                    (
                        safe_pi_id,
                        final_charge_id,
                        now(),
                        order_id,
                    ),
                )

                db.execute(
                    """INSERT INTO order_events
                       (order_id, actor_id, event, note, created_at)
                       VALUES(?,NULL,?,?,?)""",
                    (
                        order_id,
                        "paid_held",
                        "Stripe confirmó el pago. Fondos retenidos hasta la confirmación de recepción.",
                        now(),
                    ),
                )

                notify(
                    db,
                    order["seller_id"],
                    f"{order['buyer_name']} pagó «{order['post_title']}». "
                    "El pago está retenido: entrega el artículo y espera la confirmación.",
                    f"#/order/{order_id}",
                )

    return jsonify({"ok": True, "received": True})
