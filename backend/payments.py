
"""Proveedores de pago de ECO-GALLO.

SimulatedProvider permite probar el flujo sin cobrar dinero.
StripeProvider procesa pagos mediante Checkout y Connect.
"""

import secrets

import config


class PaymentProvider:
    name = "base"

    def hold(self, order_id: int, amount_cents: int, buyer_email: str) -> str:
        raise NotImplementedError

    def release(
        self,
        order_id: int,
        charge_id: str,
        seller_account_id: str,
        amount_cents: int,
    ) -> str | None:
        raise NotImplementedError

    def refund(
        self,
        order_id: int,
        payment_intent_id: str,
        amount_cents: int,
    ) -> str | None:
        raise NotImplementedError

    def start_checkout(
        self, order_id: int, amount_cents: int, buyer_email: str
    ) -> dict:
        return {
            "payment_ref": self.hold(order_id, amount_cents, buyer_email),
            "checkout_url": None,
            "session_id": None,
        }


class SimulatedProvider(PaymentProvider):
    name = "simulado"

    def hold(self, order_id, amount_cents, buyer_email):
        return "SIM-" + secrets.token_hex(6).upper()

    def release(
        self, order_id, charge_id, seller_account_id, amount_cents
    ):
        return None

    def refund(self, order_id, payment_intent_id, amount_cents):
        return {"id": "SIM-REFUND-" + str(order_id), "status": "succeeded"}


class StripeProvider(PaymentProvider):
    name = "stripe"

    def __init__(self):
        if not config.STRIPE_SECRET_KEY:
            raise RuntimeError(
                "Falta configurar la variable STRIPE_SECRET_KEY."
            )

        import stripe

        self.stripe = stripe
        self.stripe.api_key = config.STRIPE_SECRET_KEY
        self.stripe.max_network_retries = 2

    def hold(self, order_id, amount_cents, buyer_email):
        """Crea Checkout; el webhook confirmará el pago."""
        session = self.stripe.checkout.Session.create(
            mode="payment",
            customer_email=buyer_email,
            line_items=[{
                "price_data": {
                    "currency": "mxn",
                    "product_data": {
                        "name": f"Compra ECO-GALLO #{order_id}",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            success_url=config.STRIPE_SUCCESS_URL,
            cancel_url=config.STRIPE_CANCEL_URL,
            metadata={"order_id": str(order_id)},
            payment_intent_data={
                "transfer_group": f"ORDER_{order_id}",
            },
            idempotency_key=f"ecogallo-checkout-{order_id}",
        )
        return session.id

    def start_checkout(self, order_id, amount_cents, buyer_email):
        session = self.stripe.checkout.Session.create(
            mode="payment",
            customer_email=buyer_email,
            line_items=[{
                "price_data": {
                    "currency": "mxn",
                    "product_data": {
                        "name": f"Compra ECO-GALLO #{order_id}",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            success_url=config.STRIPE_SUCCESS_URL + f"/{order_id}",
            cancel_url=config.STRIPE_CANCEL_URL + f"/{order_id}",
            payment_method_types=["card"],
            metadata={"order_id": str(order_id)},
            payment_intent_data={
                "transfer_group": f"ORDER_{order_id}",
            },
            idempotency_key=f"ecogallo-checkout-{order_id}",
        )

        return {
            "payment_ref": session.id,
            "checkout_url": session.url,
            "session_id": session.id,
        }

    def release(
        self,
        order_id,
        charge_id,
        seller_account_id,
        amount_cents,
    ):

        if (
            config.STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_"))
            and config.CONNECT_SIMULATED
            and seller_account_id.startswith("SIM-CONNECT-")
        ):
            return f"SIM-TRANSFER-{order_id}"

        """Transfiere al vendedor usando el cargo original como fuente."""
        if not charge_id:
            raise RuntimeError(
                "La orden no tiene un ID de cargo de Stripe."
            )

        if not seller_account_id:
            raise RuntimeError(
                "El vendedor todavía no tiene una cuenta Stripe Connect."
            )

        if amount_cents <= 0:
            raise ValueError("El importe de la transferencia no es válido.")

        existing = self.stripe.Transfer.list(transfer_group=f"ORDER_{order_id}", limit=100)
        for transfer in existing.auto_paging_iter():
            if (transfer.to_dict() if hasattr(transfer, "to_dict") else transfer)["metadata"].get("ecogallo_order_id") == str(order_id):
                return transfer.id
        transfer = self.stripe.Transfer.create(
            amount=amount_cents,
            currency="mxn",
            destination=seller_account_id,
            source_transaction=charge_id,
            transfer_group=f"ORDER_{order_id}",
            metadata={
                "ecogallo_order_id": str(order_id),
            },
            idempotency_key=f"ecogallo-release-{order_id}",
        )

        return transfer.id

    def refund(self, order_id, payment_intent_id, amount_cents):
        """Reembolsa al comprador desde el cargo de la plataforma."""
        if not payment_intent_id:
            raise RuntimeError(
                "La orden no tiene un PaymentIntent de Stripe."
            )

        if amount_cents <= 0:
            raise ValueError("El importe del reembolso no es válido.")

        existing = self.stripe.Refund.list(payment_intent=payment_intent_id, limit=100)
        for refund in existing.auto_paging_iter():
            if (refund.to_dict() if hasattr(refund, "to_dict") else refund)["metadata"].get("ecogallo_order_id") == str(order_id):
                return {"id": refund.id, "status": refund.status}
        refund = self.stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=amount_cents,
            metadata={
                "ecogallo_order_id": str(order_id),
            },
            idempotency_key=f"ecogallo-refund-{order_id}",
        )

        return {"id": refund.id, "status": refund.status}


class MercadoPagoProvider(PaymentProvider):
    """Checkout Pro de Mercado Pago. El cobro se confirma por consulta a la API (mercadopago.sync_group).

    Liberar no mueve dinero por API: la orden queda «por liquidar» y administración paga al vendedor
    y registra la referencia. Los reembolsos sí se hacen por API (parciales por orden).
    """
    name = "mercadopago"

    def __init__(self):
        if not config.MP_ACCESS_TOKEN:
            raise RuntimeError("Falta configurar MERCADOPAGO_ACCESS_TOKEN.")
        import mercadopago
        self.mp = mercadopago

    def release(self, order_id, charge_id, seller_account_id, amount_cents):
        return f"MP-PAYOUT-{order_id}"

    def refund(self, order_id, payment_intent_id, amount_cents):
        return self.mp.refund(order_id, payment_intent_id, amount_cents)


def get_provider(name=None) -> PaymentProvider:
    name = name or config.PAYMENT_PROVIDER
    if name == "stripe":
        return StripeProvider()
    if name == "mercadopago":
        return MercadoPagoProvider()
    if name == "simulado" and not config.PRODUCTION:
        return SimulatedProvider()
    raise RuntimeError("Los pagos están deshabilitados o requieren completar la configuración.")


def seller_ready(account_id):
    if config.CONNECT_SIMULATED and config.STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")):
        return bool(account_id and account_id.startswith('SIM-CONNECT-'))
    if not account_id or not account_id.startswith('acct_'):
        return False
    from connect import _stripe_client, _account_status
    account = _stripe_client().v2.core.accounts.retrieve(account_id, {'include': ['configuration.recipient', 'requirements']})
    return _account_status(account)['connected']
