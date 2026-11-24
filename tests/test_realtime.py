"""Chat incremental y contadores de avisos (objetivo 4 de la tesina: latencia < 2 s)."""
import db
from test_regressions import Actor, app, post  # noqa: F401


def test_since_returns_only_new_messages_and_marks_read(app):  # noqa: F811
    seller, buyer = Actor(app, "v@edu.uaa.mx"), Actor(app, "c@edu.uaa.mx")
    pid = post(app, seller)
    r = buyer.call("POST", "/api/messages", json={"post_id": pid, "receiver_id": seller.id, "content": "Hola"})
    first = r.json["message"]
    assert r.status_code == 201 and first["content"] == "Hola" and first["sender_id"] == buyer.id

    p = seller.client.get("/api/pulse").json
    assert p["unread_messages"] == 1 and p["last_message_id"] == first["id"]
    assert p["latest_message"]["name"] == "Usuario Prueba"

    got = seller.client.get(f"/api/threads/{pid}/{buyer.id}/since?after=0").json
    assert [m["content"] for m in got["messages"]] == ["Hola"]
    assert seller.client.get("/api/pulse").json["unread_messages"] == 0
    # El comprador ve que ya se leyó.
    assert buyer.client.get(f"/api/threads/{pid}/{seller.id}/since?after={first['id']}").json["seen_up_to"] == first["id"]

    seller.call("POST", "/api/messages", json={"post_id": pid, "receiver_id": buyer.id, "content": "Sí, sigue"})
    got = buyer.client.get(f"/api/threads/{pid}/{seller.id}/since?after={first['id']}").json
    assert [m["content"] for m in got["messages"]] == ["Sí, sigue"]


def test_since_never_leaks_other_conversations(app):  # noqa: F811
    seller, buyer, intruder = Actor(app, "s1@edu.uaa.mx"), Actor(app, "b1@edu.uaa.mx"), Actor(app, "x1@edu.uaa.mx")
    pid = post(app, seller)
    buyer.call("POST", "/api/messages", json={"post_id": pid, "receiver_id": seller.id, "content": "privado"})
    assert intruder.client.get(f"/api/threads/{pid}/{seller.id}/since?after=0").json["messages"] == []
    assert intruder.client.get(f"/api/threads/{pid}/{buyer.id}/since?after=0").json["messages"] == []
    assert intruder.client.get("/api/pulse").json["unread_messages"] == 0
    assert app.test_client().get("/api/pulse").status_code == 401
    assert seller.client.get(f"/api/threads/{pid}/{buyer.id}/since?after=abc").status_code == 400


def test_pulse_reports_new_notifications(app):  # noqa: F811
    u = Actor(app, "n@edu.uaa.mx")
    with app.app_context():
        from security import notify
        notify(db.get_db(), u.id, "Llegó algo de tu lista de deseos", "#/wishlist")
    p = u.client.get("/api/pulse").json
    assert p["unread_notifications"] == 1 and p["latest_notification"]["link"] == "#/wishlist"
