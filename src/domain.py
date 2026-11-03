from dataclasses import dataclass

VIP_DISCOUNT_RATE = 0.15


class CustomerHasDebt(Exception):
    pass


class OrderAlreadyConfirmed(ValueError):
    """Regla agregada con TDD: un pedido no puede confirmarse dos veces."""


@dataclass
class Order:
    total: float
    vip: bool = False
    status: str = "NEW"
    discount: float = 0.0

    def confirm(self, customer_debt=0):
        self._ensure_can_be_confirmed(customer_debt)
        self.discount = round(self.total * VIP_DISCOUNT_RATE, 2) if self.vip else 0.0
        self.status = "CONFIRMED"
        return self.total - self.discount

    def _ensure_can_be_confirmed(self, customer_debt):
        # REFACTOR: las validaciones se extrajeron a un método privado; el comportamiento
        # público (excepciones y mensajes) es exactamente el mismo que en la fase GREEN.
        if self.status == "CONFIRMED":
            raise OrderAlreadyConfirmed("already confirmed")
        if self.total <= 0:
            raise ValueError("total must be positive")
        if customer_debt > 0:
            raise CustomerHasDebt("outstanding debt")
