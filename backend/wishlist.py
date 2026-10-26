"""Lista de deseos: el usuario pide aviso y se le notifica cuando alguien publica algo que coincide."""
import unicodedata

from flask import Blueprint, g, jsonify, request

import config
from db import get_db, now, rows
from security import api_error, clean_text, login_required, notify

bp = Blueprint("wishlist", __name__, url_prefix="/api")


def _fold(text: str) -> str:
    """Minúsculas y sin acentos, para que «calculo» encuentre «Cálculo»."""
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")


def notify_matches(db, post_id: int, author_id: int, title: str, description: str, category: str, centro: str):
    """Avisa (una sola vez por persona) a quienes tengan un deseo que coincida con la publicación nueva."""
    haystack = _fold(f"{title} {description}")
    seen: set[int] = set()
    for w in rows(db.execute(
            """SELECT w.* FROM wishlist w JOIN users u ON u.id=w.user_id
               WHERE w.user_id != ? AND u.suspended=0""", (author_id,))):
        if w["user_id"] in seen:
            continue
        if w["category"] and w["category"] != category:
            continue
        if w["centro"] and w["centro"] != centro:
            continue
        if _fold(w["term"]) not in haystack:
            continue
        seen.add(w["user_id"])
        notify(db, w["user_id"], f"¡Salió algo de tu lista de deseos! «{title}» (buscabas «{w['term']}»)",
               f"#/post/{post_id}")


@bp.get("/wishlist")
@login_required
def list_wishlist():
    items = rows(get_db().execute(
        "SELECT id, term, category, centro, created_at FROM wishlist WHERE user_id=? ORDER BY id DESC", (g.user["id"],)))
    return jsonify({"ok": True, "items": items, "max": config.WISHLIST_MAX})


@bp.post("/wishlist")
@login_required
def add_wishlist():
    data = request.get_json(silent=True) or {}
    term = clean_text(data.get("term"), 60)
    category = data.get("category") or ""
    centro = data.get("centro") or ""
    if not term or len(term) < 2:
        return api_error("Escribe qué estás buscando (mínimo 2 letras).", 400)
    if category and category not in config.CATEGORIES:
        return api_error("Categoría no válida.", 400)
    if centro and centro not in config.CENTROS:
        return api_error("Centro no válido.", 400)
    db = get_db()
    mine = rows(db.execute("SELECT term, category, centro FROM wishlist WHERE user_id=?", (g.user["id"],)))
    if any(_fold(m["term"]) == _fold(term) and m["category"] == category and m["centro"] == centro for m in mine):
        return api_error("Ya tienes ese deseo en tu lista.", 409)
    if len(mine) >= config.WISHLIST_MAX:
        return api_error(f"Tu lista admite hasta {config.WISHLIST_MAX} deseos. Quita alguno para agregar otro.", 409)
    cur = db.execute("INSERT INTO wishlist(user_id,term,category,centro,created_at) VALUES(?,?,?,?,?)",
                     (g.user["id"], term, category, centro, now()))
    return jsonify({"ok": True, "id": cur.lastrowid}), 201


@bp.delete("/wishlist/<int:wid>")
@login_required
def delete_wishlist(wid):
    cur = get_db().execute("DELETE FROM wishlist WHERE id=? AND user_id=?", (wid, g.user["id"]))
    if cur.rowcount != 1:
        return api_error("No encontrado.", 404)
    return jsonify({"ok": True})
