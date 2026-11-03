import pytest

from src.domain import CustomerHasDebt, Order


def test_vip_discount():
    o = Order(100, vip=True)
    assert o.confirm() == 90
    assert o.status == "CONFIRMED"

def test_regular_no_discount():
    assert Order(100).confirm() == 100

def test_customer_debt():
    with pytest.raises(CustomerHasDebt):
        Order(100).confirm(customer_debt=50)

@pytest.mark.parametrize("total", [0, -1])
def test_invalid_total(total):
    with pytest.raises(ValueError):
        Order(total).confirm()


def test_vip_200_paga_170():
    order = Order(200, vip=True)  # Arrange: pedido VIP de $200
    amount = order.confirm()  # Act: confirmar
    assert amount == 170  # Assert: 15% de descuento
    assert order.discount == 30
    assert order.status == "CONFIRMED"


def test_regular_200_paga_200():
    order = Order(200)  # Arrange: cliente regular
    amount = order.confirm()  # Act
    assert amount == 200  # Assert: sin descuento
    assert order.discount == 0


def test_cannot_confirm_twice():
    order = Order(100)
    order.confirm()
    with pytest.raises(ValueError, match="already confirmed"):
        order.confirm()
