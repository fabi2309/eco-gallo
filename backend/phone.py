"""Teléfono confirmado por SMS y cuenta para recibir pagos con tarjeta.

Para pagar o cobrar con tarjeta, comprador y vendedor deben tener un teléfono confirmado: si un artículo
no se entrega, ECO-GALLO (y la otra persona) pueden localizarlos.

Datos de tarjeta: el número completo y el CVV NUNCA llegan al servidor. El navegador los valida y solo
envía la marca y los últimos 4 dígitos (lo mismo que imprime un ticket). Con Mercado Pago real, la tarjeta
se captura en la página de Mercado Pago.
"""
import base64
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from flask import Blueprint, g, jsonify, request

import config
from db import get_db, now, tx
from security import _hmac, api_error, clean_text, login_required, new_code

bp = Blueprint("phone", __name__, url_prefix="/api")
log = logging.getLogger("ecogallo")

CODE_TTL = 600            # 10 minutos
COOLDOWN = 60             # segundos entre envíos
MAX_PER_HOUR = 5
MAX_ATTEMPTS = 5
BRANDS = ("visa", "mastercard", "amex", "carnet", "tarjeta")


def normalize_phone(raw) -> str | None:
    """Celular de México: 10 dígitos, con o sin +52 / 52 / espacios. Devuelve '+52XXXXXXXXXX'."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 12 and digits.startswith("52"):
        digits = digits[2:]
    elif len(digits) == 13 and digits.startswith("521"):      # formato antiguo de celulares
        digits = digits[3:]
    if not re.fullmatch(r"[1-9]\d{9}", digits):
        return None
    return "+52" + digits


def pretty_phone(phone: str) -> str:
    d = phone[-10:]
    return f"{d[:3]} {d[3:6]} {d[6:]}" if len(d) == 10 else phone


def masked_phone(phone: str) -> str:
    return f"••• ••• {phone[-4:]}" if phone else ""


def card_ready(u) -> bool:
    """¿Puede pagar con tarjeta? (teléfono confirmado)"""
    return bool(u["phone"] and u["phone_verified_at"])


def payout_ready(u) -> bool:
    """¿Puede recibir pagos con tarjeta? (teléfono confirmado + cuenta para recibir)"""
    return card_ready(u) and bool(u["payout_kind"] and u["payout_last4"])


def public_payment_profile(u) -> dict:
    return {
        "phone": pretty_phone(u["phone"]) if u["phone"] else "",
        "phone_verified": bool(u["phone_verified_at"]),
        "payout": {"kind": u["payout_kind"], "last4": u["payout_last4"], "holder": u["payout_holder"]}
        if u["payout_kind"] else None,
        "card_ready": card_ready(u), "payout_ready": payout_ready(u),
    }


def send_sms(phone: str, text: str) -> None:
    """Envía un SMS con la API de Twilio (sin SDK). Lanza excepción si falla."""
    url = f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json"
    body = urllib.parse.urlencode({"To": phone, "From": config.TWILIO_FROM, "Body": text}).encode()
    auth = base64.b64encode(f"{config.TWILIO_ACCOUNT_SID}:{config.TWILIO_AUTH_TOKEN}".encode()).decode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Authorization": f"Basic {auth}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310 - URL fija https de Twilio
            if resp.status >= 300:
                raise RuntimeError(f"Twilio respondió {resp.status}")
    except urllib.error.HTTPError as exc:      # Twilio explica el motivo en el cuerpo (código y mensaje)
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Twilio respondió {exc.code}: {detail}") from exc


def _code_hash(uid: int, phone: str, code: str) -> str:
    return _hmac(f"phone:{uid}:{phone}:{code}")


@bp.post("/me/phone")
@login_required
def request_phone_code():
    phone = normalize_phone((request.get_json(silent=True) or {}).get("phone"))
    if not phone:
        return api_error("Escribe tu celular a 10 dígitos (por ejemplo 449 123 4567).")
    db, uid, t = get_db(), g.user["id"], now()
    taken = db.execute("SELECT 1 FROM users WHERE phone=? AND phone_verified_at>0 AND id!=? AND deleted_at=0",
                       (phone, uid)).fetchone()
    if taken:
        return api_error("Ese número ya está confirmado en otra cuenta.", 409)
    last = db.execute("SELECT created_at FROM phone_codes WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    if last and t - last["created_at"] < COOLDOWN:
        wait = COOLDOWN - (t - last["created_at"])
        return api_error(f"Espera {wait} s para pedir otro código.", 429, retry_after=wait)
    if db.execute("SELECT COUNT(*) FROM phone_codes WHERE user_id=? AND created_at>?", (uid, t - 3600)).fetchone()[0] >= MAX_PER_HOUR:
        return api_error("Pediste demasiados códigos. Intenta de nuevo en una hora.", 429)
    code = new_code()
    with tx(db):
        db.execute("UPDATE phone_codes SET used=1 WHERE user_id=? AND used=0", (uid,))
        db.execute("INSERT INTO phone_codes(user_id,phone,code_hash,expires_at,created_at) VALUES(?,?,?,?,?)",
                   (uid, phone, _code_hash(uid, phone, code), t + CODE_TTL, t))
    out = {"ok": True, "phone": pretty_phone(phone), "ttl": CODE_TTL, "cooldown": COOLDOWN}
    if config.SMS_ENABLED:
        try:
            send_sms(phone, f"ECO-GALLO UAA: tu código para confirmar tu teléfono es {code}. Vence en 10 minutos.")
        except Exception as exc:  # noqa: BLE001 - el detalle va a la consola, no al cliente
            log.error("No se pudo enviar el SMS a %s: %s", masked_phone(phone), exc)
            print(f"  Aviso: no se pudo enviar el SMS ({exc}).", flush=True)
            if not config.DEV:
                return api_error("No pudimos enviar el SMS. Revisa el número e intenta de nuevo.", 502)
            out["dev_code"] = code   # desarrollo: si el SMS falla, el código se muestra para no bloquear
    elif config.DEV:
        out["dev_code"] = code      # SOLO desarrollo sin SMS configurado
    else:
        return api_error("El envío de SMS no está configurado.", 503)
    return jsonify(out)


@bp.post("/me/phone/verify")
@login_required
def verify_phone_code():
    code = re.sub(r"\D", "", str((request.get_json(silent=True) or {}).get("code") or ""))
    db, uid, t = get_db(), g.user["id"], now()
    row = db.execute("SELECT * FROM phone_codes WHERE user_id=? AND used=0 ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    if not row or row["expires_at"] < t:
        return api_error("El código venció. Pide uno nuevo.", 400)
    if row["attempts"] >= MAX_ATTEMPTS:
        return api_error("Demasiados intentos. Pide un código nuevo.", 429)
    import hmac
    if len(code) != 6 or not hmac.compare_digest(row["code_hash"], _code_hash(uid, row["phone"], code)):
        db.execute("UPDATE phone_codes SET attempts=attempts+1 WHERE id=?", (row["id"],))
        left = MAX_ATTEMPTS - row["attempts"] - 1
        return api_error(f"Código incorrecto. Te quedan {left} intentos." if left > 0 else
                         "Código incorrecto. Pide un código nuevo.", 400)
    with tx(db):
        db.execute("UPDATE phone_codes SET used=1 WHERE id=?", (row["id"],))
        db.execute("UPDATE users SET phone=?, phone_verified_at=? WHERE id=?", (row["phone"], t, uid))
    u = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return jsonify({"ok": True, "payments": public_payment_profile(u)})


@bp.delete("/me/phone")
@login_required
def remove_phone():
    from payment_states import OPEN_SQL
    db, uid = get_db(), g.user["id"]
    busy = db.execute(f"SELECT 1 FROM orders WHERE (buyer_id=? OR seller_id=?) AND payment_provider!='efectivo' "  # nosec B608
                      f"AND status IN {OPEN_SQL} LIMIT 1", (uid, uid)).fetchone()
    if busy:
        return api_error("Tienes compras o ventas con tarjeta en curso: tu teléfono debe seguir disponible hasta que terminen.", 409)
    db.execute("UPDATE users SET phone='', phone_verified_at=0 WHERE id=?", (uid,))
    return jsonify({"ok": True})


@bp.put("/me/payout")
@login_required
def set_payout():
    """Cuenta para recibir. El navegador valida el número completo; aquí solo llegan tipo, titular y últimos 4."""
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    last4 = str(data.get("last4") or "")
    holder = clean_text(data.get("holder"), 80)
    if kind not in ("tarjeta", "clabe"):
        return api_error("Elige tarjeta de débito o CLABE.")
    if not re.fullmatch(r"\d{4}", last4):
        return api_error("Número de cuenta inválido.")
    if not holder or len(holder) < 5:
        return api_error("Escribe el nombre del titular como aparece en la cuenta.")
    if not card_ready(g.user):
        return api_error("Primero confirma tu teléfono.", 409)
    db = get_db()
    db.execute("UPDATE users SET payout_kind=?, payout_last4=?, payout_holder=?, payout_updated_at=? WHERE id=?",
               (kind, last4, holder, now(), g.user["id"]))
    u = db.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone()
    return jsonify({"ok": True, "payments": public_payment_profile(u)})


def parse_card(data) -> tuple[dict | None, str | None]:
    """Tarjeta del comprador para el pago de prueba: solo marca, últimos 4, vencimiento y titular."""
    card = data if isinstance(data, dict) else {}
    brand = str(card.get("brand") or "").lower()
    last4 = str(card.get("last4") or "")
    holder = clean_text(card.get("holder"), 80)
    try:
        month, year = int(card.get("exp_month")), int(card.get("exp_year"))
    except (TypeError, ValueError):
        return None, "Escribe el vencimiento de la tarjeta (MM/AA)."
    if brand not in BRANDS or not re.fullmatch(r"\d{4}", last4):
        return None, "Revisa el número de la tarjeta."
    if not holder or len(holder) < 5:
        return None, "Escribe el nombre del titular como aparece en la tarjeta."
    if year < 100:
        year += 2000
    import datetime
    today = datetime.date.today()
    if not 1 <= month <= 12 or (year, month) < (today.year, today.month) or year > today.year + 20:
        return None, "La tarjeta está vencida o la fecha no es válida."
    return {"brand": brand, "last4": last4}, None
