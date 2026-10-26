"""SQLite sin ORM: una conexión por petición, transacciones explícitas."""
import contextlib
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
  avatar TEXT NOT NULL DEFAULT ''                   -- nombre de archivo en uploads/
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

CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

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
  dispute_reason TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_orders_buyer ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS ix_orders_seller ON orders(seller_id);
-- Solo una orden "viva" por publicación.
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_live_post ON orders(post_id)
  WHERE status IN ('HELD','DELIVERED','DISPUTED');

CREATE TABLE IF NOT EXISTS order_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  actor_id INTEGER,
  event TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL
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

CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  link TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  read_at INTEGER
);

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


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
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
    have = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
    for col, ddl in _USER_MIGRATIONS.items():
        if col not in have:
            con.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
    for old, new in _CENTRO_RENAMES.items():
        con.execute("UPDATE posts SET centro=? WHERE centro=?", (new, old))
        con.execute("UPDATE users SET centro=? WHERE centro=?", (new, old))
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
