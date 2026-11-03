from unittest.mock import Mock, call

import pytest

from src.application import OrderService
from src.domain import Order


def test_gateway_approved():
    gateway = Mock()
    gateway.charge.return_value = True
    assert OrderService(gateway).checkout(Order(100)) == 100
    gateway.charge.assert_called_once_with(100)

def test_gateway_rejected():
    gateway = Mock()
    gateway.charge.return_value = False
    with pytest.raises(RuntimeError):
        OrderService(gateway).checkout(Order(100))


# ---------------------------------------------------------------------------
# Pruebas agregadas por el equipo (E5)
# ---------------------------------------------------------------------------
def test_vip_200_pago_rechazado_intento_cobrar_170():
    gateway = Mock()
    gateway.charge.return_value = False
    with pytest.raises(RuntimeError, match="payment rejected"):
        OrderService(gateway).checkout(Order(200, vip=True))
    gateway.charge.assert_called_once_with(170)


def test_timeout_de_la_pasarela_no_se_reintenta():
    gateway = Mock()
    gateway.charge.side_effect = TimeoutError("gateway timeout")
    with pytest.raises(TimeoutError):
        OrderService(gateway).checkout(Order(100))
    assert gateway.charge.call_count == 1


def test_mock_no_hace_cargos_reales():
    gateway = Mock()
    gateway.charge.return_value = True
    OrderService(gateway).checkout(Order(100))
    # La única interacción fue la llamada simulada que la prueba controla.
    assert gateway.method_calls == [call.charge(100)]


def test_riesgo_pedido_queda_confirmado_aunque_el_pago_falle():
    """Prueba de caracterización: documenta el riesgo de consistencia del código base."""
    gateway = Mock()
    gateway.charge.return_value = False
    order = Order(100)
    with pytest.raises(RuntimeError):
        OrderService(gateway).checkout(order)
    assert order.status == "CONFIRMED"  # riesgo: confirmado sin pago exitoso
