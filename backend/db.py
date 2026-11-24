"""SQLite sin ORM: una conexión por petición, transacciones explícitas."""
import contextlib
import math
import sqlite3
import time

from flask import g

from config import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  carrera TEXT NOT NULL DEFAULT '',
  centro TEXT NOT NULL DEFAULT 'General',
  role TEXT NOT NULL DEFAULT 'user',          -- user | admin
  suspended INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  password_hash TEXT NOT NULL DEFAULT '',
  failed_logins INTEGER NOT NULL DEFAULT 0,
  locked_until INTEGER NOT NULL DEFAULT 0,
  kind TEXT NOT NULL DEFAULT 'estudiante',          -- estudiante | egresado
  email_verified INTEGER NOT NULL DEFAULT 1,
  verif_status TEXT NOT NULL DEFAULT 'approved',    -- approved | pending | rejected (solo egresados)
  bio TEXT NOT NULL DEFAULT '',
  avatar TEXT NOT NULL DEFAULT '',
  deleted_at INTEGER NOT NULL DEFAULT 0,
  stripe_account_id TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS login_codes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  used INTEGER NOT NULL DEFAULT 0,
  ip TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_codes_email ON login_codes(email, created_at);

CREATE TABLE IF NOT EXISTS phone_codes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  phone TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  used INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_phone_codes_user ON phone_codes(user_id, created_at);

CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  reset_until INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS auth_challenges(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at INTEGER NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  used INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_auth_challenges_user
  ON auth_challenges(user_id, expires_at);

-- Inicio de sesión con Microsoft: state de un solo uso, nonce y verificador PKCE (10 min).
CREATE TABLE IF NOT EXISTS oauth_states(
  state_hash TEXT PRIMARY KEY,
  nonce TEXT NOT NULL,
  verifier TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS totp_recovery_codes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_hash TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_totp_recovery_user
  ON totp_recovery_codes(user_id, used);

CREATE TABLE IF NOT EXISTS posts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  category TEXT NOT NULL,
  centro TEXT NOT NULL DEFAULT 'General',
  tipo TEXT NOT NULL DEFAULT 'venta',          -- venta | trueque | donacion
  price_cents INTEGER NOT NULL DEFAULT 0,
  condition TEXT NOT NULL DEFAULT 'Usado',
  status TEXT NOT NULL DEFAULT 'active',       -- active | paused | reserved | sold | removed
  views_count INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_posts_status ON posts(status, created_at);

CREATE TABLE IF NOT EXISTS post_images(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0
);

-- Pago retenido (escrow). Estados:
-- HELD (pagado y retenido) -> DELIVERED (vendedor dice que entregó, sigue retenido)
-- -> RELEASED (comprador confirmó: se libera al vendedor)
-- HELD/DELIVERED -> DISPUTED (comprador reporta) -> RELEASED | REFUNDED (admin)
-- HELD/DELIVERED -> REFUNDED (vendedor devuelve)
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL REFERENCES posts(id),
  buyer_id INTEGER NOT NULL REFERENCES users(id),
  seller_id INTEGER NOT NULL REFERENCES users(id),
  amount_cents INTEGER NOT NULL,
  status TEXT NOT NULL,
  payment_ref TEXT NOT NULL DEFAULT '',
  stripe_session_id TEXT NOT NULL DEFAULT '',
  stripe_payment_intent_id TEXT NOT NULL DEFAULT '',
  stripe_charge_id TEXT NOT NULL DEFAULT '',
  stripe_transfer_id TEXT NOT NULL DEFAULT '',
  dispute_reason TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_orders_buyer ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS ix_orders_seller ON orders(seller_id);
-- Solo una orden "viva" por publicación.
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_live_post ON orders(post_id)
  WHERE status IN (
    'PENDING_PAYMENT',
    'HELD',
    'DELIVERED',
    'DISPUTED',
    'RELEASING',
    'REFUNDING', 'PAYMENT_REVIEW'
  );

CREATE TABLE IF NOT EXISTS order_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  actor_id INTEGER,
  event TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS stripe_webhook_events(
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  processed_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet_entries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  order_id INTEGER REFERENCES orders(id),
  amount_cents INTEGER NOT NULL,
  kind TEXT NOT NULL,                          -- release
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL REFERENCES posts(id),
  sender_id INTEGER NOT NULL REFERENCES users(id),
  receiver_id INTEGER NOT NULL REFERENCES users(id),
  content TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  read_at INTEGER
);
CREATE INDEX IF NOT EXISTS ix_msg_pair ON messages(post_id, sender_id, receiver_id);
CREATE INDEX IF NOT EXISTS ix_msg_unread ON messages(receiver_id, read_at);

CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  link TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  read_at INTEGER
);
CREATE INDEX IF NOT EXISTS ix_notes_user ON notifications(user_id, read_at);

-- Documentos (kárdex / título) que suben los egresados para que un admin los revise.
-- El archivo vive fuera de /uploads y se borra al resolver la solicitud.
CREATE TABLE IF NOT EXISTS alumni_verifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL,                      -- kardex | titulo
  filename TEXT NOT NULL DEFAULT '',           -- vacío cuando ya se borró
  status TEXT NOT NULL DEFAULT 'pending',      -- pending | approved | rejected
  note TEXT NOT NULL DEFAULT '',
  reviewer_id INTEGER REFERENCES users(id),
  created_at INTEGER NOT NULL,
  reviewed_at INTEGER
);
CREATE INDEX IF NOT EXISTS ix_verif_status ON alumni_verifications(status, created_at);

-- Lista de deseos: avisa al usuario cuando alguien publica algo que coincide.
CREATE TABLE IF NOT EXISTS wishlist(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  term TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT '',           -- vacío = cualquiera
  centro TEXT NOT NULL DEFAULT '',             -- vacío = cualquiera
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_wishlist_user ON wishlist(user_id);

-- Artículos guardados / favoritos (seguimiento de interés y alertas de precio)
CREATE TABLE IF NOT EXISTS favorites(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  UNIQUE(user_id, post_id)
);
CREATE INDEX IF NOT EXISTS ix_fav_user ON favorites(user_id);
CREATE INDEX IF NOT EXISTS ix_fav_post ON favorites(post_id);

-- Carrito (US-04): artículos en venta que el usuario piensa pagar juntos.
CREATE TABLE IF NOT EXISTS cart_items(
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  added_at INTEGER NOT NULL,
  PRIMARY KEY(user_id, post_id)
);

CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reporter_id INTEGER NOT NULL REFERENCES users(id),
  target_type TEXT NOT NULL,                   -- post | user
  target_id INTEGER NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',         -- open | resolved
  created_at INTEGER NOT NULL
);
"""


def distance_km(lat1, lng1, lat2, lng2):
    """Distancia en km sobre la esfera terrestre (haversine). None si falta alguna coordenada."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.create_function("distance_km", 4, distance_km, deterministic=True)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


# Columnas añadidas después de la primera versión (bases ya existentes).
_USER_MIGRATIONS = {
    "password_hash": "TEXT NOT NULL DEFAULT ''",
    "failed_logins": "INTEGER NOT NULL DEFAULT 0",
    "locked_until": "INTEGER NOT NULL DEFAULT 0",
    "kind": "TEXT NOT NULL DEFAULT 'estudiante'",
    "email_verified": "INTEGER NOT NULL DEFAULT 1",
    "verif_status": "TEXT NOT NULL DEFAULT 'approved'",
    "bio": "TEXT NOT NULL DEFAULT ''",
    "avatar": "TEXT NOT NULL DEFAULT ''",
    "deleted_at": "INTEGER NOT NULL DEFAULT 0",
    "totp_enabled": "INTEGER NOT NULL DEFAULT 0",
    "totp_secret": "TEXT NOT NULL DEFAULT ''",
    "totp_pending_secret": "TEXT NOT NULL DEFAULT ''",
    "totp_pending_expires_at": "INTEGER NOT NULL DEFAULT 0",
    "totp_last_counter": "INTEGER NOT NULL DEFAULT -1",
    "stripe_account_id": "TEXT NOT NULL DEFAULT ''",
    "terms_version": "TEXT NOT NULL DEFAULT ''",
    "terms_accepted_at": "INTEGER NOT NULL DEFAULT 0",
    # Pagos con tarjeta: teléfono confirmado por SMS y cuenta para recibir (solo últimos 4 dígitos).
    "phone": "TEXT NOT NULL DEFAULT ''",
    "phone_verified_at": "INTEGER NOT NULL DEFAULT 0",
    "payout_kind": "TEXT NOT NULL DEFAULT ''",          # '' | tarjeta | clabe
    "payout_last4": "TEXT NOT NULL DEFAULT ''",
    "payout_holder": "TEXT NOT NULL DEFAULT ''",
    "payout_updated_at": "INTEGER NOT NULL DEFAULT 0",
}

_ORDER_MIGRATIONS = {
    "stripe_session_id": "TEXT NOT NULL DEFAULT ''",
    "stripe_payment_intent_id": "TEXT NOT NULL DEFAULT ''",
    "stripe_charge_id": "TEXT NOT NULL DEFAULT ''",
    "stripe_transfer_id": "TEXT NOT NULL DEFAULT ''",
    "stripe_refund_id": "TEXT NOT NULL DEFAULT ''",
    "checkout_url": "TEXT NOT NULL DEFAULT ''",
    "payment_provider": "TEXT NOT NULL DEFAULT 'simulado'",
    "payment_operation_at": "INTEGER NOT NULL DEFAULT 0",
    "operation_actor_id": "INTEGER",
    "operation_note": "TEXT NOT NULL DEFAULT ''",
    "checkout_group": "TEXT NOT NULL DEFAULT ''",        # órdenes pagadas juntas (carrito / Mercado Pago)
    "provider_payment_id": "TEXT NOT NULL DEFAULT ''",   # id del pago en Mercado Pago
    "payout_status": "TEXT NOT NULL DEFAULT ''",         # '' | pending | paid (liquidación manual al vendedor)
    "payout_ref": "TEXT NOT NULL DEFAULT ''",
    "payout_at": "INTEGER NOT NULL DEFAULT 0",
    "card_brand": "TEXT NOT NULL DEFAULT ''",          # tarjeta del comprador (solo marca y últimos 4)
    "card_last4": "TEXT NOT NULL DEFAULT ''",
}

# Nombres anteriores de centros -> nombres del catálogo oficial (bases ya existentes).
_CENTRO_RENAMES = {
    "Artes y Humanidades": "Centro de las Artes y la Cultura",
    "Ciencias Agropecuarias": "Centro de Ciencias Agropecuarias",
    "Ciencias Básicas": "Centro de Ciencias Básicas",
    "Ciencias Biomédicas": "Centro de Ciencias de la Salud",
    "Ciencias de la Ingeniería": "Centro de Ciencias de la Ingeniería",
    "Ciencias del Diseño y de la Construcción": "Centro de Ciencias del Diseño y de la Construcción",
    "Ciencias Económicas y Administrativas": "Centro de Ciencias Económicas y Administrativas",
    "Ciencias de la Salud": "Centro de Ciencias de la Salud",
    "Ciencias Sociales y Humanidades": "Centro de Ciencias Sociales y Humanidades",
}


def init_db():
    con = connect()
    con.executescript(SCHEMA)

    con.execute("DROP INDEX IF EXISTS ux_orders_live_post")
    con.execute("""
        CREATE UNIQUE INDEX ux_orders_live_post ON orders(post_id)
        WHERE status IN (
            'CASH_PENDING',
            'PENDING_PAYMENT',
            'HELD',
            'DELIVERED',
            'DISPUTED',
            'RELEASING',
            'REFUNDING', 'PAYMENT_REVIEW'
        )
    """)

    if "reset_until" not in {r["name"] for r in con.execute("PRAGMA table_info(sessions)")}:
        con.execute("ALTER TABLE sessions ADD COLUMN reset_until INTEGER NOT NULL DEFAULT 0")
    if "email_authenticated" not in {r["name"] for r in con.execute("PRAGMA table_info(auth_challenges)")}:
        con.execute("ALTER TABLE auth_challenges ADD COLUMN email_authenticated INTEGER NOT NULL DEFAULT 0")

    # Migraciones de usuarios.
    have_users = {
        r["name"] for r in con.execute("PRAGMA table_info(users)")
    }

    for col, ddl in _USER_MIGRATIONS.items():
        if col not in have_users:
            con.execute(
                f"ALTER TABLE users ADD COLUMN {col} {ddl}"
            )

    # Migraciones de órdenes y pagos Stripe.
    have_orders = {
        r["name"] for r in con.execute("PRAGMA table_info(orders)")
    }

    for col, ddl in _ORDER_MIGRATIONS.items():
        if col not in have_orders:
            con.execute(
                f"ALTER TABLE orders ADD COLUMN {col} {ddl}"
            )

    con.execute("UPDATE orders SET payment_provider='stripe' WHERE payment_provider NOT IN ('mercadopago','efectivo') AND "
                "(stripe_session_id!='' OR payment_ref LIKE 'cs_%' OR status='PENDING_PAYMENT')")
    con.execute("CREATE INDEX IF NOT EXISTS ix_orders_group ON orders(checkout_group)")

    # Migración de publicaciones.
    have_posts = {
        r["name"] for r in con.execute("PRAGMA table_info(posts)")
    }

    if "views_count" not in have_posts:
        con.execute(
            "ALTER TABLE posts ADD COLUMN views_count "
            "INTEGER NOT NULL DEFAULT 0"
        )

    for col, ddl in (("meet_place", "TEXT NOT NULL DEFAULT ''"), ("meet_lat", "REAL"), ("meet_lng", "REAL"),
                     ("new_price_cents", "INTEGER NOT NULL DEFAULT 0"),      # precio nuevo declarado (opcional)
                     ("closed_at", "INTEGER NOT NULL DEFAULT 0"),
                     ("featured_until", "INTEGER NOT NULL DEFAULT 0"),       # destacada hasta (US-14)
                     ("featured_at", "INTEGER NOT NULL DEFAULT 0")):           # cuándo se reutilizó (vendido/entregado)
        if col not in have_posts:
            con.execute(f"ALTER TABLE posts ADD COLUMN {col} {ddl}")

    if "approved_price_cents" not in have_posts:
        con.execute("ALTER TABLE posts ADD COLUMN approved_price_cents INTEGER NOT NULL DEFAULT -1")

    # Actualizar nombres anteriores de centros.
    for old, new in _CENTRO_RENAMES.items():
        con.execute(
            "UPDATE posts SET centro=? WHERE centro=?",
            (new, old)
        )
        con.execute(
            "UPDATE users SET centro=? WHERE centro=?",
            (new, old)
        )

    con.close()


@contextlib.contextmanager
def tx(db: sqlite3.Connection):
    """Transacción con bloqueo de escritura inmediato (evita carreras en el escrow)."""
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except BaseException:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


def now() -> int:
    return int(time.time())


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]
