"""PIA CleanPro - R2: RB-07 (solo se factura un servicio terminado) y RB-11 (50 %)."""
from decimal import Decimal

import pytest

from src.cleanpro.dominio import EstadoServicio, FacturacionNoPermitida, TransicionInvalida


def test_cln_cp06_exito_servicio_completado_se_factura_completo(servicios):
    servicio = servicios["CLN-O006"]  # Industrial 04 x4 = 2,840.00
    servicio.programar()
    servicio.iniciar()
    servicio.completar()
    assert servicio.calcular_factura() == Decimal("2840.00")
    assert servicio.eventos == ["ServicioProgramado", "ServicioIniciado", "ServicioCompletado"]


def test_cln_cp07_error_servicio_programado_no_se_factura(servicios):
    servicio = servicios["CLN-O007"]
    servicio.programar()
    with pytest.raises(FacturacionNoPermitida, match="RB-07"):
        servicio.calcular_factura()


def test_cln_cp08_limite_15_minutos_no_realizado_cobra_50(servicios):
    servicio = servicios["CLN-O003"]  # Profunda 15 x1 = 1,491.00
    servicio.programar()
    servicio.registrar_acceso_denegado(minutos_espera=15)
    assert servicio.estado == EstadoServicio.NO_REALIZADO
    assert servicio.calcular_factura() == Decimal("745.50")


def test_cln_cp09_limite_14_minutos_aun_no_es_no_realizado(servicios):
    servicio = servicios["CLN-O004"]
    servicio.programar()
    with pytest.raises(TransicionInvalida, match="RB-11"):
        servicio.registrar_acceso_denegado(minutos_espera=14)
    assert servicio.estado == EstadoServicio.PROGRAMADO


def test_cln_no_se_completa_sin_iniciar(servicios):
    servicio = servicios["CLN-O006"]
    servicio.programar()
    with pytest.raises(TransicionInvalida, match="no se puede completar"):
        servicio.completar()
