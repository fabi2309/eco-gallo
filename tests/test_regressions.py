"""Regression tests for authorization, financial failures and recoverability."""
import io
import json
import sqlite3
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

import config
import db
import security
from app import create_app
from payments import SimulatedProvider


@pytest.fixture
def app(tmp_path, monkeypatch):
    for name, value in {'DATA': tmp_path, 'UPLOADS': tmp_path / 'uploads',
                        'VERIF_DIR': tmp_path / 'private' / 'verificaciones',
                        'BACKUPS_DIR': tmp_path / 'backups', 'DB_PATH': tmp_path / 'ecogallo.sqlite'}.items():
        monkeypatch.setattr(config, name, value)
    for directory in (config.UPLOADS, config.VERIF_DIR, config.BACKUPS_DIR):
        directory.mkdir(parents=True)
    monkeypatch.setattr(db, 'DB_PATH', config.DB_PATH)
    monkeypatch.setattr(config, 'SECRET', b'test-secret-that-is-isolated-per-suite')
    monkeypatch.setattr(config, 'PRODUCTION', False)
    monkeypatch.setattr(config, 'PAYMENT_PROVIDER', 'simulado')
    monkeypatch.setattr(config, 'STRIPE_SECRET_KEY', '')
    monkeypatch.setattr(config, 'CONNECT_SIMULATED', False)
    monkeypatch.setattr(config, 'PUBLIC_URL', '')
    instance = create_app()
    instance.config['TESTING'] = True
    return instance


TEST_CARD = {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2035, "holder": "Usuario Prueba"}
_PHONE_SEQ = [4490000000]


class Actor:
    """Usuario de prueba. Por defecto con teléfono confirmado y cuenta para recibir (puede pagar y cobrar
    con tarjeta); `card=False` crea uno sin esos datos."""
    def __init__(self, app, email, role='user', card=True):
        self.app = app
        self.client = app.test_client()
        self.email = email
        with app.app_context():
            self.id = db.get_db().execute("""INSERT INTO users(email,name,carrera,role,created_at,password_hash)
                VALUES(?,?,?,?,?,?)""", (email, 'Usuario Prueba', 'Ingeniería en Sistemas Computacionales', role,
                                         db.now(), security.hash_password('CurrentPass123'))).lastrowid
            if card:
                _PHONE_SEQ[0] += 1
                db.get_db().execute(
                    """UPDATE users SET phone=?, phone_verified_at=?, payout_kind='clabe',
                    payout_last4='1234', payout_holder='Usuario Prueba' WHERE id=?""",
                    (f"+52{_PHONE_SEQ[0]}", db.now(), self.id))
            self.token = security.create_session(self.id)
        self.client.set_cookie(config.COOKIE_NAME, self.token)

    def call(self, method, path, **kwargs):
        headers = kwargs.pop('headers', {})
        # El pago de prueba pide la tarjeta (marca y últimos 4); se agrega si la prueba no la manda.
        body = kwargs.get('json')
        if method == 'POST' and path in ('/api/orders', '/api/cart/checkout') and isinstance(body, dict) \
                and body.get('method', 'en_linea') == 'en_linea' and 'card' not in body:
            kwargs['json'] = {**body, 'card': TEST_CARD}
        if method != 'GET':
            headers['X-CSRF-Token'] = self.client.get('/api/me').json['csrf_token']
        return self.client.open(path, method=method, headers=headers, **kwargs)


@pytest.fixture
def actors(app):
    return (Actor(app, 'seller@edu.uaa.mx'), Actor(app, 'buyer@edu.uaa.mx'), Actor(app, 'admin@edu.uaa.mx', 'admin'))


def post(app, seller, status='active'):
    with app.app_context():
        return db.get_db().execute("""INSERT INTO posts(author_id,title,description,category,tipo,price_cents,status,created_at)
            VALUES(?,?,?,?,?,?,?,?)""", (seller.id, 'Libro prueba', 'Descripción suficiente', 'Libros', 'venta', 10000, status, db.now())).lastrowid


def order(app, actors, status='HELD', provider='stripe', session='cs_test'):
    seller, buyer, _ = actors
    pid = post(app, seller, 'reserved')
    with app.app_context():
        oid = db.get_db().execute("""INSERT INTO orders(post_id,buyer_id,seller_id,amount_cents,status,payment_provider,
            stripe_session_id,stripe_payment_intent_id,stripe_charge_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (pid, buyer.id, seller.id, 10000, status, provider,
                                               session, 'pi_test', 'ch_test', db.now(), db.now())).lastrowid
    return oid


def row(app, oid):
    with app.app_context():
        return dict(db.get_db().execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone())


def test_csrf_origin_and_headers(app, actors):
    seller, _, _ = actors
    assert seller.client.put('/api/me', json={'name': 'Changed'}).status_code == 403
    assert seller.call('POST', '/auth/unknown', headers={'Origin': 'https://evil.example'}).status_code == 403
    response = seller.client.get('/api/me')
    assert response.headers['Cache-Control'] == 'no-store, private'
    assert response.headers['Content-Security-Policy']
    assert seller.call('PUT', '/api/me', json=[]).status_code == 400


@pytest.mark.parametrize('price', ['NaN', 'Infinity', '-Infinity', '1e100', '1e999999', '-1'])
def test_invalid_prices_are_400(app, actors, price):
    assert actors[0].call('GET', '/api/posts?min_price=' + price).status_code == 400


def test_pending_is_private_and_not_notified(app, actors):
    seller, buyer, admin = actors
    buyer.call('POST', '/api/wishlist', json={'term': 'Libro'})
    response = seller.call('POST', '/api/posts', data={'title': 'Libro pendiente', 'description': 'Descripción suficiente',
                                                       'category': 'Libros', 'tipo': 'venta', 'price': '100'})
    pid = response.json['id']
    assert buyer.call('GET', f'/api/posts/{pid}').status_code == 404
    assert not buyer.call('GET', '/api/notifications').json['notifications']
    assert buyer.call('GET', f'/api/threads/{pid}/{seller.id}').status_code == 404
    assert buyer.call('POST', f'/api/posts/{pid}/favorite').status_code == 404
    assert admin.call('POST', f'/api/admin/posts/{pid}/moderate', json={'action': 'approve'}).status_code == 200
    assert buyer.call('GET', '/api/notifications').json['notifications']


def test_password_recovery_grant_is_short_lived_and_consumed(app, actors):
    seller, _, _ = actors
    assert seller.call('PUT', '/api/auth/password', json={'new_password': 'NewPass123'}).status_code == 400
    with app.app_context():
        db.get_db().execute('INSERT INTO login_codes(email,code_hash,expires_at,created_at) VALUES(?,?,?,?)',
                            (seller.email, security.hash_code(seller.email, '123456'), db.now() + 60, db.now()))
    other = app.test_client()
    login = other.post('/api/auth/verify', json={'email': seller.email, 'code': '123456'})
    assert login.status_code == 200
    headers = {'X-CSRF-Token': login.json['csrf_token']}
    assert other.put('/api/auth/password', json={'new_password': 'NewPass123'}, headers=headers).status_code == 200
    assert seller.client.get('/api/me').json['user'] is None
    assert other.put('/api/auth/password', json={'new_password': 'OtherPass123'}, headers=headers).status_code == 400


def test_password_recovery_cannot_bypass_totp(app, actors):
    seller, _, _ = actors
    with app.app_context():
        db.get_db().execute('UPDATE users SET totp_enabled=1,totp_secret=? WHERE id=?',
                            (security.encrypt_totp_secret(security.new_totp_secret()), seller.id))
        db.get_db().execute('INSERT INTO login_codes(email,code_hash,expires_at,created_at) VALUES(?,?,?,?)',
                            (seller.email, security.hash_code(seller.email, '123456'), db.now() + 60, db.now()))
    c = app.test_client()
    response = c.post('/api/auth/verify', json={'email': seller.email, 'code': '123456'})
    assert response.json['needs_totp']
    assert c.get('/api/me').json['user'] is None
    assert c.put('/api/auth/password', json={'new_password': 'Attack123'}).status_code == 401


def test_monthly_metrics_and_pagination(app, actors):
    seller, _, admin = actors
    for _ in range(3):
        post(app, seller)
    page1 = seller.call('GET', '/api/posts?per_page=2').json
    page2 = seller.call('GET', '/api/posts?per_page=2&page=2').json
    assert page1['total'] == 3 and page1['pages'] == 2
    assert not {p['id'] for p in page1['posts']} & {p['id'] for p in page2['posts']}
    assert admin.call('GET', '/api/admin/metrics').json['users_monthly'][0]['month'] is not None


def test_image_batch_does_not_leave_orphans(app, actors):
    image = io.BytesIO()
    Image.new('RGB', (2, 2)).save(image, format='PNG')
    before = set(config.UPLOADS.iterdir())
    response = actors[0].call('POST', '/api/posts', data={'title': 'Libro prueba', 'description': 'Descripción suficiente',
                                                          'category': 'Libros', 'tipo': 'venta', 'price': '100',
                                                          'images': [(io.BytesIO(image.getvalue()), 'real.png'), (io.BytesIO(b'MZ not image'), 'fake.png')]})
    assert response.status_code == 400
    assert set(config.UPLOADS.iterdir()) == before


def test_ambiguous_transfer_never_enables_refund(app, actors, monkeypatch):
    import orders
    seller, buyer, _ = actors
    oid = order(app, actors)
    fake = Mock()
    fake.release.side_effect = TimeoutError('response lost')
    monkeypatch.setattr(orders, 'get_provider', lambda name=None: fake)
    assert buyer.call('POST', f'/api/orders/{oid}/confirm', json={}).status_code == 502
    assert row(app, oid)['status'] == 'RELEASING'
    assert seller.call('POST', f'/api/orders/{oid}/refund', json={}).status_code == 403
    fake.refund.assert_not_called()
    fake.release.side_effect = None
    fake.release.return_value = 'tr_test'
    assert buyer.call('POST', f'/api/orders/{oid}/confirm', json={}).status_code == 200
    with app.app_context():
        assert db.get_db().execute('SELECT COUNT(*) FROM wallet_entries WHERE order_id=?', (oid,)).fetchone()[0] == 1


def test_refund_stays_pending_until_confirmed(app, actors, monkeypatch):
    import orders
    seller, buyer, _ = actors
    oid = order(app, actors)
    fake = Mock()
    fake.refund.return_value = {'id': 're_pending', 'status': 'pending'}
    monkeypatch.setattr(orders, 'get_provider', lambda name=None: fake)
    assert seller.call('POST', f'/api/orders/{oid}/refund', json={}).status_code == 202
    assert row(app, oid)['status'] == 'REFUNDING'
    assert buyer.call('POST', f'/api/orders/{oid}/confirm', json={}).status_code == 403
    from stripe_webhook import apply_event
    with app.app_context():
        result, code = apply_event({'id': 'evt_refund', 'type': 'refund.updated', 'data': {'object': {
            'id': 're_pending', 'status': 'succeeded', 'amount': 10000, 'payment_intent': 'pi_test'}}}, fake)
        assert code == 200
    assert row(app, oid)['status'] == 'REFUNDED'


def test_early_webhook_binds_session_and_retry_is_safe(app, actors):
    from stripe_webhook import apply_event
    oid = order(app, actors, 'PENDING_PAYMENT', session='')
    event = {'id': 'evt_early', 'type': 'checkout.session.completed', 'data': {'object': {
        'id': 'cs_early', 'metadata': {'order_id': str(oid)}, 'payment_status': 'paid',
        'payment_intent': 'pi_test', 'currency': 'mxn', 'amount_total': 10000}}}
    api = SimpleNamespace(PaymentIntent=SimpleNamespace(retrieve=lambda *a, **k: {'latest_charge': 'ch_test'}))
    with app.app_context():
        assert apply_event(event, api)[1] == 200
        assert apply_event(event, api)[0]['duplicate']
    assert row(app, oid)['status'] == 'HELD'


@pytest.mark.parametrize('status', ['PENDING_PAYMENT', 'RELEASING', 'REFUNDING', 'PAYMENT_REVIEW'])
def test_admin_cannot_delete_open_payment_accounts(app, actors, status):
    seller, _, admin = actors
    order(app, actors, status)
    assert admin.call('DELETE', f'/api/admin/users/{seller.id}', json={'confirm_email': seller.email}).status_code == 409


def test_disabled_payments_and_unready_seller_do_not_reserve(app, actors, monkeypatch):
    import orders
    pid = post(app, actors[0])
    monkeypatch.setattr(config, 'PAYMENT_PROVIDER', 'disabled')
    assert actors[1].call('POST', '/api/orders', json={'post_id': pid}).status_code == 503
    monkeypatch.setattr(orders, 'get_provider', lambda name=None: SimpleNamespace(name='stripe'))
    monkeypatch.setattr(orders, 'seller_ready', lambda account: False)
    assert actors[1].call('POST', '/api/orders', json={'post_id': pid}).status_code == 409
    with app.app_context():
        assert db.get_db().execute('SELECT status FROM posts WHERE id=?', (pid,)).fetchone()[0] == 'active'


def test_demo_full_order_flow(app, actors, monkeypatch):
    import orders
    monkeypatch.setattr(orders, 'get_provider', lambda name=None: SimulatedProvider())
    seller, buyer, _ = actors
    pid = post(app, seller)
    created = buyer.call('POST', '/api/orders', json={'post_id': pid})
    assert created.status_code == 201
    oid = created.json['id']
    assert seller.call('POST', f'/api/orders/{oid}/deliver', json={}).status_code == 200
    assert buyer.call('POST', f'/api/orders/{oid}/confirm', json={}).status_code == 200
    assert buyer.call('GET', f'/api/orders/{oid}').json['order']['simulated']


def test_backups_encrypted_authenticated_and_restore_revokes_old_sessions(app, actors, monkeypatch):
    from backups import create_backup, restore_backup, _read_backup
    seller, _, admin = actors
    with app.app_context():
        backup = create_backup('regression')
        path = config.BACKUPS_DIR / backup['filename']
        with zipfile.ZipFile(path) as zf:
            assert 'payload.enc' in zf.namelist()
            assert 'database/ecogallo.sqlite' not in zf.namelist()
        original = config.SECRET
        monkeypatch.setattr(config, 'SECRET', b'a-different-key')
        with pytest.raises(ValueError, match='clave'):
            _read_backup(path)
        monkeypatch.setattr(config, 'SECRET', original)
        restore_backup(backup['filename'], admin.token, {'email': admin.email})
    assert seller.client.get('/api/me').json['user'] is None
    assert admin.client.get('/api/me').json['user']['id'] == admin.id


def test_restore_blocked_with_stripe_history(app, actors):
    from backups import create_backup, restore_backup
    order(app, actors, 'RELEASED')
    with app.app_context():
        backup = create_backup()
        with pytest.raises(ValueError, match='conciliación'):
            restore_backup(backup['filename'])


@pytest.mark.parametrize('name', ['uploads/../escape', 'uploads/..\\escape', 'uploads/C:/escape', '/absolute'])
def test_archive_rejects_cross_platform_traversal(app, name):
    from backups import _safe_entries
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as zf:
        zf.writestr(name, 'bad')
        with pytest.raises(ValueError):
            _safe_entries(zf)


def test_production_rejects_demo_and_debug_config(app, monkeypatch):
    monkeypatch.setattr(config, 'PRODUCTION', True)
    with pytest.raises(RuntimeError):
        config.validate_runtime()


def test_webhook_invalid_signature_does_not_modify_orders(app, actors, monkeypatch):
    monkeypatch.setattr(config, 'PAYMENT_PROVIDER', 'stripe')
    monkeypatch.setattr(config, 'STRIPE_SECRET_KEY', 'sk_test_fake')
    monkeypatch.setattr(config, 'STRIPE_WEBHOOK_SECRET', 'whsec_fake')
    response = app.test_client().post('/api/stripe/webhook', data=json.dumps({'id': 'fake'}),
                                      headers={'Stripe-Signature': 'invalid'})
    assert response.status_code == 400


def test_restore_rolls_back_database_and_media_on_failure(app, actors, monkeypatch):
    import backups
    seller, _, _ = actors
    with app.app_context():
        backup = backups.create_backup()
        db.get_db().execute('UPDATE users SET name=? WHERE id=?', ('Latest Name', seller.id))
        (config.UPLOADS / 'latest.txt').write_text('keep')
        real_init = db.init_db
        monkeypatch.setattr(db, 'init_db', Mock(side_effect=RuntimeError('injected migration failure')))
        with pytest.raises(RuntimeError):
            backups.restore_backup(backup['filename'])
        monkeypatch.setattr(db, 'init_db', real_init)
        assert db.get_db().execute('SELECT name FROM users WHERE id=?', (seller.id,)).fetchone()[0] == 'Latest Name'
        assert (config.UPLOADS / 'latest.txt').read_text() == 'keep'


def test_checkout_timeout_keeps_reservation_and_resume_reuses_order(app, actors, monkeypatch):
    import orders
    seller, buyer, _ = actors
    pid = post(app, seller)
    fake = Mock(name='provider')
    fake.name = 'stripe'
    fake.start_checkout.side_effect = TimeoutError('lost response')
    monkeypatch.setattr(orders, 'get_provider', lambda name=None: fake)
    monkeypatch.setattr(orders, 'seller_ready', lambda account: True)
    first = buyer.call('POST', '/api/orders', json={'post_id': pid})
    assert first.status_code == 502
    oid = first.json['id']
    assert row(app, oid)['status'] == 'PENDING_PAYMENT'
    fake.start_checkout.side_effect = None
    fake.start_checkout.return_value = {'payment_ref': 'cs_retry', 'session_id': 'cs_retry',
                                        'checkout_url': 'https://checkout.stripe.com/test'}
    assert buyer.call('POST', f'/api/orders/{oid}/checkout', json={}).status_code == 200
    assert row(app, oid)['stripe_session_id'] == 'cs_retry'
    assert buyer.call('POST', '/api/orders', json={'post_id': pid}).status_code == 409
    assert all(call.args[0] == oid for call in fake.start_checkout.call_args_list)


def test_cancel_verifies_stripe_expiration_before_releasing_article(app, actors, monkeypatch):
    import orders
    oid = order(app, actors, 'PENDING_PAYMENT')
    session = SimpleNamespace(id='cs_test', url='https://checkout.stripe.com/test', status='open', payment_status='unpaid')
    service = SimpleNamespace(retrieve=Mock(return_value=session), expire=Mock())
    provider = SimpleNamespace(stripe=SimpleNamespace(checkout=SimpleNamespace(Session=service)))
    monkeypatch.setattr(orders, 'get_provider', lambda name=None: provider)
    service.expire.side_effect = TimeoutError('uncertain expiration')
    assert actors[1].call('POST', f'/api/orders/{oid}/cancel', json={}).status_code == 502
    assert row(app, oid)['status'] == 'PENDING_PAYMENT'
    service.expire.side_effect = None
    assert actors[1].call('POST', f'/api/orders/{oid}/cancel', json={}).status_code == 200
    assert row(app, oid)['status'] == 'CANCELLED'


def test_real_signature_and_sdk_object_are_processed_idempotently(app, actors, monkeypatch):
    import hashlib
    import hmac
    import stripe
    import time
    oid = order(app, actors, 'PENDING_PAYMENT', session='')
    monkeypatch.setattr(config, 'PAYMENT_PROVIDER', 'stripe')
    monkeypatch.setattr(config, 'STRIPE_SECRET_KEY', 'sk_test_fake')
    monkeypatch.setattr(config, 'STRIPE_WEBHOOK_SECRET', 'whsec_test')
    monkeypatch.setattr(stripe.PaymentIntent, 'retrieve', lambda *a, **kw: {'latest_charge': 'ch_test'})
    event = {'id': 'evt_signed', 'object': 'event', 'type': 'checkout.session.completed', 'data': {'object': {
        'object': 'checkout.session', 'id': 'cs_signed', 'metadata': {'order_id': str(oid)}, 'payment_status': 'paid',
        'payment_intent': 'pi_test', 'currency': 'mxn', 'amount_total': 10000}}}
    payload = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(b'whsec_test', timestamp.encode() + b'.' + payload, hashlib.sha256).hexdigest()
    headers = {'Stripe-Signature': f't={timestamp},v1={digest}'}
    client = app.test_client()
    assert client.post('/api/stripe/webhook', data=payload, headers=headers).status_code == 200
    assert client.post('/api/stripe/webhook', data=payload, headers=headers).json['duplicate']
    assert row(app, oid)['status'] == 'HELD'


def test_sync_recovers_paid_checkout_without_browser_return(app, actors, monkeypatch):
    import payments
    import stripe
    oid = order(app, actors, 'PENDING_PAYMENT')
    session = stripe.StripeObject.construct_from({'id': 'cs_test', 'status': 'complete', 'payment_status': 'paid',
                                                  'metadata': {'order_id': str(oid)}, 'payment_intent': 'pi_test', 'currency': 'mxn', 'amount_total': 10000}, None)
    api = SimpleNamespace(checkout=SimpleNamespace(Session=SimpleNamespace(retrieve=lambda *a: session)),
                          PaymentIntent=SimpleNamespace(retrieve=lambda *a, **k: {'latest_charge': 'ch_test'}))
    monkeypatch.setattr(payments, 'get_provider', lambda name=None: SimpleNamespace(stripe=api))
    assert actors[1].call('POST', f'/api/orders/{oid}/sync', json={}).status_code == 200
    assert row(app, oid)['status'] == 'HELD'


def test_modified_content_requires_new_moderation(app, actors):
    seller, buyer, admin = actors
    pid = post(app, seller)
    response = seller.call('PUT', f'/api/posts/{pid}', data={'title': 'Texto modificado',
                                                             'description': 'Descripción nueva suficientemente larga', 'category': 'Libros', 'tipo': 'venta', 'price': '50'})
    assert response.status_code == 200
    assert buyer.call('GET', f'/api/posts/{pid}').status_code == 404
    assert admin.call('POST', f'/api/admin/posts/{pid}/moderate', json={'action': 'approve'}).status_code == 200
    assert buyer.call('GET', f'/api/posts/{pid}').status_code == 200


def test_backup_metadata_cannot_be_changed_outside_ciphertext(app, actors):
    from backups import create_backup, _read_backup
    with app.app_context():
        backup = create_backup()
        path = config.BACKUPS_DIR / backup['filename']
        with zipfile.ZipFile(path) as original:
            payload = original.read('payload.enc')
            meta = json.loads(original.read('meta.json'))
        meta['stats']['users'] = 999999
        with zipfile.ZipFile(path, 'w') as changed:
            changed.writestr('meta.json', json.dumps(meta))
            changed.writestr('payload.enc', payload)
        with pytest.raises(ValueError, match='alterados'):
            _read_backup(path)


def test_stripe_existing_transfer_is_reused_with_sdk16_objects(app):
    import stripe
    from payments import StripeProvider
    transfer = stripe.StripeObject.construct_from({'id': 'tr_existing', 'metadata': {'ecogallo_order_id': '7'}}, None)
    page = SimpleNamespace(auto_paging_iter=lambda: iter([transfer]))
    service = SimpleNamespace(list=Mock(return_value=page), create=Mock())
    provider = object.__new__(StripeProvider)
    provider.stripe = SimpleNamespace(Transfer=service)
    assert provider.release(7, 'ch_original', 'acct_seller', 10000) == 'tr_existing'
    service.create.assert_not_called()


def test_expired_password_recovery_grant_is_rejected(app, actors):
    seller, _, _ = actors
    with app.app_context():
        db.get_db().execute('UPDATE sessions SET reset_until=? WHERE user_id=?', (db.now() - 1, seller.id))
    assert seller.call('PUT', '/api/auth/password', json={'new_password': 'NewPassword123'}).status_code == 400


def test_existing_database_migrates_without_losing_pending_stripe_order(app, tmp_path, monkeypatch):
    legacy = tmp_path / 'legacy.sqlite'
    con = sqlite3.connect(legacy)
    con.executescript(db.SCHEMA)
    con.execute("INSERT INTO users(email,created_at) VALUES('legacy@edu.uaa.mx',0)")
    con.execute("""INSERT INTO posts(author_id,title,description,category,created_at)
                   VALUES(1,'Legacy','Descripción anterior','Libros',0)""")
    con.execute("""INSERT INTO orders(post_id,buyer_id,seller_id,amount_cents,status,created_at,updated_at)
                   VALUES(1,1,1,10000,'PENDING_PAYMENT',0,0)""")
    con.commit()
    con.close()
    monkeypatch.setattr(db, 'DB_PATH', legacy)
    db.init_db()
    db.init_db()
    con = sqlite3.connect(legacy)
    try:
        assert con.execute('SELECT payment_provider,status FROM orders').fetchone() == ('stripe', 'PENDING_PAYMENT')
        assert con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1
        assert 'reset_until' in {r[1] for r in con.execute('PRAGMA table_info(sessions)')}
    finally:
        con.close()


@pytest.mark.parametrize('status', ['failed', 'canceled'])
def test_failed_refunds_require_review_instead_of_showing_success(app, actors, monkeypatch, status):
    import orders
    oid = order(app, actors)
    provider = Mock()
    provider.refund.return_value = {'id': 're_failed', 'status': status}
    monkeypatch.setattr(orders, 'get_provider', lambda name=None: provider)
    assert actors[0].call('POST', f'/api/orders/{oid}/refund', json={}).status_code == 409
    assert row(app, oid)['status'] == 'PAYMENT_REVIEW'
    assert not actors[1].call('GET', f'/api/orders/{oid}').json['order']['actions']


def test_origin_check_allows_https_tunnel_but_not_other_sites(app):
    """Un túnel (trycloudflare/ngrok) llega por https a un servidor http local: mismo sitio, se permite."""
    c = app.test_client()
    body = {"email": "nadie@edu.uaa.mx", "password": "x"}
    tunnel = {"Host": "abc.trycloudflare.com", "Origin": "https://abc.trycloudflare.com"}
    assert c.post("/api/auth/login", json=body, headers=tunnel).status_code != 403
    evil = {"Host": "abc.trycloudflare.com", "Origin": "https://malo.example.com"}
    assert c.post("/api/auth/login", json=body, headers=evil).status_code == 403


def test_mobile_simulation_guard_prevents_external_checkout(app, actors, monkeypatch):
    import orders
    seller, buyer, _ = actors
    pid = post(app, seller)
    provider = SimpleNamespace(name='stripe')
    monkeypatch.setattr(orders, 'get_provider', lambda *args: provider)
    ready = Mock(side_effect=AssertionError('No debe consultar Stripe'))
    monkeypatch.setattr(orders, 'seller_ready', ready)
    response = buyer.call('POST', '/api/orders', json={'post_id': pid, 'simulation_only': True})
    assert response.status_code == 409
    ready.assert_not_called()
    with app.app_context():
        assert db.get_db().execute('SELECT status FROM posts WHERE id=?', (pid,)).fetchone()[0] == 'active'
        assert db.get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 0


def test_mobile_simulation_guard_prevents_external_order_action(app, actors, monkeypatch):
    import orders
    oid = order(app, actors, provider='stripe')
    provider = Mock(side_effect=AssertionError('No debe tocar proveedor externo'))
    monkeypatch.setattr(orders, 'get_provider', provider)
    response = actors[1].call('POST', f'/api/orders/{oid}/confirm', json={'simulation_only': True})
    assert response.status_code == 409
    assert row(app, oid)['status'] == 'HELD'
    provider.assert_not_called()


def test_can_remove_saved_post_after_it_becomes_unavailable(app, actors):
    seller, buyer, _ = actors
    pid = post(app, seller)
    assert buyer.call('POST', f'/api/posts/{pid}/favorite', json={}).json['favorited'] is True
    with app.app_context():
        db.get_db().execute("UPDATE posts SET status='pending' WHERE id=?", (pid,))
    assert buyer.call('POST', f'/api/posts/{pid}/favorite', json={}).json['favorited'] is False
    assert buyer.call('POST', f'/api/posts/{pid}/favorite', json={}).status_code == 404
