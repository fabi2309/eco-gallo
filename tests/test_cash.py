"""Pago en efectivo al entregar: se aparta el artículo, el vendedor registra el cobro y no pasa dinero por la plataforma."""
import db
from test_regressions import Actor, app, post, row  # noqa: F401


def make(app):  # noqa: F811
    seller, buyer = Actor(app, "vende@edu.uaa.mx"), Actor(app, "compra@edu.uaa.mx")
    return seller, buyer, post(app, seller)


def post_status(app, pid):  # noqa: F811
    with app.app_context():
        return db.get_db().execute("SELECT status FROM posts WHERE id=?", (pid,)).fetchone()[0]


def test_meta_offers_both_methods(app):  # noqa: F811
    m = app.test_client().get("/api/meta").json
    assert m["payment_methods"] == ["en_linea", "efectivo"]


def test_cash_order_reserves_and_seller_registers_payment(app):  # noqa: F811
    seller, buyer, pid = make(app)
    r = buyer.call("POST", "/api/orders", json={"post_id": pid, "method": "efectivo"})
    assert r.status_code == 201
    o = row(app, r.json["id"])
    assert o["status"] == "CASH_PENDING" and o["payment_provider"] == "efectivo"
    assert post_status(app, pid) == "reserved"
    # Nadie más puede comprarlo mientras está apartado.
    other = Actor(app, "otra@edu.uaa.mx")
    assert other.call("POST", "/api/orders", json={"post_id": pid, "method": "efectivo"}).status_code == 409
    d = buyer.client.get(f"/api/orders/{o['id']}").json["order"]
    assert d["payment_method"] == "efectivo" and d["actions"] == ["cancel_cash"]
    # El comprador no puede marcar el cobro; el vendedor sí.
    assert buyer.call("POST", f"/api/orders/{o['id']}/cash-received", json={}).status_code == 403
    assert seller.call("POST", f"/api/orders/{o['id']}/cash-received", json={}).status_code == 200
    assert row(app, o["id"])["status"] == "RELEASED" and post_status(app, pid) == "sold"
    # El efectivo no entra al saldo de la plataforma ni queda por liquidar.
    w = seller.client.get("/api/wallet").json
    assert w["available_cents"] == 0 and w["payout_pending_cents"] == 0


def test_cash_order_can_be_cancelled_by_either_side(app):  # noqa: F811
    seller, buyer, pid = make(app)
    oid = buyer.call("POST", "/api/orders", json={"post_id": pid, "method": "efectivo"}).json["id"]
    assert buyer.call("POST", f"/api/orders/{oid}/cancel-cash", json={}).status_code == 200
    assert row(app, oid)["status"] == "CANCELLED" and post_status(app, pid) == "active"
    oid2 = buyer.call("POST", "/api/orders", json={"post_id": pid, "method": "efectivo"}).json["id"]
    assert seller.call("POST", f"/api/orders/{oid2}/cancel-cash", json={}).status_code == 200
    assert post_status(app, pid) == "active"
    # Las acciones de pago en línea no aplican a una compra en efectivo.
    oid3 = buyer.call("POST", "/api/orders", json={"post_id": pid, "method": "efectivo"}).json["id"]
    assert buyer.call("POST", f"/api/orders/{oid3}/confirm", json={}).status_code == 403
    assert seller.call("POST", f"/api/orders/{oid3}/refund", json={}).status_code == 403


def test_cash_checkout_from_cart(app):  # noqa: F811
    s1, buyer = Actor(app, "s1@edu.uaa.mx"), Actor(app, "comp@edu.uaa.mx")
    s2 = Actor(app, "s2@edu.uaa.mx")
    pids = [post(app, s1), post(app, s2)]
    for p in pids:
        buyer.call("POST", "/api/cart", json={"post_id": p})
    r = buyer.call("POST", "/api/cart/checkout", json={"method": "efectivo"})
    assert r.status_code == 201 and len(r.json["ids"]) == 2
    assert all(row(app, i)["status"] == "CASH_PENDING" for i in r.json["ids"])
    assert buyer.client.get("/api/cart").json["count"] == 0


def test_invalid_method_rejected(app):  # noqa: F811
    seller, buyer, pid = make(app)
    assert buyer.call("POST", "/api/orders", json={"post_id": pid, "method": "bitcoin"}).status_code == 400


def test_open_cash_order_blocks_account_deletion(app):  # noqa: F811
    import accounts
    seller, buyer, pid = make(app)
    buyer.call("POST", "/api/orders", json={"post_id": pid, "method": "efectivo"})
    with app.app_context():
        assert accounts.has_open_orders(db.get_db(), buyer.id)
