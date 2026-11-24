"""Recover interrupted Stripe requests without opening an opposite operation."""
import logging
import os
import threading

from flask import Blueprint, g, jsonify

from db import get_db, now, tx
from security import api_error, login_required

bp = Blueprint('reconciliation', __name__, url_prefix='/api')
_started = False
log = logging.getLogger('ecogallo.payments')


def reconcile(oid):
    from orders import SELECT_ORDER, ensure_checkout, _act, move
    from payments import get_provider
    from stripe_webhook import apply_event
    db = get_db()
    row = db.execute(f'{SELECT_ORDER} WHERE o.id=?', (oid,)).fetchone()
    if not row:
        return
    o = dict(row)
    if o['payment_provider'] == 'mercadopago':
        import mercadopago
        if o['status'] == 'PENDING_PAYMENT' or (o['status'] in ('HELD', 'DELIVERED', 'DISPUTED') and o['checkout_group']):
            mercadopago.sync_group(o['checkout_group'])
            return
        if o['status'] not in ('RELEASING', 'REFUNDING'):
            return
    elif o['payment_provider'] != 'stripe':
        return
    if o['status'] in ('RELEASING', 'REFUNDING'):
        return _act(oid, 'confirm' if o['status'] == 'RELEASING' and g.user['id'] == o['buyer_id'] else
                    'resolve_release' if o['status'] == 'RELEASING' else
                    'refund' if g.user['id'] == o['seller_id'] else 'resolve_refund')
    provider = get_provider('stripe')
    if o['status'] == 'PENDING_PAYMENT':
        sid = o['stripe_session_id']
        if not sid:
            # Search before recreating a Checkout whose response may have been lost.
            sessions = provider.stripe.checkout.Session.list(created={'gte': o['created_at'] - 5}, limit=100)
            for session in sessions.auto_paging_iter():
                if (session.to_dict() if hasattr(session, 'to_dict') else session)['metadata'].get('order_id') == str(oid):
                    sid = session.id
                    break
            if not sid and now() - o['created_at'] > 23 * 3600:
                with tx(db):
                    current = db.execute('SELECT status FROM orders WHERE id=?', (oid,)).fetchone()
                    if current[0] == 'PENDING_PAYMENT':
                        move(db, oid, ('PENDING_PAYMENT',), 'CANCELLED')
                        db.execute("UPDATE posts SET status='active' WHERE id=? AND status='reserved'", (o['post_id'],))
                return
            if not sid:
                sid = ensure_checkout(o)['session_id']
        session = provider.stripe.checkout.Session.retrieve(sid)
        if session.payment_status == 'paid':
            kind = 'checkout.session.completed'
        elif session.status == 'expired':
            kind = 'checkout.session.expired'
        else:
            return
        event = {'id': f'reconcile_{sid}_{session.status}_{session.payment_status}', 'type': kind,
                 'data': {'object': session}}
        result, code = apply_event(event, provider.stripe)
        if code >= 400:
            raise RuntimeError(result.get('message', 'Conciliación pendiente.'))
    elif o['status'] in ('RELEASING', 'REFUNDING'):
        return _act(oid, 'confirm' if o['status'] == 'RELEASING' and g.user['id'] == o['buyer_id'] else
                    'resolve_release' if o['status'] == 'RELEASING' else
                    'refund' if g.user['id'] == o['seller_id'] else 'resolve_refund')


@bp.post('/orders/<int:oid>/sync')
@login_required
def sync_order(oid):
    row = get_db().execute('SELECT buyer_id,seller_id FROM orders WHERE id=?', (oid,)).fetchone()
    if not row or (g.user['role'] != 'admin' and g.user['id'] not in tuple(row)):
        return api_error('Orden no encontrada.', 404)
    try:
        result = reconcile(oid)
        return result if result is not None else jsonify({'ok': True})
    except Exception:
        log.exception('Conciliación pendiente en orden %s', oid)
        return api_error('No se pudo confirmar el resultado. La operación permanece protegida para reintentar.', 502)


def start_scheduler(app):
    global _started
    if _started or os.environ.get('ECOGALLO_RECONCILE_ENABLED', '1') != '1':
        return
    _started = True

    def worker():
        import time
        from runtime import enter_request, leave_request
        while True:
            time.sleep(60)
            with app.app_context():
                pending = list(get_db().execute("""SELECT id,operation_actor_id,buyer_id FROM orders
                    WHERE payment_provider IN ('stripe','mercadopago') AND status IN ('PENDING_PAYMENT','RELEASING','REFUNDING')
                    AND updated_at<? LIMIT 50""", (now() - 35,)))
            for row in pending:
                with app.test_request_context(json={}, method='POST'):
                    if enter_request() is not None:
                        continue
                    try:
                        user = get_db().execute('SELECT * FROM users WHERE id=? AND suspended=0',
                                                (row['operation_actor_id'] or row['buyer_id'],)).fetchone()
                        if user:
                            g.user = dict(user)
                            reconcile(row['id'])
                    except Exception:
                        log.exception('Se reintentará conciliación de orden %s', row['id'])
                    finally:
                        leave_request()

    threading.Thread(target=worker, daemon=True, name='payment-reconciliation').start()
