"""Proveedor de pagos con retención (escrow).

`SimulatedProvider` NO mueve dinero real ni pide datos de tarjeta: sirve para
demostrar y probar el flujo completo. Para producción, implementa la misma
interfaz con una pasarela que soporte retención / pago diferido
(p. ej. Stripe Connect con captura manual, o Mercado Pago con liberación
posterior) y cámbiala en `get_provider()`.
"""
import secrets


class PaymentProvider:
    name = "base"

    def hold(self, order_id: int, amount_cents: int, buyer_email: str) -> str:
        """Cobra y RETIENE los fondos. Devuelve una referencia de pago."""
        raise NotImplementedError

    def release(self, payment_ref: str, seller_email: str, amount_cents: int) -> None:
        """Libera los fondos retenidos al vendedor."""
        raise NotImplementedError

    def refund(self, payment_ref: str, amount_cents: int) -> None:
        """Devuelve los fondos retenidos al comprador."""
        raise NotImplementedError


class SimulatedProvider(PaymentProvider):
    name = "simulado"

    def hold(self, order_id, amount_cents, buyer_email):
        return "SIM-" + secrets.token_hex(6).upper()

    def release(self, payment_ref, seller_email, amount_cents):
        return None

    def refund(self, payment_ref, amount_cents):
        return None


def get_provider() -> PaymentProvider:
    return SimulatedProvider()
