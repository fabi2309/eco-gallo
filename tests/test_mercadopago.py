"""Pagos con Mercado Pago (US-09). La API se simula: ninguna prueba sale a la red."""
import hashlib
import hmac

import pytest

import config
import db
import mercadopago
from test_regressions import Actor, app, post, row  # noqa: F401


class FakeMP:
    """Estado mínimo de la API de Mercado Pago."""

    def __init__(self):
        self.prefs, self.payments, self.refunds, self.calls = {}, [], [], []

    def __call__(self, method, path, body=None, idempotency=None):
        self.calls.append((method, path, idempotency))
        if path == "/checkout/preferences":
            pid = f"pref-{len(self.prefs) + 1}"
            self.prefs.setdefault(idempotency, {"id": pid, "init_point": f"https://mp.example/{pid}",
                                                "sandbox_init_point": f"https://sandbox.mp.example/{pid}", "body": body})
            return self.prefs[idempotency]
        if path.startswith("/v1/payments/search"):
            ref = path.split("external_reference=")[1].split("&")[0]
            return {"results": [p for p in self.payments if p["external_reference"] == ref]}
        if path.endswith("/refunds"):
            self.refunds.append((path, body, idempotency))
            return {"id": 777, "status": "approved"}
        if path.startswith("/v1/payments/"):
            pid = path.rsplit("/", 1)[1]
            return next(p for p in self.payments if str(p["id"]) == pid)
        raise AssertionError(path)

    def pay(self, group, amount_cents, status="approved", pid=None):
        p = {"id": pid or 5000 + len(self.payments), "status": status, "external_reference": group,
             "transaction_amount": amount_cents / 100, "currency_id": "MXN"}
        self.payments.append(p)
        return p


@pytest.fixture
def mp(app, monkeypatch):  # noqa: F811
    fake = FakeMP()
    monkeypatch.setattr(config, "PAYMENT_PROVIDER", "mercadopago")
    monkeypatch.setattr(config, "MP_ACCESS_TOKEN", "TEST-token")
    monkeypatch.setattr(config, "MP_WEBHOOK_SECRET", "secreto-webhook")
    monkeypatch.setattr(config, "MP_TEST", True)
    monkeypatch.setattr(mercadopago, "_api", fake)
    return fake


@pytest.fixture
def people(app):  # noqa: F811
    return Actor(app, "vendedor@edu.uaa.mx"), Actor(app, "comprador@edu.uaa.mx"), Actor(app, "admin@edu.uaa.mx", "admin")


def buy(app, people):  # noqa: F811
    seller, buyer, _ = people
    pid = post(app, seller)
    r = buyer.call("POST", "/api/orders", json={"post_id": pid})
    assert r.status_code == 201, r.json
    oid = r.json["id"]
    return pid, oid, row(app, oid)


def test_order_opens_checkout_pro_and_reserves_item(app, mp, people):  # noqa: F811
    pid, oid, o = buy(app, people)
    assert o["status"] == "PENDING_PAYMENT" and o["payment_provider"] == "mercadopago"
    assert o["checkout_group"].startswith(f"eg-{oid}-")
    pref = next(iter(mp.prefs.values()))
    assert pref["body"]["external_reference"] == o["checkout_group"]
    assert pref["body"]["items"][0]["unit_price"] == 100.0 and pref["body"]["items"][0]["currency_id"] == "MXN"
    assert o["checkout_url"] == pref["sandbox_init_point"]   # credenciales de prueba
    # Reintentar el pago reutiliza el mismo enlace (sin crear otra preferencia).
    r = people[1].call("POST", f"/api/orders/{oid}/checkout", json={})
    assert r.json["checkout_url"] == o["checkout_url"] and len(mp.prefs) == 1
    with app.app_context():
        assert db.get_db().execute("SELECT status FROM posts WHERE id=?", (pid,)).fetchone()[0] == "reserved"


def test_approved_payment_holds_money_and_wrong_amount_goes_to_review(app, mp, people):  # noqa: F811
    _, oid, o = buy(app, people)
    mp.pay(o["checkout_group"], 10000)
    with app.test_request_context():
        assert mercadopago.sync_group(o["checkout_group"]) == "aprobado"
    o = row(app, oid)
    assert o["status"] == "HELD" and o["provider_payment_id"] == "5000"

    seller, buyer, admin = people
    pid2 = post(app, seller)
    oid2 = buyer.call("POST", "/api/orders", json={"post_id": pid2}).json["id"]
    mp.pay(row(app, oid2)["checkout_group"], 1)   # importe alterado
    with app.test_request_context():
        mercadopago.sync_group(row(app, oid2)["checkout_group"])
    assert row(app, oid2)["status"] == "PAYMENT_REVIEW"


def test_oxxo_pending_keeps_reservation_and_blocks_cancel(app, mp, people):  # noqa: F811
    _, oid, o = buy(app, people)
    mp.pay(o["checkout_group"], 10000, status="pending")
    r = people[1].call("POST", f"/api/orders/{oid}/cancel", json={})
    assert r.status_code == 409 and row(app, oid)["status"] == "PENDING_PAYMENT"


def test_cancel_without_payment_frees_item(app, mp, people):  # noqa: F811
    pid, oid, _ = buy(app, people)
    assert people[1].call("POST", f"/api/orders/{oid}/cancel", json={}).status_code == 200
    assert row(app, oid)["status"] == "CANCELLED"
    with app.app_context():
        assert db.get_db().execute("SELECT status FROM posts WHERE id=?", (pid,)).fetchone()[0] == "active"


def test_expired_preference_without_payment_is_cancelled(app, mp, people):  # noqa: F811
    _, oid, o = buy(app, people)
    with app.app_context():
        db.get_db().execute("UPDATE orders SET created_at=? WHERE id=?", (db.now() - 30 * 3600, oid))
    mp.pay(o["checkout_group"], 10000, status="rejected")
    with app.test_request_context():
        assert mercadopago.sync_group(o["checkout_group"]) == "vencido"
    assert row(app, oid)["status"] == "CANCELLED"


def test_release_leaves_payout_for_admin_and_refund_uses_api(app, mp, people):  # noqa: F811
    seller, buyer, admin = people
    _, oid, o = buy(app, people)
    mp.pay(o["checkout_group"], 10000)
    with app.test_request_context():
        mercadopago.sync_group(o["checkout_group"])
    assert buyer.call("POST", f"/api/orders/{oid}/confirm", json={}).status_code == 200
    o = row(app, oid)
    assert o["status"] == "RELEASED" and o["payout_status"] == "pending"
    assert seller.client.get("/api/wallet").json["payout_pending_cents"] == 10000
    assert admin.client.get("/api/admin/payouts").json["total_cents"] == 10000
    assert admin.call("POST", f"/api/admin/payouts/{oid}", json={"reference": "x"}).status_code == 400
    assert admin.call("POST", f"/api/admin/payouts/{oid}", json={"reference": "SPEI 123456"}).status_code == 200
    assert row(app, oid)["payout_status"] == "paid"
    assert buyer.call("POST", f"/api/admin/payouts/{oid}", json={"reference": "SPEI 1"}).status_code == 403

    _, oid2, o2 = buy(app, people)
    mp.pay(o2["checkout_group"], 10000, pid=9999)
    with app.test_request_context():
        mercadopago.sync_group(o2["checkout_group"])
    assert seller.call("POST", f"/api/orders/{oid2}/refund", json={}).status_code == 200
    assert row(app, oid2)["status"] == "REFUNDED"
    path, body, idem = mp.refunds[-1]
    assert path == "/v1/payments/9999/refunds" and body == {"amount": 100.0} and idem == f"ecogallo-refund-{oid2}"


def test_chargeback_after_payment_goes_to_review(app, mp, people):  # noqa: F811
    _, oid, o = buy(app, people)
    p = mp.pay(o["checkout_group"], 10000)
    with app.test_request_context():
        mercadopago.sync_group(o["checkout_group"])
    p["status"] = "charged_back"
    with app.test_request_context():
        assert mercadopago.sync_group(o["checkout_group"]) == "revision"
    assert row(app, oid)["status"] == "PAYMENT_REVIEW"


def sign(data_id, request_id, ts="1700000000", secret="secreto-webhook"):
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    return f"ts={ts},v1={hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()}"


def test_webhook_requires_valid_signature_and_queries_api(app, mp, people):  # noqa: F811
    _, oid, o = buy(app, people)
    p = mp.pay(o["checkout_group"], 10000, pid=4242)
    c = app.test_client()
    url = "/api/mercadopago/webhook?data.id=4242&type=payment"
    body = {"type": "payment", "data": {"id": "4242"}}
    r = c.post(url, json=body, headers={"x-signature": sign("4242", "req-1", secret="otra"), "x-request-id": "req-1"})
    assert r.status_code == 401 and row(app, oid)["status"] == "PENDING_PAYMENT"
    r = c.post(url, json=body, headers={"x-signature": sign("4242", "req-1"), "x-request-id": "req-1"})
    assert r.status_code == 200 and row(app, oid)["status"] == "HELD"
    # Repetir la notificación no cambia nada (idempotente).
    r = c.post(url, json=body, headers={"x-signature": sign("4242", "req-2"), "x-request-id": "req-2"})
    assert r.status_code == 200 and row(app, oid)["status"] == "HELD"
    assert p["id"] == 4242


def test_return_url_syncs_and_redirects(app, mp, people):  # noqa: F811
    _, oid, o = buy(app, people)
    mp.pay(o["checkout_group"], 10000)
    r = app.test_client().get(f"/api/mercadopago/return/{oid}?collection_status=approved")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/#/order/{oid}")
    assert row(app, oid)["status"] == "HELD"


def test_config_rules(monkeypatch):
    monkeypatch.setattr(config, "PAYMENT_PROVIDER", "mercadopago")
    monkeypatch.setattr(config, "MP_ACCESS_TOKEN", "")
    monkeypatch.setattr(config, "MP_WEBHOOK_SECRET", "")
    with pytest.raises(RuntimeError):
        config.validate_runtime()
    monkeypatch.setattr(config, "MP_ACCESS_TOKEN", "APP_USR-x")
    monkeypatch.setattr(config, "MP_WEBHOOK_SECRET", "s")
    monkeypatch.setattr(config, "MP_TEST", False)
    monkeypatch.setattr(config, "PRODUCTION", False)
    with pytest.raises(RuntimeError):   # cobros reales fuera de producción
        config.validate_runtime()


def test_seller_with_pending_payout_cannot_delete_account(app, mp, people):  # noqa: F811
    seller, buyer, admin = people
    _, oid, o = buy(app, people)
    mp.pay(o["checkout_group"], 10000)
    with app.test_request_context():
        mercadopago.sync_group(o["checkout_group"])
    buyer.call("POST", f"/api/orders/{oid}/confirm", json={})
    assert seller.call("DELETE", "/api/me", json={"confirm": "ELIMINAR", "password": "CurrentPass123"}).status_code == 409
    r = admin.call("DELETE", f"/api/admin/users/{seller.id}", json={"confirm_email": "vendedor@edu.uaa.mx"})
    assert r.status_code == 409
