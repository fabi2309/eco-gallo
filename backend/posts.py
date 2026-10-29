"""Publicaciones, búsqueda y subida de imágenes."""
import re
import uuid
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, jsonify, request

import catalog
import config
from db import get_db, now, rows, tx
from security import api_error, clean_text, login_required
from wishlist import notify_matches

bp = Blueprint("posts", __name__, url_prefix="/api")

_MAGIC = [
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
]


def sniff_image(data: bytes) -> str | None:
    for magic, ext in _MAGIC:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_images(files) -> list[str] | tuple[None, str]:
    saved: list[str] = []
    files = [f for f in files if f and f.filename]
    if len(files) > config.MAX_IMAGES:
        return None, f"Máximo {config.MAX_IMAGES} imágenes."
    for f in files:
        data = f.read(config.MAX_IMAGE_BYTES + 1)
        if len(data) > config.MAX_IMAGE_BYTES:
            return None, "Cada imagen debe pesar menos de 5 MB."
        ext = sniff_image(data)
        if not ext:
            return None, "Solo se permiten imágenes JPG, PNG o WebP."
        name = f"{uuid.uuid4().hex}.{ext}"
        (config.UPLOADS / name).write_bytes(data)
        saved.append(name)
    return saved


def parse_price(raw) -> int | None:
    try:
        value = Decimal(str(raw).replace(",", ".").strip() or "0")
    except InvalidOperation:
        return None
    if value < 0 or value.is_nan() or value.is_infinite():
        return None
    return int((value * 100).to_integral_value())


def serialize(row: dict, images: list[str]) -> dict:
    return {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "category": row["category"], "centro": row["centro"], "tipo": row["tipo"],
        "price_cents": row["price_cents"], "condition": row["condition"],
        "status": row["status"], "created_at": row["created_at"],
        "author": {"id": row["author_id"], "name": row["author_name"],
                   "carrera": row["author_carrera"], "centro": row["author_centro"],
                   "bio": row["author_bio"],
                   "avatar": f"/uploads/{row['author_avatar']}" if row["author_avatar"] else ""},
        "images": [f"/uploads/{n}" for n in images],
    }


BASE_SELECT = """SELECT p.*, u.name AS author_name, u.carrera AS author_carrera,
                        u.centro AS author_centro, u.bio AS author_bio, u.avatar AS author_avatar
                 FROM posts p JOIN users u ON u.id = p.author_id"""


def images_for(db, ids: list[int]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {i: [] for i in ids}
    if not ids:
        return out
    q = ",".join("?" * len(ids))
    query = f"SELECT post_id, filename FROM post_images WHERE post_id IN ({q}) ORDER BY position, id"
    for r in db.execute(query, ids):  # nosec B608
        out[r["post_id"]].append(r["filename"])
    return out


@bp.get("/meta")
def meta():
    return jsonify({
        "categories": config.CATEGORIES, "centros": config.CENTROS, "tipos": config.TIPOS,
        "carreras": catalog.CENTROS_CARRERAS,
        "password_min": config.PASSWORD_MIN, "doc_types": config.VERIF_DOC_TYPES,
        "conditions": config.CONDITIONS, "meeting_points": config.SAFE_MEETING_POINTS,
        "max_images": config.MAX_IMAGES, "max_price_cents": config.MAX_PRICE_CENTS,
    })


@bp.get("/posts")
@login_required
def list_posts():
    db = get_db()
    where, args = [], []
    mine = request.args.get("mine") == "1"
    if mine:
        where.append("p.author_id = ?")
        args.append(g.user["id"])
        where.append("p.status != 'removed'")
    else:
        where.append("p.status IN ('active','reserved')")

    q = (request.args.get("q") or "").strip()[:80]
    if q:
        like = "%" + re.sub(r"([%_\\])", r"\\\1", q) + "%"
        where.append("(p.title LIKE ? ESCAPE '\\' OR p.description LIKE ? ESCAPE '\\')")
        args += [like, like]
    for key, col in (("category", "p.category"), ("tipo", "p.tipo"), ("centro", "p.centro")):
        v = request.args.get(key)
        if v and v != "todos":
            where.append(f"{col} = ?")
            args.append(v)

    cond = request.args.get("condition")
    if cond and cond != "todos":
        if cond not in config.CONDITIONS:
            return api_error("Estado no válido.", 400)
        where.append("p.condition = ?")
        args.append(cond)
    # Rango de precio en pesos. Donaciones y trueques cuentan como $0.
    lo, hi = request.args.get("min_price"), request.args.get("max_price")
    if lo not in (None, ""):
        v = parse_price(lo)
        if v is None:
            return api_error("Precio mínimo no válido.", 400)
        where.append("p.price_cents >= ?"); args.append(v)
    if hi not in (None, ""):
        v = parse_price(hi)
        if v is None:
            return api_error("Precio máximo no válido.", 400)
        where.append("p.price_cents <= ?"); args.append(v)

    order = {"nuevo": "p.id DESC", "barato": "p.price_cents ASC, p.id DESC",
             "caro": "p.price_cents DESC, p.id DESC"}.get(request.args.get("sort", "nuevo"), "p.id DESC")
    posts = rows(db.execute(f"{BASE_SELECT} WHERE {' AND '.join(where)} ORDER BY {order} LIMIT 100", args))
    imgs = images_for(db, [p["id"] for p in posts])
    return jsonify({"ok": True, "posts": [serialize(p, imgs[p["id"]]) for p in posts]})


@bp.get("/posts/<int:pid>")
@login_required
def get_post(pid):
    db = get_db()
    row = db.execute(f"{BASE_SELECT} WHERE p.id=?", (pid,)).fetchone()
    if not row or (row["status"] == "removed" and row["author_id"] != g.user["id"]
                   and g.user["role"] != "admin"):
        return api_error("Publicación no encontrada.", 404)
    row = dict(row)
    out = serialize(row, images_for(db, [pid])[pid])
    order = db.execute(
        """SELECT id, buyer_id, status FROM orders WHERE post_id=? AND status IN
           ('HELD','DELIVERED','DISPUTED') LIMIT 1""", (pid,)
    ).fetchone()
    if order and g.user["id"] in (order["buyer_id"], row["author_id"]):
        out["live_order"] = {"id": order["id"], "status": order["status"]}
    return jsonify({"ok": True, "post": out})


def _validate_fields(form, existing=None):
    title = clean_text(form.get("title"), 100)
    desc = clean_text(form.get("description"), 1500)
    category = form.get("category")
    centro = form.get("centro") or "General"
    tipo = form.get("tipo") or "venta"
    condition = form.get("condition") or "Usado"
    if not title or len(title) < 3:
        return None, "Escribe un título (mínimo 3 caracteres)."
    if not desc or len(desc) < 10:
        return None, "Describe el artículo y su condición (mínimo 10 caracteres)."
    if category not in config.CATEGORIES:
        return None, "Elige una categoría válida."
    if centro not in config.CENTROS:
        return None, "Elige un centro académico válido."
    if tipo not in config.TIPOS:
        return None, "Elige un tipo de operación válido."
    if condition not in config.CONDITIONS:
        return None, "Elige el estado del producto."
    price = 0
    if tipo == "venta":
        price = parse_price(form.get("price"))
        if price is None or price <= 0:
            return None, "Escribe un precio mayor a $0."
        if price > config.MAX_PRICE_CENTS:
            return None, f"El precio máximo es ${config.MAX_PRICE_CENTS // 100:,} MXN."
    return {"title": title, "description": desc, "category": category, "centro": centro,
            "tipo": tipo, "condition": condition, "price_cents": price}, None


@bp.post("/posts")
@login_required
def create_post():
    fields, err = _validate_fields(request.form)
    if err:
        return api_error(err)
    saved = save_images(request.files.getlist("images"))
    if isinstance(saved, tuple):
        return api_error(saved[1])
    db = get_db()
    with tx(db):
        cur = db.execute(
            """INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,
                                 condition,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (g.user["id"], fields["title"], fields["description"], fields["category"],
             fields["centro"], fields["tipo"], fields["price_cents"], fields["condition"], now()),
        )
        pid = cur.lastrowid
        for i, name in enumerate(saved):
            db.execute("INSERT INTO post_images(post_id,filename,position) VALUES(?,?,?)", (pid, name, i))
        notify_matches(db, pid, g.user["id"], fields["title"], fields["description"],
                       fields["category"], fields["centro"])
    return jsonify({"ok": True, "id": pid}), 201


@bp.put("/posts/<int:pid>")
@login_required
def update_post(pid):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
    if not post or post["author_id"] != g.user["id"] or post["status"] == "removed":
        return api_error("Publicación no encontrada.", 404)
    if post["status"] not in ("active", "paused"):
        return api_error("No puedes editar una publicación reservada o vendida.", 409)
    fields, err = _validate_fields(request.form)
    if err:
        return api_error(err)
    new_imgs = [f for f in request.files.getlist("images") if f and f.filename]
    saved = []
    if new_imgs:
        saved = save_images(new_imgs)
        if isinstance(saved, tuple):
            return api_error(saved[1])
    with tx(db):
        cur = db.execute(
            """UPDATE posts SET title=?,description=?,category=?,centro=?,tipo=?,price_cents=?,
                                condition=? WHERE id=? AND status IN ('active','paused')""",
            (fields["title"], fields["description"], fields["category"], fields["centro"],
             fields["tipo"], fields["price_cents"], fields["condition"], pid),
        )
        if cur.rowcount != 1:
            raise RuntimeError("estado cambió")
        if saved:
            db.execute("DELETE FROM post_images WHERE post_id=?", (pid,))
            for i, name in enumerate(saved):
                db.execute("INSERT INTO post_images(post_id,filename,position) VALUES(?,?,?)", (pid, name, i))
    return jsonify({"ok": True})


@bp.delete("/posts/<int:pid>")
@login_required
def delete_post(pid):
    db = get_db()
    with tx(db):
        post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if not post or post["author_id"] != g.user["id"] or post["status"] == "removed":
            resp = api_error("Publicación no encontrada.", 404)
        elif post["status"] == "reserved":
            resp = api_error("Hay un pago retenido en esta publicación; ciérralo primero.", 409)
        else:
            db.execute("UPDATE posts SET status='removed' WHERE id=?", (pid,))
            resp = jsonify({"ok": True})
    return resp


@bp.post("/posts/<int:pid>/pause")
@login_required
def pause_post(pid):
    """Pausa (deja de aparecer en el catálogo) o reanuda una publicación propia."""
    paused = bool((request.get_json(silent=True) or {}).get("paused", True))
    db = get_db()
    with tx(db):
        post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if not post or post["author_id"] != g.user["id"] or post["status"] == "removed":
            resp = api_error("Publicación no encontrada.", 404)
        elif paused and post["status"] != "active":
            resp = api_error("Solo se pueden pausar publicaciones activas (no reservadas ni vendidas).", 409)
        elif not paused and post["status"] != "paused":
            resp = api_error("La publicación no está pausada.", 409)
        else:
            new = "paused" if paused else "active"
            db.execute("UPDATE posts SET status=? WHERE id=? AND status=?", (new, pid, post["status"]))
            resp = jsonify({"ok": True, "status": new})
    return resp


@bp.post("/posts/<int:pid>/close")
@login_required
def close_post(pid):
    """Trueque o donación concluidos (sin pago): el autor la marca como entregada."""
    db = get_db()
    with tx(db):
        post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if not post or post["author_id"] != g.user["id"]:
            resp = api_error("Publicación no encontrada.", 404)
        elif post["tipo"] == "venta":
            resp = api_error("Las ventas se cierran cuando el comprador confirma la recepción.", 409)
        elif post["status"] != "active":
            resp = api_error("La publicación ya no está activa.", 409)
        else:
            db.execute("UPDATE posts SET status='sold' WHERE id=?", (pid,))
            resp = jsonify({"ok": True})
    return resp
