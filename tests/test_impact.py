"""Dashboard de impacto (objetivo 5): ahorro = precio nuevo − precio pagado."""
import config
import db
from test_regressions import Actor, app  # noqa: F401


def add(app, author, category, tipo, price, new_price=0):  # noqa: F811
    with app.app_context():
        return db.get_db().execute(
            "INSERT INTO posts(author_id,title,description,category,tipo,price_cents,new_price_cents,status,created_at,closed_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (author.id, "x", "descripción larga", category, tipo, price, new_price, "sold", db.now(), db.now())).lastrowid


def test_savings_use_declared_price_or_category_reference(app):  # noqa: F811
    u = Actor(app, "i@edu.uaa.mx")
    add(app, u, "Libros", "venta", 200_00, 700_00)          # declarado: ahorra 500
    add(app, u, "Apuntes", "donacion", 0)                   # referencia: ahorra 150
    add(app, u, "Libros", "venta", 900_00, 0)               # pagó más que la referencia: 0, nunca negativo
    s = u.client.get("/api/impact").json
    assert s["reused_items"] == 3
    assert s["savings_cents"] == 500_00 + config.NEW_PRICE_EST_CENTS["Apuntes"]
    assert s["declared_share"] == round(500_00 / s["savings_cents"], 3)
    assert s["reused_by_tipo"] == {"venta": 2, "donacion": 1}
    assert s["monthly"][-1]["items"] == 3


def test_new_price_must_not_be_below_price(app):  # noqa: F811
    u = Actor(app, "np@edu.uaa.mx")
    base = {"title": "Libro", "description": "Descripción suficientemente larga", "category": "Libros", "tipo": "venta",
            "price": "300"}
    assert u.call("POST", "/api/posts", data={**base, "new_price": "200"}).status_code == 400
    r = u.call("POST", "/api/posts", data={**base, "new_price": "650"})
    assert r.status_code == 201
    assert u.client.get(f"/api/posts/{r.json['id']}").json["post"]["new_price_cents"] == 650_00


def test_seller_stats_summary(app):  # noqa: F811
    seller, fan = Actor(app, "st@edu.uaa.mx"), Actor(app, "fan@edu.uaa.mx")
    with app.app_context():
        pid = db.get_db().execute(
            "INSERT INTO posts(author_id,title,description,category,tipo,price_cents,status,views_count,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)", (seller.id, "Bata", "Bata talla M", "Uniformes", "donacion", 0, "active", 10, db.now())).lastrowid
    fan.call("POST", "/api/messages", json={"post_id": pid, "receiver_id": seller.id, "content": "¿Sigue?"})
    fan.call("POST", f"/api/posts/{pid}/favorite")
    r = seller.client.get("/api/posts/stats/mine").json
    assert r["totals"]["views"] == 10 and r["totals"]["contacts"] == 1 and r["totals"]["favorites"] == 1
    assert r["posts"][0]["contact_rate"] == 0.1
    assert fan.client.get("/api/posts/stats/mine").json["totals"]["posts"] == 0


def test_feature_post_rules(app, monkeypatch):  # noqa: F811
    seller, other = Actor(app, "dest@edu.uaa.mx"), Actor(app, "otro@edu.uaa.mx")

    def mk(status="active"):
        with app.app_context():
            return db.get_db().execute(
                "INSERT INTO posts(author_id,title,description,category,tipo,price_cents,status,created_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (seller.id, "Libro", "Libro en buen estado", "Libros", "donacion", 0, status, db.now())).lastrowid
    old, newer, pending = mk(), mk(), mk("pending")
    assert other.call("POST", f"/api/posts/{old}/feature").status_code == 404
    assert seller.call("POST", f"/api/posts/{pending}/feature").status_code == 409
    assert seller.call("POST", f"/api/posts/{old}/feature").status_code == 200
    assert seller.call("POST", f"/api/posts/{newer}/feature").status_code == 409     # una a la vez
    ids = [p["id"] for p in other.client.get("/api/posts").json["posts"]]
    assert ids[0] == old                                                              # la destacada va primero
    assert other.client.get(f"/api/posts/{old}").json["post"]["featured"] is True
    with app.app_context():                                                           # termina la destacada
        db.get_db().execute("UPDATE posts SET featured_until=? WHERE id=?", (db.now() - 1, old))
    assert seller.call("POST", f"/api/posts/{old}/feature").status_code == 429       # espera de una semana
    assert seller.call("POST", f"/api/posts/{newer}/feature").status_code == 200
