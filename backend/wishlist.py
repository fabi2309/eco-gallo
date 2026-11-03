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


def get_matching_wishlist_users(db, post_id: int, author_id: int, title: str, description: str, category: str, centro: str) -> set[int]:
    """Obtiene el conjunto de user_ids con deseos activos que coinciden con el producto."""
    haystack = _fold(f"{title} {description}")
    matched: set[int] = set()
    for w in rows(db.execute(
            """SELECT w.* FROM wishlist w JOIN users u ON u.id=w.user_id
               WHERE w.user_id != ? AND u.suspended=0""", (author_id,))):
        if w["user_id"] in matched:
            continue
        if w["category"] and w["category"] != category:
            continue
        if w["centro"] and w["centro"] != centro:
            continue
        if _fold(w["term"]) not in haystack:
            continue
        matched.add(w["user_id"])
    return matched


def notify_matches(db, post_id: int, author_id: int, title: str, description: str, category: str, centro: str):
    """Avisa (una sola vez por persona) a quienes tengan un deseo que coincida con la publicación nueva."""
    matched = get_matching_wishlist_users(db, post_id, author_id, title, description, category, centro)
    for uid in matched:
        notify(db, uid, f"¡Salió algo de tu lista de deseos! «{title}»", f"#/post/{post_id}")


def notify_price_drop(db, post_id: int, author_id: int, title: str, category: str, centro: str,
                      old_price_cents: int, new_price_cents: int, description: str = "") -> int:
    """Notifica a usuarios interesados (artículo guardado, lista de deseos o chat activo) cuando baja de precio."""
    old_p = f"${old_price_cents / 100:.2f}"
    new_p = f"${new_price_cents / 100:.2f}"
    msg = f"¡Bajó de precio! «{title}» ahora cuesta {new_p} (antes {old_p})."
    link = f"#/post/{post_id}"

    # 1. Usuarios que guardaron el artículo en favoritos
    fav_users = {r[0] for r in db.execute(
        "SELECT user_id FROM favorites WHERE post_id=? AND user_id != ?", (post_id, author_id)
    ).fetchall()}

    # 2. Usuarios con el artículo en su lista de deseos
    wish_users = get_matching_wishlist_users(db, post_id, author_id, title, description, category, centro)

    # 3. Usuarios que iniciaron conversación por chat sobre este artículo
    chat_users = {r[0] for r in db.execute(
        "SELECT DISTINCT sender_id FROM messages WHERE post_id=? AND sender_id != ?", (post_id, author_id)
    ).fetchall()}

    target_users = fav_users.union(wish_users).union(chat_users)
    count = 0
    for uid in target_users:
        notify(db, uid, msg, link)
        count += 1
    return count


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


# ------------------------------------------------------------- Favoritos / Artículos guardados
@bp.post("/posts/<int:pid>/favorite")
@login_required
def toggle_favorite(pid):
    db = get_db()
    post = db.execute("SELECT id, author_id, status FROM posts WHERE id=?", (pid,)).fetchone()
    if not post or post["status"] == "removed":
        return api_error("Publicación no encontrada.", 404)
    uid = g.user["id"]
    fav = db.execute("SELECT id FROM favorites WHERE user_id=? AND post_id=?", (uid, pid)).fetchone()
    if fav:
        db.execute("DELETE FROM favorites WHERE user_id=? AND post_id=?", (uid, pid))
        favorited = False
    else:
        db.execute("INSERT INTO favorites(user_id, post_id, created_at) VALUES(?,?,?)", (uid, pid, now()))
        favorited = True

    count = db.execute("SELECT COUNT(*) c FROM favorites WHERE post_id=?", (pid,)).fetchone()["c"]
    return jsonify({"ok": True, "favorited": favorited, "favorites_count": count})


@bp.get("/favorites")
@login_required
def list_favorites():
    db = get_db()
    fav_ids = [r[0] for r in db.execute(
        "SELECT post_id FROM favorites WHERE user_id=? ORDER BY id DESC", (g.user["id"],)
    ).fetchall()]
    return jsonify({"ok": True, "post_ids": fav_ids})
