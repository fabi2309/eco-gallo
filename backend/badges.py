"""Insignias de confianza que se muestran junto al nombre de una persona.

- «Egresado verificado»: cuenta de egresado cuyo kárdex/título aprobó un administrador.
- «Vendedor verificado»: identidad institucional comprobada (correo UAA confirmado, o egresado
  aprobado) y al menos `VERIFIED_SELLER_MIN_DEALS` operaciones concluidas (venta liberada o
  trueque/donación entregado). Así la insignia se gana con historial, no solo con registrarse.
"""
import config
from security import is_institutional

# Columnas para añadir a cualquier SELECT que tenga la tabla `users` con alias `u`.
BADGE_COLS = """u.kind AS a_kind, u.verif_status AS a_verif, u.email AS a_email, u.email_verified AS a_ev,
  (SELECT COUNT(*) FROM orders o WHERE o.seller_id=u.id AND o.status='RELEASED')
  + (SELECT COUNT(*) FROM posts q WHERE q.author_id=u.id AND q.status='sold' AND q.tipo!='venta') AS a_deals"""


def compute(row) -> dict:
    """`row` trae las columnas de BADGE_COLS (dict o sqlite3.Row)."""
    approved_alumni = row["a_kind"] == "egresado" and row["a_verif"] == "approved" and bool(row["a_ev"])
    identity = bool(row["a_ev"]) and (is_institutional(row["a_email"]) or approved_alumni)
    deals = int(row["a_deals"] or 0)
    return {"egresado": approved_alumni, "seller": identity and deals >= config.VERIFIED_SELLER_MIN_DEALS,
            "deals": deals}


def user_badges(db, user_id: int) -> dict:
    row = db.execute(f"SELECT {BADGE_COLS} FROM users u WHERE u.id=?", (user_id,)).fetchone()  # nosec B608 - BADGE_COLS es constante
    return compute(row) if row else {"egresado": False, "seller": False, "deals": 0}
