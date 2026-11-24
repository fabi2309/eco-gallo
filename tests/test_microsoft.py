"""Entrar con la cuenta Microsoft de la UAA (US-01). El canje del código se simula: no hay red."""
import base64
import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest

import config
import db
import microsoft
from test_regressions import app  # noqa: F401

TENANT = "11111111-2222-3333-4444-555555555555"
CLIENT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def id_token(**claims):
    seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{seg({'alg': 'RS256'})}.{seg(claims)}.firma"


@pytest.fixture
def ms(app, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "MS_CLIENT_ID", CLIENT)
    monkeypatch.setattr(config, "MS_CLIENT_SECRET", "secreto")
    monkeypatch.setattr(config, "MS_TENANT", TENANT)
    sent = {}

    def fake_exchange(code, verifier):
        sent["verifier"] = verifier
        return {"id_token": id_token(**sent["claims"])}
    monkeypatch.setattr(microsoft, "exchange_code", fake_exchange)
    return sent


def start(client):
    r = client.get("/api/auth/microsoft/start")
    assert r.status_code == 302
    url = urlsplit(r.headers["Location"])
    assert url.netloc == "login.microsoftonline.com" and url.path.startswith(f"/{TENANT}/")
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert q["code_challenge_method"] == "S256" and q["client_id"] == CLIENT
    return q


def claims(q, **over):
    base = {"aud": CLIENT, "tid": TENANT, "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
            "nonce": q["nonce"], "exp": int(time.time()) + 600, "preferred_username": "AL350114@edu.uaa.mx"}
    base.update(over)
    return base


def test_microsoft_login_creates_session_for_uaa_account(app, ms):  # noqa: F811
    c = app.test_client()
    q = start(c)
    ms["claims"] = claims(q)
    r = c.get(f"/api/auth/microsoft/callback?code=abc&state={q['state']}")
    assert r.status_code == 302 and r.headers["Location"].endswith("/#/")
    me = c.get("/api/me").json
    assert me["user"]["email"] == "al350114@edu.uaa.mx" and me["needs_profile"] is True
    assert me["password_reset_allowed"] is True
    # PKCE: el verificador enviado corresponde al reto publicado.
    import hashlib
    assert microsoft._b64url(hashlib.sha256(ms["verifier"].encode()).digest()) == q["code_challenge"]
    # El state es de un solo uso.
    r = app.test_client().get(f"/api/auth/microsoft/callback?code=abc&state={q['state']}")
    assert "oauth-error/vencido" in r.headers["Location"]


@pytest.mark.parametrize("over", [
    {"tid": "99999999-2222-3333-4444-555555555555"},
    {"iss": "https://login.microsoftonline.com/otro/v2.0"},
    {"aud": "otra-app"},
    {"nonce": "repetido"},
    {"exp": 1000},
    {"preferred_username": "alguien@gmail.com"},
])
def test_microsoft_rejects_foreign_or_tampered_tokens(app, ms, over):  # noqa: F811
    c = app.test_client()
    q = start(c)
    ms["claims"] = claims(q, **over)
    r = c.get(f"/api/auth/microsoft/callback?code=abc&state={q['state']}")
    assert "oauth-error/cuenta-no-uaa" in r.headers["Location"]
    assert c.get("/api/me").json["user"] is None


def test_microsoft_respects_2fa_and_suspension(app, ms):  # noqa: F811
    with app.app_context():
        con = db.get_db()
        con.execute("INSERT INTO users(email,name,carrera,created_at,totp_enabled) VALUES(?,?,?,?,1)",
                    ("al111111@edu.uaa.mx", "Con 2FA", "Ingeniería en Sistemas Computacionales", db.now()))
        con.execute("INSERT INTO users(email,name,carrera,created_at,suspended) VALUES(?,?,?,?,1)",
                    ("al222222@edu.uaa.mx", "Suspendido", "Ingeniería en Sistemas Computacionales", db.now()))
    c = app.test_client()
    q = start(c)
    ms["claims"] = claims(q, preferred_username="al111111@edu.uaa.mx")
    r = c.get(f"/api/auth/microsoft/callback?code=abc&state={q['state']}")
    assert "/#/oauth-totp/" in r.headers["Location"] and c.get("/api/me").json["user"] is None

    q = start(c)
    ms["claims"] = claims(q, preferred_username="al222222@edu.uaa.mx")
    r = c.get(f"/api/auth/microsoft/callback?code=abc&state={q['state']}")
    assert "oauth-error/suspendida" in r.headers["Location"]


def test_microsoft_disabled_without_configuration(app):  # noqa: F811
    assert app.test_client().get("/api/meta").json["microsoft_login"] is False
    r = app.test_client().get("/api/auth/microsoft/start")
    assert "oauth-error/no-configurado" in r.headers["Location"]


def test_tenant_must_be_a_guid(monkeypatch):
    monkeypatch.setattr(config, "MS_CLIENT_ID", CLIENT)
    monkeypatch.setattr(config, "MS_CLIENT_SECRET", "x")
    monkeypatch.setattr(config, "MS_TENANT", "common")
    with pytest.raises(RuntimeError):
        config.validate_runtime()
