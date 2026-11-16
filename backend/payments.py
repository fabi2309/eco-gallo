
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
        return None


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
            success_url=(
                config.STRIPE_SUCCESS_URL
                + "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=config.STRIPE_CANCEL_URL,
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
            config.CONNECT_SIMULATED
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

        refund = self.stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=amount_cents,
            metadata={
                "ecogallo_order_id": str(order_id),
            },
            idempotency_key=f"ecogallo-refund-{order_id}",
        )

        return refund.id


def get_provider() -> PaymentProvider:
    if config.PAYMENT_PROVIDER == "stripe":
        return StripeProvider()

    if config.PAYMENT_PROVIDER == "simulado":
        return SimulatedProvider()

    raise RuntimeError(
        f"Proveedor de pagos no reconocido: {config.PAYMENT_PROVIDER}"
    )
