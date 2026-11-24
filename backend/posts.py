"""Publicaciones, búsqueda y subida de imágenes."""
import math
import re
import uuid
import difflib
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, jsonify, request

import catalog
import config
from badges import BADGE_COLS, compute as compute_badges
from db import get_db, now, rows, tx
from security import api_error, clean_text, login_required
from pagination import pagination

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


def drop_images(names):
    for name in names:
        (config.UPLOADS / name).unlink(missing_ok=True)


def save_images(files) -> list[str] | tuple[None, str]:
    from media import normalize_image
    files = [f for f in files if f and f.filename]
    if len(files) > config.MAX_IMAGES:
        return None, f"Máximo {config.MAX_IMAGES} imágenes."
    normalized = []
    for f in files:
        data = f.read(config.MAX_IMAGE_BYTES + 1)
        if len(data) > config.MAX_IMAGE_BYTES:
            return None, "Cada imagen debe pesar menos de 5 MB."
        try:
            data, ext = normalize_image(data)
        except ValueError as exc:
            return None, str(exc)
        normalized.append((f"{uuid.uuid4().hex}.{ext}", data))
    saved = []
    try:
        for name, data in normalized:
            (config.UPLOADS / name).write_bytes(data)
            saved.append(name)
    except Exception:
        drop_images(saved)
        raise
    return saved


def parse_price(raw) -> int | None:
    try:
        text = str(raw).replace(",", ".").strip()
        if len(text) > 40:
            return None
        value = Decimal(text or "0")
        if not value.is_finite() or value < 0 or value > config.MAX_PRICE_CENTS / 100:
            return None
        return int((value * 100).to_integral_value())
    except (InvalidOperation, ValueError, OverflowError):
        return None


def post_stats(db, post_id: int, author_id: int, views_count: int = 0, title: str = "",
               desc: str = "", cat: str = "", centro: str = "") -> dict:
    """Métricas detalladas por publicación: vistas, contactos e interesados."""
    contacts = db.execute(
        "SELECT COUNT(DISTINCT sender_id) c FROM messages WHERE post_id=? AND sender_id != ?",
        (post_id, author_id)
    ).fetchone()["c"]

    fav_users = {r[0] for r in db.execute("SELECT user_id FROM favorites WHERE post_id=?", (post_id,)).fetchall()}
    from wishlist import get_matching_wishlist_users
    wish_users = get_matching_wishlist_users(db, post_id, author_id, title, desc, cat, centro)
    interested = len(fav_users.union(wish_users))

    return {
        "views": views_count,
        "contacts": contacts,
        "interested": interested,
    }


def serialize(row: dict, images: list[str], stats: dict | None = None) -> dict:
    out = {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "category": row["category"], "centro": row["centro"], "tipo": row["tipo"],
        "price_cents": row["price_cents"], "condition": row["condition"],
        "status": row["status"], "created_at": row["created_at"],
        "author": {"id": row["author_id"], "name": row["author_name"],
                   "carrera": row["author_carrera"], "centro": row["author_centro"],
                   "bio": row["author_bio"], "badges": compute_badges(row),
                   "avatar": f"/uploads/{row['author_avatar']}" if row["author_avatar"] else ""},
        "images": [f"/uploads/{n}" for n in images],
        "meeting": {"place": row.get("meet_place", ""), "lat": row.get("meet_lat"), "lng": row.get("meet_lng")},
        "new_price_cents": row.get("new_price_cents", 0),
        "featured": (row.get("featured_until") or 0) > now(),
        "featured_until": row.get("featured_until") or 0,
        "accepts_card": bool(row.get("author_card_ready")),
    }
    if row.get("distance_km") is not None:
        out["distance_km"] = round(row["distance_km"], 1)
    if stats is not None:
        out["stats"] = stats
    elif "views_count" in row:
        out["stats"] = {
            "views": row.get("views_count", 0),
            "contacts": row.get("contacts_count", 0),
            "interested": row.get("interested_count", 0),
        }
    return out


BASE_SELECT = f"""SELECT p.*, u.name AS author_name, u.carrera AS author_carrera,
                        u.centro AS author_centro, u.bio AS author_bio, u.avatar AS author_avatar,
                        (u.phone_verified_at>0 AND u.payout_last4!='') AS author_card_ready,
                        {BADGE_COLS}
                 FROM posts p JOIN users u ON u.id = p.author_id"""  # nosec B608 - BADGE_COLS es constante


def images_for(db, ids: list[int]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {i: [] for i in ids}
    if not ids:
        return out
    q = ",".join("?" * len(ids))
    query = f"SELECT post_id, filename FROM post_images WHERE post_id IN ({q}) ORDER BY position, id"  # nosec B608 - solo placeholders ?
    for r in db.execute(query, ids):
        out[r["post_id"]].append(r["filename"])
    return out


@bp.get("/meta")
def meta():
    return jsonify({
        "payment_mode": "disabled" if config.PAYMENT_PROVIDER == "disabled" else "demo" if config.PAYMENT_PROVIDER == "simulado"
        else ("test" if config.MP_TEST else "live") if config.PAYMENT_PROVIDER == "mercadopago"
        else "live" if config.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_")) else "test",
        "payment_provider": config.PAYMENT_PROVIDER,
        "payment_methods": (["en_linea"] if config.PAYMENT_PROVIDER != "disabled" else []) + ["efectivo"],
        "categories": config.CATEGORIES, "centros": config.CENTROS, "tipos": config.TIPOS,
        "carreras": catalog.CENTROS_CARRERAS, "email_domains": list(config.EMAIL_DOMAINS),
        "password_min": config.PASSWORD_MIN, "doc_types": config.VERIF_DOC_TYPES,
        "conditions": config.CONDITIONS, "meeting_points": config.SAFE_MEETING_POINTS,
        "max_images": config.MAX_IMAGES, "max_price_cents": config.MAX_PRICE_CENTS,
        "microsoft_login": bool(config.MS_CLIENT_ID and config.MS_CLIENT_SECRET and config.MS_TENANT),
        "legal": {"version": config.LEGAL_VERSION, "operator": config.OPERATOR_NAME,
                  "email": config.PRIVACY_EMAIL, "address": config.OPERATOR_ADDRESS},
    })


# Diccionario de sinónimos locales para la comunidad UAA
SYNONYMS = {
    'libro': ['texto', 'guia', 'antologia', 'manual'],
    'bici': ['bicicleta', 'cicla', 'transporte'],
    'compu': ['laptop', 'computadora', 'pc', 'portatil'],
    'calculadora': ['casio', 'cientifica'],
    'bata': ['laboratorio', 'quimica', 'medicina']
}


def expand_query(term):
    """Expande el término de búsqueda usando el diccionario de sinónimos"""
    term_lower = term.lower().strip()
    expanded = [term_lower]
    for key, synonyms in SYNONYMS.items():
        if term_lower == key or term_lower in synonyms:
            expanded.append(key)
            expanded.extend(synonyms)
    return list(set(expanded))


@bp.get("/search/smart")
@login_required
def smart_search():
    """Buscador inteligente con sinónimos y tolerancia a errores (fuzzy search)."""
    db = get_db()
    query = (request.args.get("q") or "").strip()[:80]
    if not query:
        return jsonify([])

    # 1. Obtener todas las publicaciones activas
    posts_cursor = db.execute(f"{BASE_SELECT} WHERE p.status IN ('active','reserved') ORDER BY p.id DESC LIMIT 500")
    posts = rows(posts_cursor)

    search_terms = expand_query(query)
    matched_products = set()

    all_titles = [p['title'] for p in posts]

    for term in search_terms:
        # Tolerancia a errores de escritura con difflib (cutoff=0.3 permite errores tipográficos)
        close_titles = difflib.get_close_matches(term, all_titles, n=5, cutoff=0.3)

        for p in posts:
            if any(t in p['title'].lower() for t in search_terms) or \
               any(t in p['description'].lower() for t in search_terms) or \
               p['title'] in close_titles:
                matched_products.add(p["id"])

    # Filtrar las publicaciones que coincidieron preservando el orden y formato
    filtered_posts = [p for p in posts if p["id"] in matched_products]
    imgs = images_for(db, [p["id"] for p in filtered_posts])

    out_posts = [serialize(p, imgs[p["id"]]) for p in filtered_posts[:10]]
    return jsonify(out_posts)


@bp.get("/posts")
@login_required
def list_posts():
    db = get_db()
    try:
        page, size, offset = pagination()
    except ValueError as exc:
        return api_error(str(exc))
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

    # Cerca de mí (US-10, US-16): la ubicación del usuario solo viaja en la consulta; no se guarda.
    select, sel_args = BASE_SELECT, []
    lat, lng = request.args.get("lat"), request.args.get("lng")
    near = lat not in (None, "") and lng not in (None, "")
    if near:
        lat, lng = parse_coord(lat, 90), parse_coord(lng, 180)
        try:
            radius = float(request.args.get("radius_km", "10"))
        except ValueError:
            radius = -1
        if lat is None or lng is None or not 0 < radius <= 200:
            return api_error("Ubicación o distancia no válida.", 400)
        select = BASE_SELECT.replace("SELECT p.*,", "SELECT p.*, distance_km(p.meet_lat, p.meet_lng, ?, ?) AS distance_km,", 1)
        sel_args = [lat, lng]
        where.append("p.meet_lat IS NOT NULL AND distance_km(p.meet_lat, p.meet_lng, ?, ?) <= ?")
        args += [lat, lng, radius]

    feat = f"(p.featured_until > {int(now())}) DESC, "   # las destacadas vigentes primero (valor numérico propio)
    order = {"nuevo": feat + "p.id DESC", "barato": "p.price_cents ASC, p.id DESC",
             "caro": "p.price_cents DESC, p.id DESC",
             "cerca": "distance_km ASC, p.id DESC" if near else "p.id DESC"}.get(request.args.get("sort", "nuevo"), "p.id DESC")
    total = db.execute(f"SELECT COUNT(*) FROM posts p WHERE {' AND '.join(where)}", args).fetchone()[0]  # nosec B608 - SQL structure from fixed constants; user values are bound parameters
    posts = rows(db.execute(f"{select} WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?",  # nosec B608 - estructura constante
                            [*sel_args, *args, size, offset]))
    imgs = images_for(db, [p["id"] for p in posts])
    is_mine = request.args.get("mine") == "1"
    out_posts = []
    for p in posts:
        s = post_stats(db, p["id"], p["author_id"], p.get("views_count", 0),
                       p["title"], p["description"], p["category"], p["centro"]) if is_mine else None
        out_posts.append(serialize(p, imgs[p["id"]], stats=s))
    return jsonify({"ok": True, "posts": out_posts, "page": page, "per_page": size, "total": total,
                    "pages": max(1, (total + size - 1) // size)})


@bp.get("/posts/<int:pid>")
@login_required
def get_post(pid):
    db = get_db()
    row = db.execute(f"{BASE_SELECT} WHERE p.id=?", (pid,)).fetchone()
    if not row or (row["status"] in ("removed", "pending") and row["author_id"] != g.user["id"]
                   and g.user["role"] != "admin"):
        return api_error("Publicación no encontrada.", 404)
    row = dict(row)

    # Incrementar vistas si quien consulta no es el autor
    if g.user["id"] != row["author_id"]:
        db.execute("UPDATE posts SET views_count = views_count + 1 WHERE id=?", (pid,))
        row["views_count"] = (row.get("views_count") or 0) + 1

    stats = post_stats(db, pid, row["author_id"], row.get("views_count", 0),
                       row["title"], row["description"], row["category"], row["centro"])
    out = serialize(row, images_for(db, [pid])[pid], stats=stats)

    is_fav = bool(db.execute("SELECT 1 FROM favorites WHERE user_id=? AND post_id=?", (g.user["id"], pid)).fetchone())
    out["is_favorited"] = is_fav

    order = db.execute(
        """SELECT id, buyer_id, status FROM orders WHERE post_id=? AND status IN
           ('CASH_PENDING','PENDING_PAYMENT','HELD','DELIVERED','DISPUTED','RELEASING','REFUNDING','PAYMENT_REVIEW') LIMIT 1""", (pid,)
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
    new_price = 0
    if form.get("new_price") not in (None, ""):
        new_price = parse_price(form.get("new_price"))
        if new_price is None or new_price <= 0:
            return None, "El precio nuevo de referencia no es válido."
        if new_price < price:
            return None, "El precio nuevo de referencia debe ser mayor o igual a tu precio."
    meet_place = clean_text(form.get("meet_place"), 120, required=False) or ""
    lat, lng = form.get("meet_lat"), form.get("meet_lng")
    if lat in (None, "") and lng in (None, ""):
        lat = lng = None
    else:
        lat, lng = parse_coord(lat, 90), parse_coord(lng, 180)
        if lat is None or lng is None:
            return None, "La ubicación no es válida. Vuelve a tomarla o quítala."
    return {"title": title, "description": desc, "category": category, "centro": centro,
            "tipo": tipo, "condition": condition, "price_cents": price,
            "meet_place": meet_place, "meet_lat": lat, "meet_lng": lng, "new_price_cents": new_price}, None


def parse_coord(raw, limit):
    """Coordenada redondeada a 3 decimales (~100 m): suficiente para «cerca de mí» sin exponer un domicilio exacto."""
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or abs(v) > limit:
        return None
    return round(v, 3)


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
    try:
        with tx(db):
            cur = db.execute(
                """INSERT INTO posts(author_id,title,description,category,centro,tipo,price_cents,
                                     condition,status,created_at,meet_place,meet_lat,meet_lng,new_price_cents)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (g.user["id"], fields["title"], fields["description"], fields["category"],
                 fields["centro"], fields["tipo"], fields["price_cents"], fields["condition"], "pending", now(),
                 fields["meet_place"], fields["meet_lat"], fields["meet_lng"], fields["new_price_cents"]),
            )
            pid = cur.lastrowid
            for i, name in enumerate(saved):
                db.execute("INSERT INTO post_images(post_id,filename,position) VALUES(?,?,?)", (pid, name, i))
            from security import notify
            for admin in db.execute("SELECT id FROM users WHERE role='admin' AND suspended=0"):
                notify(db, admin['id'], 'Hay una publicación pendiente de revisión.', '#/admin')
    except Exception:
        drop_images(saved)
        raise
    return jsonify({"ok": True, "id": pid}), 201


@bp.put("/posts/<int:pid>")
@login_required
def update_post(pid):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
    if not post or post["author_id"] != g.user["id"] or post["status"] == "removed":
        return api_error("Publicación no encontrada.", 404)
    if post["status"] not in ("active", "paused", "pending"):
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
    changed_content = bool(saved) or any(fields[k] != post[k] for k in ("title", "description", "category", "centro", "tipo",
                                                                        "meet_place"))
    next_status = "pending" if changed_content else post["status"]
    old_images = []
    try:
        with tx(db):
            cur = db.execute(
                """UPDATE posts SET title=?,description=?,category=?,centro=?,tipo=?,price_cents=?,
                                    condition=?,status=?,meet_place=?,meet_lat=?,meet_lng=?,new_price_cents=?
                   WHERE id=? AND status IN ('active','paused','pending')""",
                (fields["title"], fields["description"], fields["category"], fields["centro"],
                 fields["tipo"], fields["price_cents"], fields["condition"], next_status,
                 fields["meet_place"], fields["meet_lat"], fields["meet_lng"], fields["new_price_cents"], pid),
            )
            if cur.rowcount != 1:
                raise RuntimeError("estado cambió")
            if saved:
                old_images = [r[0] for r in db.execute("SELECT filename FROM post_images WHERE post_id=?", (pid,))]
                db.execute("DELETE FROM post_images WHERE post_id=?", (pid,))
                for i, name in enumerate(saved):
                    db.execute("INSERT INTO post_images(post_id,filename,position) VALUES(?,?,?)", (pid, name, i))
            # Notificar si baja de precio
            old_price = post["price_cents"]
            new_price = fields["price_cents"]
            if next_status == "active" and post["tipo"] == "venta" and fields["tipo"] == "venta" and new_price < old_price:
                from wishlist import notify_price_drop
                db.execute("UPDATE posts SET approved_price_cents=? WHERE id=?", (new_price, pid))
                notify_price_drop(db, pid, post["author_id"], fields["title"], fields["category"],
                                  fields["centro"], old_price, new_price, fields["description"])
            if changed_content:
                from security import notify
                for admin in db.execute("SELECT id FROM users WHERE role='admin' AND suspended=0"):
                    notify(db, admin["id"], "Una publicación editada requiere revisión.", "#/admin")
    except Exception:
        drop_images(saved)
        raise
    if saved:
        drop_images(old_images)
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


@bp.post("/posts/<int:pid>/feature")
@login_required
def feature_post(pid):
    """Destacar una publicación propia (US-14): gratis, por FEATURE_HOURS, una a la vez por persona."""
    db = get_db()
    t = now()
    with tx(db):
        post = db.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        if not post or post["author_id"] != g.user["id"]:
            return api_error("Publicación no encontrada.", 404)
        if post["status"] != "active":
            return api_error("Solo puedes destacar publicaciones activas (ya aprobadas).", 409)
        if post["featured_until"] > t:
            return api_error("Esta publicación ya está destacada.", 409)
        wait = post["featured_at"] + config.FEATURE_COOLDOWN_DAYS * 86400 - t
        if post["featured_at"] and wait > 0:
            return api_error(f"Podrás volver a destacarla en {max(1, wait // 86400)} día(s).", 429)
        active = db.execute("SELECT COUNT(*) FROM posts WHERE author_id=? AND featured_until>? AND status='active'",
                            (g.user["id"], t)).fetchone()[0]
        if active >= config.FEATURE_MAX_ACTIVE:
            return api_error("Ya tienes una publicación destacada. Espera a que termine para destacar otra.", 409)
        until = t + config.FEATURE_HOURS * 3600
        db.execute("UPDATE posts SET featured_until=?, featured_at=? WHERE id=?", (until, t, pid))
    return jsonify({"ok": True, "featured_until": until})


@bp.get("/posts/stats/mine")
@login_required
def my_stats():
    """Estadísticas del anunciante (US-17): vistas, contactos e interesados por publicación y en total."""
    db = get_db()
    uid = g.user["id"]
    per = rows(db.execute(
        """SELECT p.id, p.title, p.status, p.tipo, p.price_cents, p.views_count AS views, p.created_at,
                  (SELECT COUNT(DISTINCT m.sender_id) FROM messages m WHERE m.post_id=p.id AND m.sender_id!=p.author_id) AS contacts,
                  (SELECT COUNT(*) FROM favorites f WHERE f.post_id=p.id) AS favorites
           FROM posts p WHERE p.author_id=? AND p.status!='removed' ORDER BY p.views_count DESC, p.id DESC LIMIT 100""",
        (uid,)))
    for r in per:
        r["contact_rate"] = round(r["contacts"] / r["views"], 3) if r["views"] else 0
    earned = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM orders WHERE seller_id=? AND status='RELEASED'",
                        (uid,)).fetchone()[0]
    totals = {
        "posts": len(per),
        "active": sum(1 for r in per if r["status"] in ("active", "reserved")),
        "reused": sum(1 for r in per if r["status"] == "sold"),
        "views": sum(r["views"] for r in per),
        "contacts": sum(r["contacts"] for r in per),
        "favorites": sum(r["favorites"] for r in per),
        "earned_cents": earned,
    }
    return jsonify({"ok": True, "totals": totals, "posts": per})


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
            db.execute("UPDATE posts SET status='sold', closed_at=? WHERE id=?", (now(), pid))
            resp = jsonify({"ok": True})
    return resp
