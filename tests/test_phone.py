"""Pagos con tarjeta: celular confirmado por SMS, tarjeta del comprador y cuenta del vendedor."""
import config
import db
import phone
from test_regressions import TEST_CARD, Actor, app, post, row  # noqa: F401


def test_normalize_phone():
    assert phone.normalize_phone("449 123 4567") == "+524491234567"
    assert phone.normalize_phone("+52 (449) 123-4567") == "+524491234567"
    assert phone.normalize_phone("5214491234567") == "+524491234567"
    for bad in ("12345", "0491234567", "449123456789", "", None, "abc"):
        assert phone.normalize_phone(bad) is None


def confirm(actor, number="4491112233"):
    r = actor.call("POST", "/api/me/phone", json={"phone": number})
    assert r.status_code == 200, r.json
    return r.json["dev_code"]


def test_sms_code_flow_and_attempt_limit(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DEV", True)
    u = Actor(app, "nuevo@edu.uaa.mx", card=False)
    assert u.client.get("/api/me").json["user"]["payments"]["card_ready"] is False
    code = confirm(u)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(4):
        assert u.call("POST", "/api/me/phone/verify", json={"code": wrong}).status_code == 400
    assert u.call("POST", "/api/me/phone/verify", json={"code": code}).status_code == 200
    me = u.client.get("/api/me").json["user"]["payments"]
    assert me["phone_verified"] and me["phone"] == "449 111 2233"
    # Un código ya usado no sirve otra vez.
    assert u.call("POST", "/api/me/phone/verify", json={"code": code}).status_code == 400


def test_too_many_wrong_codes_burns_the_code(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DEV", True)
    u = Actor(app, "intentos@edu.uaa.mx", card=False)
    code = confirm(u)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(phone.MAX_ATTEMPTS):
        u.call("POST", "/api/me/phone/verify", json={"code": wrong})
    assert u.call("POST", "/api/me/phone/verify", json={"code": code}).status_code == 429


def test_cooldown_and_number_already_taken(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DEV", True)
    a, b = Actor(app, "a@edu.uaa.mx", card=False), Actor(app, "b@edu.uaa.mx", card=False)
    code = confirm(a, "4497778899")
    assert a.call("POST", "/api/me/phone", json={"phone": "4497778899"}).status_code == 429   # espera entre envíos
    a.call("POST", "/api/me/phone/verify", json={"code": code})
    assert b.call("POST", "/api/me/phone", json={"phone": "449 777 8899"}).status_code == 409


def test_sms_goes_through_provider_when_configured(app, monkeypatch):  # noqa: F811
    sent = []
    monkeypatch.setattr(config, "SMS_ENABLED", True)
    monkeypatch.setattr(phone, "send_sms", lambda to, text: sent.append((to, text)))
    u = Actor(app, "sms@edu.uaa.mx", card=False)
    r = u.call("POST", "/api/me/phone", json={"phone": "4491230000"})
    assert r.status_code == 200 and "dev_code" not in r.json          # con SMS real el código NO sale en pantalla
    assert sent and sent[0][0] == "+524491230000" and "ECO-GALLO" in sent[0][1]


def test_without_sms_outside_dev_no_code_is_revealed(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DEV", False)
    monkeypatch.setattr(config, "SMS_ENABLED", False)
    u = Actor(app, "prod@edu.uaa.mx", card=False)
    r = u.call("POST", "/api/me/phone", json={"phone": "4491230001"})
    assert r.status_code == 503 and "dev_code" not in r.json


def test_payout_requires_confirmed_phone_and_stores_only_last4(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DEV", True)
    u = Actor(app, "vende@edu.uaa.mx", card=False)
    body = {"kind": "clabe", "last4": "6789", "holder": "Vendedor Uno"}
    assert u.call("PUT", "/api/me/payout", json=body).status_code == 409
    u.call("POST", "/api/me/phone/verify", json={"code": confirm(u)})
    assert u.call("PUT", "/api/me/payout", json={**body, "last4": "012180012345678912"}).status_code == 400
    r = u.call("PUT", "/api/me/payout", json=body)
    assert r.status_code == 200 and r.json["payments"]["payout_ready"]


def test_card_purchase_needs_buyer_phone_and_seller_account(app):  # noqa: F811
    seller, buyer = Actor(app, "s@edu.uaa.mx"), Actor(app, "c@edu.uaa.mx", card=False)
    pid = post(app, seller)
    r = buyer.call("POST", "/api/orders", json={"post_id": pid})
    assert r.status_code == 409 and "celular" in r.json["message"]
    # El efectivo no pide nada de eso.
    assert buyer.call("POST", "/api/orders", json={"post_id": pid, "method": "efectivo"}).status_code == 201

    s2, b2 = Actor(app, "s2@edu.uaa.mx", card=False), Actor(app, "c2@edu.uaa.mx")
    pid2 = post(app, s2)
    r = b2.call("POST", "/api/orders", json={"post_id": pid2})
    assert r.status_code == 409 and "vendedor" in r.json["message"]
    assert b2.client.get(f"/api/posts/{pid2}").json["post"]["accepts_card"] is False


def test_card_data_is_validated_and_only_last4_kept(app):  # noqa: F811
    seller, buyer = Actor(app, "s@edu.uaa.mx"), Actor(app, "c@edu.uaa.mx")
    pid = post(app, seller)
    for bad in ({**TEST_CARD, "exp_year": 2021}, {**TEST_CARD, "exp_month": 13}, {**TEST_CARD, "last4": "42"},
                {**TEST_CARD, "brand": "otra"}, {**TEST_CARD, "holder": "x"}, None):
        assert buyer.call("POST", "/api/orders", json={"post_id": pid, "card": bad}).status_code == 400
    r = buyer.call("POST", "/api/orders", json={"post_id": pid, "card": {**TEST_CARD, "number": "4242424242424242", "cvv": "123"}})
    assert r.status_code == 201
    o = row(app, r.json["id"])
    assert o["card_brand"] == "visa" and o["card_last4"] == "4242"
    with app.app_context():
        dump = "\n".join(db.get_db().iterdump())
    assert "4242424242424242" not in dump          # el número completo nunca se guarda


def test_phones_visible_only_to_the_parties(app):  # noqa: F811
    seller, buyer, other = Actor(app, "s@edu.uaa.mx"), Actor(app, "c@edu.uaa.mx"), Actor(app, "x@edu.uaa.mx")
    admin = Actor(app, "adm@edu.uaa.mx", role="admin")
    oid = buyer.call("POST", "/api/orders", json={"post_id": post(app, seller)}).json["id"]
    b = buyer.client.get(f"/api/orders/{oid}").json["order"]
    s = seller.client.get(f"/api/orders/{oid}").json["order"]
    a = admin.client.get(f"/api/orders/{oid}").json["order"]
    assert b["seller"].get("phone") and "phone" not in b["buyer"] and b["card"]["last4"] == "4242"
    assert s["buyer"].get("phone") and "card" not in s and s["payout_account"]["last4"] == "1234"
    assert a["buyer"].get("phone") and a["seller"].get("phone")
    assert other.client.get(f"/api/orders/{oid}").status_code == 404
    # En efectivo no se comparten teléfonos.
    cid = buyer.call("POST", "/api/orders", json={"post_id": post(app, seller), "method": "efectivo"}).json["id"]
    assert "phone" not in buyer.client.get(f"/api/orders/{cid}").json["order"]["seller"]


def test_phone_cannot_be_removed_with_open_card_order(app):  # noqa: F811
    seller, buyer = Actor(app, "s@edu.uaa.mx"), Actor(app, "c@edu.uaa.mx")
    buyer.call("POST", "/api/orders", json={"post_id": post(app, seller)})
    assert buyer.call("DELETE", "/api/me/phone").status_code == 409


def test_privacy_export_and_anonymize_cover_phone(app):  # noqa: F811
    import accounts
    u = Actor(app, "priv@edu.uaa.mx")
    exp = u.client.get("/api/me/export").json
    profile = exp.get("profile") or exp.get("data", {}).get("profile")
    assert profile["phone"].startswith("+52") and profile["payout_account"]["last4"] == "1234"
    with app.app_context():
        accounts.anonymize_account(db.get_db(), u.id, "priv@edu.uaa.mx")
        r = db.get_db().execute("SELECT phone, payout_last4 FROM users WHERE id=?", (u.id,)).fetchone()
        assert tuple(r) == ("", "")


def test_dev_shows_code_when_sms_provider_fails(app, monkeypatch):  # noqa: F811
    def boom(to, text):
        raise RuntimeError("Twilio respondió 400: 'From' is not a Twilio phone number")
    monkeypatch.setattr(config, "SMS_ENABLED", True)
    monkeypatch.setattr(config, "DEV", True)
    monkeypatch.setattr(phone, "send_sms", boom)
    u = Actor(app, "falla@edu.uaa.mx", card=False)
    r = u.call("POST", "/api/me/phone", json={"phone": "4491239999"})
    assert r.status_code == 200 and r.json["dev_code"]
    assert u.call("POST", "/api/me/phone/verify", json={"code": r.json["dev_code"]}).status_code == 200
    monkeypatch.setattr(config, "DEV", False)
    u2 = Actor(app, "falla2@edu.uaa.mx", card=False)
    r = u2.call("POST", "/api/me/phone", json={"phone": "4491238888"})
    assert r.status_code == 502 and "dev_code" not in r.json
