"""Carrito (US-04): varios artículos, un pago; cada artículo conserva su propia orden protegida."""
import db
import mercadopago
from test_mercadopago import mp  # noqa: F401
from test_regressions import Actor, app, post, row  # noqa: F401


def make(app, n=2):  # noqa: F811
    s1, s2, buyer = Actor(app, "s1@edu.uaa.mx"), Actor(app, "s2@edu.uaa.mx"), Actor(app, "comp@edu.uaa.mx")
    pids = [post(app, s1), post(app, s2)][:n]
    return s1, s2, buyer, pids


def test_cart_add_rules_and_listing(app):  # noqa: F811
    s1, s2, buyer, (p1, p2) = make(app)
    assert s1.call("POST", "/api/cart", json={"post_id": p1}).status_code == 400          # lo propio no
    assert buyer.call("POST", "/api/cart", json={"post_id": p1}).status_code == 200
    assert buyer.call("POST", "/api/cart", json={"post_id": p1}).status_code == 200       # sin duplicar
    assert buyer.call("POST", "/api/cart", json={"post_id": p2}).status_code == 200
    c = buyer.client.get("/api/cart").json
    assert c["count"] == 2 and c["total_cents"] == 20000
    assert buyer.call("DELETE", f"/api/cart/{p2}").status_code == 200
    assert buyer.client.get("/api/cart").json["count"] == 1


def test_simulated_checkout_creates_one_held_order_per_item(app):  # noqa: F811
    s1, s2, buyer, (p1, p2) = make(app)
    for p in (p1, p2):
        buyer.call("POST", "/api/cart", json={"post_id": p})
    r = buyer.call("POST", "/api/cart/checkout", json={})
    assert r.status_code == 201
    o1, o2 = (row(app, i) for i in r.json["ids"])
    assert o1["status"] == o2["status"] == "HELD"
    assert o1["checkout_group"] == o2["checkout_group"] and {o1["seller_id"], o2["seller_id"]} == {s1.id, s2.id}
    assert buyer.client.get("/api/cart").json["items"] == []
    # Cada vendedor gestiona su orden por separado.
    assert s1.call("POST", f"/api/orders/{o1['id']}/deliver", json={}).status_code == 200
    assert s2.call("POST", f"/api/orders/{o1['id']}/deliver", json={}).status_code in (403, 404)


def test_checkout_is_all_or_nothing(app, monkeypatch):  # noqa: F811
    import cart
    s1, s2, buyer, (p1, p2) = make(app)
    for p in (p1, p2):
        buyer.call("POST", "/api/cart", json={"post_id": p})
    real, calls = cart.place_order, []

    def racy(db_, pid, provider, group=None, **kw):
        calls.append(pid)
        if len(calls) == 2:   # otra persona reservó el segundo artículo justo antes
            raise cart.OrderRefused("Alguien más acaba de reservar este artículo.", 409)
        return real(db_, pid, provider, group, **kw)
    monkeypatch.setattr(cart, "place_order", racy)
    r = buyer.call("POST", "/api/cart/checkout", json={})
    assert r.status_code == 409 and "No se reservó ningún artículo" in r.json["message"]
    with app.app_context():
        con = db.get_db()
        assert con.execute("SELECT COUNT(*) FROM orders WHERE buyer_id=?", (buyer.id,)).fetchone()[0] == 0
        assert con.execute("SELECT status FROM posts WHERE id=?", (p1,)).fetchone()[0] == "active"
    assert buyer.client.get("/api/cart").json["count"] == 2


def test_bought_item_leaves_every_cart(app):  # noqa: F811
    s1, s2, buyer, (p1, p2) = make(app)
    buyer.call("POST", "/api/cart", json={"post_id": p1})
    other = Actor(app, "rapido@edu.uaa.mx")
    assert other.call("POST", "/api/orders", json={"post_id": p1}).status_code == 201
    assert buyer.client.get("/api/cart").json["items"] == []


def test_mercadopago_cart_uses_single_preference_and_partial_refund(app, mp):  # noqa: F811
    s1, s2, buyer, (p1, p2) = make(app)
    for p in (p1, p2):
        buyer.call("POST", "/api/cart", json={"post_id": p})
    r = buyer.call("POST", "/api/cart/checkout", json={})
    assert r.status_code == 201 and r.json["checkout_url"]
    assert len(mp.prefs) == 1
    pref = next(iter(mp.prefs.values()))
    assert len(pref["body"]["items"]) == 2
    o1, o2 = (row(app, i) for i in r.json["ids"])
    mp.pay(o1["checkout_group"], 20000, pid=31337)
    with app.test_request_context():
        assert mercadopago.sync_group(o1["checkout_group"]) == "aprobado"
    assert row(app, o1["id"])["status"] == row(app, o2["id"])["status"] == "HELD"
    # El vendedor 2 devuelve solo su parte.
    assert s2.call("POST", f"/api/orders/{o2['id']}/refund", json={}).status_code == 200
    assert mp.refunds[-1][1] == {"amount": 100.0}
    assert row(app, o2["id"])["status"] == "REFUNDED" and row(app, o1["id"])["status"] == "HELD"
