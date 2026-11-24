"""Compatibility of the native client with the extended web API."""
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import db
from test_regressions import Actor, actors, app, post  # noqa: F401


def test_mobile_legal_documents_match_web(app):  # noqa: F811
    root = Path(__file__).resolve().parent.parent
    templates = json.loads((root / 'backend/legal_documents.json').read_text(encoding='utf-8'))
    web = (root / 'frontend/js/views/legal.js').read_text(encoding='utf-8')
    for key, function in [('privacy', 'privacyHtml'), ('terms', 'termsHtml')]:
        match = re.search(r'export function ' + function + r'\(m\)\s*\{.*?return `([\s\S]*?)`;', web, re.S)
        assert match and templates[key] == match[1]
    data = app.test_client().get('/api/legal').json
    assert data['version'] and data['operator'] in data['documents']['privacy']
    assert all('${' not in document for document in data['documents'].values())


def test_forwarded_host_requires_authenticated_proxy(app, monkeypatch):  # noqa: F811
    client = app.test_client()
    body = {'email': 'nadie@edu.uaa.mx', 'password': 'incorrecta'}
    headers = {'Origin': 'https://evil.example', 'X-Forwarded-Host': 'evil.example'}
    monkeypatch.delenv('ECOGALLO_PROXY_TOKEN', raising=False)
    assert client.post('/api/auth/login', json=body, headers=headers).status_code == 403
    monkeypatch.setenv('ECOGALLO_PROXY_TOKEN', 'proxy-local-test')
    assert client.post('/api/auth/login', json=body, headers=headers).status_code == 403
    headers['X-Ecogallo-Proxy'] = 'proxy-local-test'
    assert client.post('/api/auth/login', json=body, headers=headers).status_code == 401


def test_mobile_cart_guard_precedes_external_payment(app, actors, monkeypatch):  # noqa: F811
    import cart
    seller, buyer, _ = actors
    pid = post(app, seller)
    assert buyer.call('POST', '/api/cart', json={'post_id': pid}).status_code == 200
    monkeypatch.setattr(cart, 'get_provider', lambda: SimpleNamespace(name='mercadopago'))
    response = buyer.call('POST', '/api/cart/checkout', json={'simulation_only': True})
    assert response.status_code == 409
    with app.app_context():
        assert db.get_db().execute('SELECT status FROM posts WHERE id=?', (pid,)).fetchone()[0] == 'active'
        assert db.get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 0


def test_cash_still_works_with_mobile_safety_flag(app, actors):  # noqa: F811
    seller, buyer, _ = actors
    response = buyer.call('POST', '/api/orders', json={'post_id': post(app, seller), 'method': 'efectivo', 'simulation_only': True})
    assert response.status_code == 201
    oid = response.json['id']
    assert buyer.call('GET', f'/api/orders/{oid}').json['order']['status'] == 'CASH_PENDING'
    assert seller.call('POST', f'/api/orders/{oid}/cash-received', json={'simulation_only': True}).status_code == 200
    assert buyer.call('GET', f'/api/orders/{oid}').json['order']['status'] == 'RELEASED'


def test_read_selected_notification_does_not_mark_new_or_foreign(app, actors):  # noqa: F811
    seller, buyer, _ = actors
    with app.app_context():
        def note(uid):
            return db.get_db().execute('INSERT INTO notifications(user_id,text,link,created_at) VALUES(?,?,?,?)',
                                       (uid, 'Aviso', '#/mine', db.now())).lastrowid
        first, new, foreign = note(seller.id), note(seller.id), note(buyer.id)
    assert seller.call('POST', '/api/notifications/read', json={'ids': [first, foreign]}).status_code == 200
    values = {n['id']: n['read_at'] for n in seller.call('GET', '/api/notifications').json['notifications']}
    assert values[first] and values[new] is None
    assert buyer.call('GET', '/api/notifications').json['notifications'][0]['read_at'] is None


@pytest.mark.parametrize('ids', [[True], [-1], ['1'], [2**80], list(range(1, 52)), '1'])
def test_mobile_notification_validation(actors, ids):  # noqa: F811
    assert actors[0].call('POST', '/api/notifications/read', json={'ids': ids}).status_code == 400
