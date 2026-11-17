"""Registro de vendedores mediante Stripe Connect V2."""

import stripe

from flask import Blueprint, g, jsonify

import config
from db import get_db, tx
from security import api_error, login_required


bp = Blueprint("connect", __name__, url_prefix="/api/connect")


def _stripe_client():
    if config.PAYMENT_PROVIDER != "stripe":
        raise RuntimeError("Stripe no está habilitado como proveedor de pagos.")

    if not config.STRIPE_SECRET_KEY:
        raise RuntimeError("Falta configurar STRIPE_SECRET_KEY.")

    return stripe.StripeClient(config.STRIPE_SECRET_KEY)


def _get(obj, key, default=None):
    """Lee propiedades de objetos Stripe o diccionarios."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _account_status(account):
    configuration = _get(account, "configuration", {})
    recipient = _get(configuration, "recipient", {})
    capabilities = _get(recipient, "capabilities", {})
    stripe_balance = _get(capabilities, "stripe_balance", {})
    transfers_config = _get(stripe_balance, "stripe_transfers", {})

    transfers = _get(transfers_config, "status", "pending")

    requirements = _get(account, "requirements", {})
    entries = _get(requirements, "entries", []) or []

    currently_due = [
        _get(entry, "description", "Requisito pendiente")
        for entry in entries
        if _get(entry, "awaiting_action_from") == "user"
    ]

    status_details = _get(transfers_config, "status_details", []) or []

    return {
        "account_id": account.id,
        "details_submitted": len(currently_due) == 0,
        "transfers": transfers,
        "currently_due": currently_due,
        "status_details": status_details,
        "connected": transfers == "active",
    }


@bp.post("/onboarding")
@login_required
def create_onboarding():
    if config.CONNECT_SIMULATED and config.STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")):
        db = get_db()
        account_id = f"SIM-CONNECT-{g.user['id']}"

        with tx(db):
            db.execute(
                "UPDATE users SET stripe_account_id=? WHERE id=?",
                (account_id, g.user["id"]),
            )

        return jsonify({
            "ok": True,
            "url": None,
            "simulated": True,
            "account": {
                "account_id": account_id,
                "details_submitted": True,
                "transfers": "active",
                "currently_due": [],
                "status_details": [],
                "connected": True,
                "simulated": True,
            },
        })
    try:
        stripe_client = _stripe_client()
    except RuntimeError as exc:
        return api_error(str(exc), 503)

    db = get_db()
    account_id = g.user.get("stripe_account_id") or ""

    try:
        if account_id.startswith("SIM-CONNECT-"):
            return api_error("Esta cuenta pertenece a una prueba. Usa un usuario independiente para pagos reales.", 409)
        if account_id:
            account = stripe_client.v2.core.accounts.retrieve(account_id, {"include": ["configuration.recipient", "requirements"]})
        else:
            account = stripe_client.v2.core.accounts.create(
                {
                    "contact_email": g.user["email"],
                    "include": ["configuration.recipient", "requirements"],
                    "identity": {
                        "country": "MX",
                    },
                    "dashboard": "express",
                    "defaults": {
                        "responsibilities": {
                            "fees_collector": "application",
                            "losses_collector": "application",
                        },
                    },
                    "configuration": {
                        "recipient": {
                            "capabilities": {
                                "stripe_balance": {
                                    "stripe_transfers": {
                                        "requested": True,
                                    },
                                },
                            },
                        },
                    },
                    "metadata": {
                        "ecogallo_user_id": str(g.user["id"]),
                    },
                },
                {
                    "idempotency_key": (
                        f"ecogallo-connect-account-{g.user['id']}"
                    ),
                },
            )

            with tx(db):
                db.execute(
                    "UPDATE users SET stripe_account_id=? WHERE id=?",
                    (account.id, g.user["id"]),
                )

        account_link = stripe_client.v2.core.account_links.create(
            {
                "account": account.id,
                "use_case": {
                    "type": "account_onboarding",
                    "account_onboarding": {
                        "configurations": ["recipient"],
                        "refresh_url": config.STRIPE_CONNECT_REFRESH_URL,
                        "return_url": config.STRIPE_CONNECT_RETURN_URL,
                        "collection_options": {
                            "fields": "currently_due",
                        },
                    },
                },
            }
        )

        return jsonify({
            "ok": True,
            "url": account_link.url,
            "account": _account_status(account),
        })

    except stripe.StripeError:
        return api_error(
            "Stripe no pudo iniciar el registro. Revisa la configuración y vuelve a intentarlo.",
            502,
        )


@bp.get("/status")
@login_required
def connect_status():
    if config.PAYMENT_PROVIDER == "simulado":
        return jsonify({"ok": True, "connected": True, "simulated": True, "demo": True})
    if config.CONNECT_SIMULATED and config.STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")):
        account_id = g.user.get("stripe_account_id") or ""

        return jsonify({
            "ok": True,
            "account": {
                "account_id": account_id,
                "details_submitted": True,
                "transfers": "simulated",
                "currently_due": [],
                "status_details": [],
                "connected": True,
                "simulated": True,
            },
            "connected": account_id.startswith("SIM-CONNECT-"),
            "simulated": True,
        })
    try:
        stripe_client = _stripe_client()
    except RuntimeError as exc:
        return api_error(str(exc), 503)

    account_id = g.user.get("stripe_account_id") or ""

    if not account_id:
        return jsonify({
            "ok": True,
            "account": None,
            "connected": False,
        })

    try:
        account = stripe_client.v2.core.accounts.retrieve(account_id, {"include": ["configuration.recipient", "requirements"]})
        status = _account_status(account)

        return jsonify({
            "ok": True,
            "account": status,
            "connected": status["connected"],
        })

    except stripe.StripeError:
        return api_error(
            "No se pudo consultar la cuenta de Stripe. Intenta más tarde.",
            502,
        )
