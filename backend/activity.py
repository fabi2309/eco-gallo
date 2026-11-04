"""Historial de actividades del usuario: publicaciones, compras, ventas y mensajes (paginado)."""
from flask import Blueprint, g, jsonify, request

from db import get_db, rows
from security import api_error, login_required

bp = Blueprint("activity", __name__, url_prefix="/api")

PER_PAGE = 10
KINDS = ("todo", "publicaciones", "compras", "ventas", "mensajes")

# Todas las ramas devuelven las mismas 7 columnas: kind, ts, ref, ref2, title, detail, amount
_BRANCHES = {
    "publicaciones": ("""SELECT 'publicacion' AS kind, p.created_at AS ts, p.id AS ref, 0 AS ref2, p.title AS title,
                                p.status AS detail, p.price_cents AS amount
                         FROM posts p WHERE p.author_id=?""", 1),
    "compras": ("""SELECT 'compra' AS kind, o.created_at AS ts, o.id AS ref, 0 AS ref2,
                          (SELECT title FROM posts WHERE id=o.post_id) AS title,
                          o.status AS detail, o.amount_cents AS amount FROM orders o WHERE o.buyer_id=?""", 1),
    "ventas": ("""SELECT 'venta' AS kind, o.created_at AS ts, o.id AS ref, 0 AS ref2,
                         (SELECT title FROM posts WHERE id=o.post_id) AS title,
                         o.status AS detail, o.amount_cents AS amount FROM orders o WHERE o.seller_id=?""", 1),
    "mensajes": ("""SELECT CASE WHEN m.sender_id=? THEN 'mensaje_enviado' ELSE 'mensaje_recibido' END AS kind,
                           m.created_at AS ts, m.post_id AS ref,
                           CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END AS ref2,
                           substr(m.content, 1, 90) AS title,
                           (SELECT title FROM posts WHERE id=m.post_id) AS detail, 0 AS amount
                    FROM messages m WHERE m.sender_id=? OR m.receiver_id=?""", 4),
}


def _link(kind: str, ref: int, ref2: int) -> str:
    if kind == "publicacion":
        return f"#/post/{ref}"
    if kind in ("compra", "venta"):
        return f"#/order/{ref}"
    return f"#/chat/{ref}/{ref2}"


@bp.get("/activity")
@login_required
def activity():
    kind = request.args.get("kind", "todo")
    if kind not in KINDS:
        return api_error("Tipo de actividad no válido.", 400)
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        return api_error("Página no válida.", 400)
    uid = g.user["id"]
    chosen = list(_BRANCHES) if kind == "todo" else [kind]
    sql = " UNION ALL ".join(_BRANCHES[k][0] for k in chosen)
    args = [uid] * sum(_BRANCHES[k][1] for k in chosen)

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) c FROM ({sql})", args).fetchone()["c"]  # nosec B608 - SQL fijo (_BRANCHES); valores parametrizados
    pages = max(1, -(-total // PER_PAGE))
    page = min(page, pages)
    items = rows(db.execute(
        f"SELECT * FROM ({sql}) ORDER BY ts DESC, ref DESC LIMIT ? OFFSET ?",  # nosec B608 - SQL fijo (_BRANCHES); valores parametrizados
        [*args, PER_PAGE, (page - 1) * PER_PAGE]))
    for it in items:
        it["link"] = _link(it["kind"], it["ref"], it["ref2"])
        it["title"] = it["title"] or "(publicación eliminada)"
    return jsonify({"ok": True, "items": items, "page": page, "pages": pages, "total": total, "per_page": PER_PAGE})
