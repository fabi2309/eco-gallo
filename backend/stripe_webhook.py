"""Signed Stripe events, applied atomically with their deduplication record."""
import stripe
from flask import Blueprint, jsonify, request

import config
from db import get_db, now, tx
from security import notify

bp = Blueprint('stripe_webhook', __name__, url_prefix='/api/stripe')


def _stripe_client():
    if config.PAYMENT_PROVIDER != 'stripe' or not config.STRIPE_SECRET_KEY or not config.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError('El webhook de Stripe no está configurado.')
    stripe.api_key = config.STRIPE_SECRET_KEY
    return stripe


def apply_event(event, api):
    kind = event['type']
    obj = event['data']['object']
    obj = obj.to_dict() if hasattr(obj, 'to_dict') else dict(obj)
    db = get_db()
    if db.execute('SELECT 1 FROM stripe_webhook_events WHERE event_id=?', (event['id'],)).fetchone():
        return {'ok': True, 'duplicate': True}, 200
    if kind.startswith('checkout.session.'):
        if kind not in ('checkout.session.completed', 'checkout.session.async_payment_succeeded',
                        'checkout.session.async_payment_failed', 'checkout.session.expired'):
            return {'ok': True, 'ignored': True}, 200
        try:
            oid = int((obj.get('metadata') or {}).get('order_id'))
        except (TypeError, ValueError):
            return {'ok': False, 'message': 'Orden inválida.'}, 400
        charge = None
        paid = obj.get('payment_status') == 'paid' and kind in ('checkout.session.completed', 'checkout.session.async_payment_succeeded')
        if paid:
            pi = api.PaymentIntent.retrieve(obj['payment_intent'], expand=['latest_charge'])
            pi = pi.to_dict() if hasattr(pi, 'to_dict') else pi
            charge = pi.get('latest_charge')
            if isinstance(charge, dict):
                charge = charge.get('id')
            if not isinstance(charge, str):
                return {'ok': False, 'message': 'El cargo aún no está disponible.'}, 503
        with tx(db):
            if db.execute('SELECT 1 FROM stripe_webhook_events WHERE event_id=?', (event['id'],)).fetchone():
                return {'ok': True, 'duplicate': True}, 200
            row = db.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
            if not row or row['payment_provider'] != 'stripe':
                return {'ok': False, 'message': 'La orden aún no está disponible.'}, 409
            if row['stripe_session_id'] and row['stripe_session_id'] != obj['id']:
                return {'ok': False, 'message': 'La sesión no coincide.'}, 409
            if paid and (obj.get('amount_total') != row['amount_cents'] or obj.get('currency') != 'mxn'):
                return {'ok': False, 'message': 'Importe o moneda incorrectos.'}, 400
            # A signed event with matching metadata can bind a session before the Checkout response is saved.
            db.execute("UPDATE orders SET stripe_session_id=? WHERE id=? AND stripe_session_id=''", (obj['id'], oid))
            if paid and row['status'] == 'PENDING_PAYMENT':
                db.execute("""UPDATE orders SET status='HELD', stripe_payment_intent_id=?, stripe_charge_id=?, updated_at=? WHERE id=?""",
                           (obj['payment_intent'], charge, now(), oid))
                db.execute("INSERT INTO order_events(order_id,event,note,created_at) VALUES(?,?,?,?)",
                           (oid, 'paid_held', 'Stripe confirmó el pago. Pendiente de entrega.', now()))
                notify(db, row['seller_id'], 'Stripe confirmó el pago. Coordina la entrega.', f'#/order/{oid}')
            elif paid and row['status'] == 'CANCELLED':
                db.execute("UPDATE orders SET status='PAYMENT_REVIEW', stripe_payment_intent_id=?, stripe_charge_id=? WHERE id=?",
                           (obj['payment_intent'], charge, oid))
                notify_admins(db, oid, 'Se recibió un pago tras una cancelación; requiere conciliación.')
            elif kind in ('checkout.session.expired', 'checkout.session.async_payment_failed') and row['status'] == 'PENDING_PAYMENT':
                db.execute("UPDATE orders SET status='CANCELLED', updated_at=? WHERE id=?", (now(), oid))
                db.execute("UPDATE posts SET status='active' WHERE id=? AND status='reserved'", (row['post_id'],))
                db.execute("INSERT INTO order_events(order_id,event,note,created_at) VALUES(?,?,?,?)",
                           (oid, 'payment_cancelled', 'Checkout expiró o el pago falló.', now()))
            record_event(db, event)
        return {'ok': True}, 200
    if kind in ('refund.created', 'refund.updated', 'refund.failed', 'charge.dispute.created', 'charge.refunded'):
        pi = obj.get('payment_intent')
        with tx(db):
            if db.execute('SELECT 1 FROM stripe_webhook_events WHERE event_id=?', (event['id'],)).fetchone():
                return {'ok': True, 'duplicate': True}, 200
            row = db.execute("SELECT * FROM orders WHERE stripe_payment_intent_id=? AND payment_provider='stripe'", (pi,)).fetchone()
            if not row:
                return {'ok': False, 'message': 'Pago aún no asociado a una orden.'}, 409
            o = dict(row)
            from orders import move, _refund
            if kind == 'charge.dispute.created':
                db.execute("UPDATE orders SET status='PAYMENT_REVIEW', updated_at=? WHERE id=?", (now(), o['id']))
                notify_admins(db, o['id'], 'Stripe notificó un contracargo. Revisa el Dashboard de Stripe.')
            elif kind.startswith('refund.'):
                if obj.get('amount') != o['amount_cents']:
                    notify_admins(db, o['id'], 'Reembolso parcial externo; requiere revisión.')
                    db.execute("UPDATE orders SET status='PAYMENT_REVIEW' WHERE id=?", (o['id'],))
                elif obj.get('status') == 'succeeded' and o['status'] == 'REFUNDING':
                    db.execute('UPDATE orders SET stripe_refund_id=? WHERE id=?', (obj['id'], o['id']))
                    _refund(db, o, o.get('operation_actor_id'), 'refund_confirmed', 'Stripe confirmó el reembolso.')
                    notify(db, o['buyer_id'], 'Stripe confirmó tu reembolso.', f"#/order/{o['id']}")
                elif obj.get('status') in ('failed', 'canceled'):
                    db.execute("UPDATE orders SET status='PAYMENT_REVIEW', updated_at=? WHERE id=?", (now(), o['id']))
                    notify_admins(db, o['id'], 'El reembolso falló o fue cancelado. El pago sigue en revisión.')
                elif o['status'] not in ('REFUNDING', 'REFUNDED'):
                    db.execute("UPDATE orders SET status='PAYMENT_REVIEW' WHERE id=?", (o['id'],))
                    notify_admins(db, o['id'], 'Reembolso iniciado fuera de ECO-GALLO; concilia el pago.')
            elif kind == 'charge.refunded' and o['status'] != 'REFUNDED':
                if obj.get('refunded') and obj.get('amount_refunded') == o['amount_cents'] and o['status'] in ('HELD', 'DELIVERED', 'DISPUTED', 'REFUNDING'):
                    if o['status'] != 'REFUNDING':
                        move(db, o['id'], (o['status'],), 'REFUNDING')
                    _refund(db, o, None, 'external_refund', 'Stripe confirmó un reembolso completo.')
                else:
                    db.execute("UPDATE orders SET status='PAYMENT_REVIEW' WHERE id=?", (o['id'],))
                    notify_admins(db, o['id'], 'Reembolso externo después de liberar fondos; concilia la transferencia.')
            record_event(db, event)
        return {'ok': True}, 200
    return {'ok': True, 'ignored': True}, 200


def notify_admins(db, oid, message):
    for user in db.execute("SELECT id FROM users WHERE role='admin' AND suspended=0"):
        notify(db, user['id'], message, f'#/order/{oid}')


def record_event(db, event):
    db.execute('INSERT INTO stripe_webhook_events(event_id,event_type,processed_at) VALUES(?,?,?)',
               (event['id'], event['type'], now()))


@bp.post('/webhook')
def stripe_webhook():
    try:
        api = _stripe_client()
    except RuntimeError as exc:
        return jsonify({'ok': False, 'message': str(exc)}), 503
    try:
        event = api.Webhook.construct_event(request.get_data(), request.headers.get('Stripe-Signature', ''), config.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        return jsonify({'ok': False, 'message': 'Firma de Stripe inválida.'}), 400
    try:
        payload, status = apply_event(event, api)
        return jsonify(payload), status
    except (stripe.StripeError, KeyError, TypeError, ValueError):
        return jsonify({'ok': False, 'message': 'No se pudo verificar el evento. Stripe puede reintentarlo.'}), 503
