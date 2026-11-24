"""Cuenta de administración inicial y archivo .env."""
import os


import accounts
import config
import db
import envfile
from test_regressions import app  # noqa: F401


def test_admin_account_is_created_and_can_log_in(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "ADMIN_EMAIL", "jefa@edu.uaa.mx")
    monkeypatch.setattr(config, "ADMINS", {"jefa@edu.uaa.mx"})
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "EcoGallo2026")
    with app.app_context():
        assert accounts.bootstrap_admin() == "jefa@edu.uaa.mx"
        assert accounts.bootstrap_admin() is None          # ya tiene contraseña: no la toca
    c = app.test_client()
    r = c.post("/api/auth/login", json={"email": "jefa@edu.uaa.mx", "password": "EcoGallo2026"})
    assert r.status_code == 200, r.json
    me = c.get("/api/me").json
    assert me["user"]["role"] == "admin" and me["needs_profile"] is False and me["needs_terms"] is False


def test_production_never_overwrites_existing_password(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "ADMIN_EMAIL", "otro@edu.uaa.mx")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "EcoGallo2026")
    monkeypatch.setattr(config, "DEV", False)
    with app.app_context():
        db.get_db().execute("INSERT INTO users(email,password_hash,created_at) VALUES(?,?,?)",
                            ("otro@edu.uaa.mx", "hash-propio", db.now()))
        accounts.bootstrap_admin()
        assert db.get_db().execute("SELECT password_hash FROM users WHERE email='otro@edu.uaa.mx'").fetchone()[0] == "hash-propio"


def test_dev_repairs_admin_from_older_database(app, monkeypatch):  # noqa: F811
    """Base de una versión anterior: la cuenta 'admin' entró con código, sin perfil y con otra contraseña."""
    from security import hash_password
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@edu.uaa.mx")
    monkeypatch.setattr(config, "ADMINS", {"admin@edu.uaa.mx"})
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "EcoGallo2026")
    monkeypatch.setattr(config, "DEV", True)
    with app.app_context():
        db.get_db().execute("INSERT INTO users(email,name,password_hash,created_at) VALUES(?,?,?,?)",
                            ("admin@edu.uaa.mx", "admin", hash_password("otra-clave-9"), db.now()))
        assert accounts.bootstrap_admin() == "admin@edu.uaa.mx"
        assert accounts.bootstrap_admin() is None           # ya quedó bien: no vuelve a tocarla
        u = db.get_db().execute("SELECT * FROM users WHERE email='admin@edu.uaa.mx'").fetchone()
        assert u["name"] == accounts.ADMIN_NAME and u["carrera"] and u["centro"] and u["role"] == "admin"
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": "admin@edu.uaa.mx", "password": "EcoGallo2026"}).status_code == 200


def test_production_rejects_demo_admin_password(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    env = dict(os.environ)
    env.update(ECOGALLO_ENV="production", ECOGALLO_DEV="0", ECOGALLO_SEED="0", ECOGALLO_SECURE="1",
               ECOGALLO_PUBLIC_URL="https://market.example", ECOGALLO_SMTP_HOST="smtp.example",
               ECOGALLO_SECRET="test-only-persistent-secret-at-least-32-chars",
               ECOGALLO_PRIVACY_EMAIL="privacidad@market.example", ECOGALLO_DATA=str(tmp_path),
               ECOGALLO_BACKUP_ENABLED="0", ECOGALLO_RECONCILE_ENABLED="0", PAYMENT_PROVIDER="disabled",
               ECOGALLO_ADMINS="admin@edu.uaa.mx", ECOGALLO_ADMIN_PASSWORD="EcoGallo2026", ECOGALLO_NO_DOTENV="1")
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import webapp"], env=env, capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parent.parent, timeout=20)
    assert r.returncode != 0 and "ADMIN_PASSWORD" in r.stderr


def test_envfile_fills_missing_values_only(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# comentario\nEG_TEST_A=desde-archivo\nEG_TEST_B=\nexport EG_TEST_C=\"con comillas\"\nEG_TEST_D=archivo\n")
    monkeypatch.setenv("EG_TEST_D", "proceso")
    monkeypatch.setattr(envfile, "_loaded", False)
    monkeypatch.setattr(envfile, "sys", type("S", (), {"modules": {}})())
    envfile.load(f)
    try:
        assert os.environ["EG_TEST_A"] == "desde-archivo"
        assert "EG_TEST_B" not in os.environ
        assert os.environ["EG_TEST_C"] == "con comillas"
        assert os.environ["EG_TEST_D"] == "proceso"
    finally:
        for k in ("EG_TEST_A", "EG_TEST_C"):
            os.environ.pop(k, None)
