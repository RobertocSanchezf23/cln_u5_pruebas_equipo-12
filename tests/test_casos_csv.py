"""Casos CP01-CP12 de datos/casos_de_prueba.csv, leídos con csv.DictReader.

Cada caso se une con su pedido de datos/pedidos_prueba.csv (total, VIP, deuda y estado
inicial) y se compara el resultado real contra el resultado esperado del CSV.
"""
import csv
from pathlib import Path

import pytest

from src.domain import CustomerHasDebt, Order

DATOS = Path(__file__).resolve().parents[1] / "datos"
EXCEPCIONES = {"CustomerHasDebt": CustomerHasDebt, "ValueError": ValueError}


def _leer(nombre):
    with (DATOS / nombre).open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


PEDIDOS = {fila["pedido_id"]: fila for fila in _leer("pedidos_prueba.csv")}
CASOS = [caso for caso in _leer("casos_de_prueba.csv") if caso["accion"] == "confirmar"]


def construir_pedido(pedido):
    return Order(
        total=float(pedido["total"]),
        vip=pedido["es_vip"] == "1",
        status=pedido["estado_inicial"],
    )


@pytest.mark.parametrize("caso", CASOS, ids=[c["caso_id"] for c in CASOS])
def test_caso_del_csv(caso):
    pedido = PEDIDOS[caso["pedido_id"]]
    order = construir_pedido(pedido)  # Arrange
    deuda = float(pedido["deuda_cliente"])
    esperado = caso["resultado_esperado"]

    if "TDD" in caso["nota"]:
        # CP08: el CSV describe el comportamiento ANTERIOR (confirmaba dos veces).
        # Después del ciclo Red-Green-Refactor la regla nueva lo rechaza.
        with pytest.raises(ValueError, match="already confirmed"):
            order.confirm(customer_debt=deuda)
        assert order.status == "CONFIRMED"
    elif esperado in EXCEPCIONES:
        with pytest.raises(EXCEPCIONES[esperado]):  # Act + Assert (error)
            order.confirm(customer_debt=deuda)
        assert order.status == "NEW"  # el pedido no cambia si la regla falla
    else:
        cobro = float(esperado.split("cobro")[1])  # "CONFIRMED, cobro 170.00" -> 170.0
        assert order.confirm(customer_debt=deuda) == pytest.approx(cobro, abs=0.001)
        assert order.status == "CONFIRMED"


def test_el_csv_tiene_los_15_casos_del_paquete():
    ids = [c["caso_id"] for c in _leer("casos_de_prueba.csv")]
    assert ids == [f"CP{n:02d}" for n in range(1, 16)]
