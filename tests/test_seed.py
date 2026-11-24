"""Datos de demostración: cuentas con las que se puede entrar, publicaciones y escenas de compra/mensajes."""
import config
import db
import seed
from test_regressions import app  # noqa: F401


def test_seed_creates_loginable_accounts_and_scenes_once(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DEV", True)
    monkeypatch.setattr(config, "PRODUCTION", False)
    with app.app_context():
        # Base de una versión anterior: vendedora demo con correo @demo.invalid y una publicación suya.
        con = db.get_db()
        con.execute("INSERT INTO users(email,name,created_at) VALUES('demo1@demo.invalid','Mariana Torres',?)", (db.now(),))
        uid = con.execute("SELECT id FROM users WHERE email='demo1@demo.invalid'").fetchone()[0]
        con.execute("""INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,condition,created_at)
                       VALUES(?, 'Libro de Cálculo Vectorial','x','Libros','General','venta',25000,'Usado',?)""", (uid, db.now()))
        seed.seed()
        seed.seed()     # repetir no duplica nada
        con = db.get_db()
        assert con.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()[0] == "al900101@edu.uaa.mx"
        assert con.execute("SELECT COUNT(*) FROM posts WHERE title='Libro de Cálculo Vectorial'").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == len(seed.POSTS)
        states = sorted(r[0] for r in con.execute("SELECT status FROM orders"))
        assert states == ["CASH_PENDING", "DELIVERED", "HELD", "RELEASED", "RELEASED"]
        assert con.execute("SELECT COUNT(*) FROM messages").fetchone()[0] >= 9
    for email in ("al900101@edu.uaa.mx", "al900108@edu.uaa.mx"):
        c = app.test_client()
        r = c.post("/api/auth/login", json={"email": email, "password": seed.DEMO_PASSWORD})
        assert r.status_code == 200, r.json
        assert r.json["needs_profile"] is False and r.json["needs_terms"] is False


def test_seed_never_runs_in_production(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "PRODUCTION", True)
    with app.app_context():
        seed.seed()
        assert db.get_db().execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0
