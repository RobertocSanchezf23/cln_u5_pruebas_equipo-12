"""PIA CleanPro - R3: RB-12/RB-14 (cargos autorizados antes de facturar) y RB-15 (rol)."""
from decimal import Decimal

import pytest

from src.cleanpro.dominio import AutorizacionDenegada, FacturacionNoPermitida, Rol


def en_proceso(servicio):
    servicio.programar()
    servicio.iniciar()
    return servicio


def test_cln_cp10_exito_cargo_autorizado_se_suma_a_la_factura(servicios):
    servicio = en_proceso(servicios["CLN-O010"])  # 6,745.00
    cargo = servicio.registrar_cargo("Limpieza de alfombra extra", Decimal("350.00"))
    servicio.autorizar_cargo(cargo, Rol.COORDINADOR)
    servicio.completar()
    assert servicio.calcular_factura() == Decimal("7095.00")


def test_cln_cp11_error_cargo_sin_autorizar_bloquea_la_factura(servicios):
    servicio = en_proceso(servicios["CLN-O011"])
    servicio.registrar_cargo("Material especial", Decimal("500.00"))
    servicio.completar()
    with pytest.raises(FacturacionNoPermitida, match="RB-14"):
        servicio.calcular_factura()


@pytest.mark.parametrize("rol", [Rol.SUPERVISOR, Rol.ADMINISTRACION])
def test_cln_cp12_error_solo_el_coordinador_autoriza(servicios, rol):
    servicio = en_proceso(servicios["CLN-O012"])
    cargo = servicio.registrar_cargo("Servicio adicional en sitio", Decimal("200.00"))
    with pytest.raises(AutorizacionDenegada, match="RB-15"):
        servicio.autorizar_cargo(cargo, rol)
    assert cargo.autorizado is False


def test_cln_cp13_limite_un_centavo_sin_autorizar_tambien_bloquea(servicios):
    servicio = en_proceso(servicios["CLN-O014"])
    servicio.registrar_cargo("Cargo mínimo", Decimal("0.01"))
    servicio.completar()
    with pytest.raises(FacturacionNoPermitida, match="RB-14"):
        servicio.calcular_factura()


def test_cln_cargo_en_cero_no_es_valido(servicios):
    servicio = en_proceso(servicios["CLN-O014"])
    with pytest.raises(ValueError, match="mayor que cero"):
        servicio.registrar_cargo("Cargo vacío", Decimal("0"))
