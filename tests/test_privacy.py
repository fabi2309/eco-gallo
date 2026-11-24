"""Aviso de privacidad, consentimiento y derechos ARCO (tesina 5.3 y 5.9)."""
import json

import config
import db
from test_regressions import Actor, app, order, post  # noqa: F401 - fixture y ayudantes compartidos


def user_row(app, uid):  # noqa: F811
    with app.app_context():
        return dict(db.get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())


def test_legal_info_is_public_and_terms_are_required_until_accepted(app):  # noqa: F811
    anon = app.test_client()
    r = anon.get("/api/legal")
    assert r.status_code == 200 and r.json["version"] == config.LEGAL_VERSION
    assert anon.get("/api/meta").json["legal"]["version"] == config.LEGAL_VERSION

    u = Actor(app, "nuevo@edu.uaa.mx")
    assert u.client.get("/api/me").json["needs_terms"] is True
    assert u.call("POST", "/api/me/terms", json={"accept": True, "version": "vieja"}).status_code == 400
    assert u.call("POST", "/api/me/terms", json={"accept": False, "version": config.LEGAL_VERSION}).status_code == 400
    r = u.call("POST", "/api/me/terms", json={"accept": True, "version": config.LEGAL_VERSION})
    assert r.status_code == 200
    me = u.client.get("/api/me").json
    assert me["needs_terms"] is False
    assert me["user"]["terms_version"] == config.LEGAL_VERSION and me["user"]["terms_accepted_at"] > 0


def test_terms_can_be_accepted_before_completing_profile(app):  # noqa: F811
    u = Actor(app, "sinperfil@edu.uaa.mx")
    with app.app_context():
        db.get_db().execute("UPDATE users SET name='' WHERE id=?", (u.id,))
    r = u.call("POST", "/api/me/terms", json={"accept": True, "version": config.LEGAL_VERSION})
    assert r.status_code == 200


def test_new_legal_version_asks_again(app, monkeypatch):  # noqa: F811
    u = Actor(app, "version@edu.uaa.mx")
    u.call("POST", "/api/me/terms", json={"accept": True, "version": config.LEGAL_VERSION})
    monkeypatch.setattr(config, "LEGAL_VERSION", "2099-01")
    assert u.client.get("/api/me").json["needs_terms"] is True


def test_export_contains_own_data_and_no_secrets(app):  # noqa: F811
    seller, buyer = Actor(app, "vende@edu.uaa.mx"), Actor(app, "compra@edu.uaa.mx")
    pid = post(app, seller)
    buyer.call("POST", "/api/messages", json={"post_id": pid, "receiver_id": seller.id, "content": "¿Sigue disponible?"})
    buyer.call("POST", "/api/wishlist", json={"term": "calculadora"})
    r = seller.client.get("/api/me/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"]
    data = json.loads(r.data)
    assert data["profile"]["email"] == "vende@edu.uaa.mx"
    assert [p["id"] for p in data["posts"]] == [pid]
    assert [m["direction"] for m in data["messages"]] == ["recibido"]
    raw = r.data.decode()
    assert "password_hash" not in raw and "totp_secret" not in raw
    # Nadie más aparece como dueño: el comprador no recibe las publicaciones del vendedor.
    other = json.loads(buyer.client.get("/api/me/export").data)
    assert other["posts"] == [] and other["profile"]["email"] == "compra@edu.uaa.mx"
    assert [w["term"] for w in other["wishlist"]] == ["calculadora"]
    assert other["messages"][0]["direction"] == "enviado"
    assert app.test_client().get("/api/me/export").status_code == 401


def test_delete_me_requires_confirmation_and_password(app):  # noqa: F811
    u = Actor(app, "baja@edu.uaa.mx")
    assert u.call("DELETE", "/api/me", json={"password": "CurrentPass123"}).status_code == 400
    assert u.call("DELETE", "/api/me", json={"confirm": "ELIMINAR", "password": "mala"}).status_code == 400
    assert user_row(app, u.id)["deleted_at"] == 0

    pid = post(app, u)
    r = u.call("DELETE", "/api/me", json={"confirm": "eliminar", "password": "CurrentPass123"})
    assert r.status_code == 200
    row = user_row(app, u.id)
    assert row["deleted_at"] > 0 and row["email"].endswith("@eliminado.invalid")
    assert row["name"] == "Cuenta eliminada" and row["password_hash"] == ""
    with app.app_context():
        con = db.get_db()
        assert con.execute("SELECT status FROM posts WHERE id=?", (pid,)).fetchone()[0] == "removed"
        assert con.execute("SELECT COUNT(*) FROM sessions WHERE user_id=?", (u.id,)).fetchone()[0] == 0
    # La sesión ya no sirve.
    assert u.client.get("/api/me").json["user"] is None


def test_delete_me_without_password_needs_recent_code_login(app):  # noqa: F811
    u = Actor(app, "sinclave@edu.uaa.mx")
    with app.app_context():
        db.get_db().execute("UPDATE users SET password_hash='' WHERE id=?", (u.id,))
    r = u.call("DELETE", "/api/me", json={"confirm": "ELIMINAR"})
    assert r.status_code == 403 and r.json["needs_recent_login"] is True
    # Acceso reciente por código al correo (lo que hace /api/auth/verify).
    with app.app_context():
        db.get_db().execute("UPDATE sessions SET reset_until=? WHERE user_id=?", (db.now() + 600, u.id))
    assert u.call("DELETE", "/api/me", json={"confirm": "ELIMINAR"}).status_code == 200


def test_delete_me_blocked_with_open_orders_and_for_admins(app):  # noqa: F811
    seller, buyer, admin = Actor(app, "s@edu.uaa.mx"), Actor(app, "b@edu.uaa.mx"), Actor(app, "a@edu.uaa.mx", "admin")
    order(app, (seller, buyer, admin), status="HELD", provider="simulado", session="")
    r = buyer.call("DELETE", "/api/me", json={"confirm": "ELIMINAR", "password": "CurrentPass123"})
    assert r.status_code == 409 and user_row(app, buyer.id)["deleted_at"] == 0
    r = admin.call("DELETE", "/api/me", json={"confirm": "ELIMINAR", "password": "CurrentPass123"})
    assert r.status_code == 400 and user_row(app, admin.id)["deleted_at"] == 0


def test_admin_delete_still_anonymizes(app):  # noqa: F811
    target, admin = Actor(app, "objetivo@edu.uaa.mx"), Actor(app, "jefe@edu.uaa.mx", "admin")
    r = admin.call("DELETE", f"/api/admin/users/{target.id}", json={"confirm_email": "objetivo@edu.uaa.mx"})
    assert r.status_code == 200
    assert user_row(app, target.id)["email"] == f"eliminado-{target.id}@eliminado.invalid"
