"""PIA CleanPro - R1: RB-02 + precondiciones del paquete (programar un servicio).

Datos: datos/cleanpro (paquete del PIA). Cada prueba usa una carga nueva.
"""
import pytest

from src.cleanpro.dominio import EstadoServicio, ServicioNoProgramable


def test_cln_cp01_exito_servicio_aceptado_se_programa(servicios):
    servicio = servicios["CLN-O001"]  # C020 activo, cotización aceptada, 2 servicios
    servicio.programar()
    assert servicio.estado == EstadoServicio.PROGRAMADO
    assert servicio.eventos == ["ServicioProgramado"]


@pytest.mark.parametrize(
    "servicio_id, regla, motivo",
    [
        ("CLN-O008", "RB-02", "no ha aceptado la cotización"),  # CP02 error
        ("CLN-O022", "PIA-precondición", "cliente está inactivo"),  # CP03 error
        ("CLN-O013", "PIA-precondición", "no tiene servicios"),  # CP04 límite: 0 líneas
        ("CLN-O005", "PIA-precondición", "servicio deshabilitado"),  # CP05 error
    ],
    ids=["CP02-no-aceptada", "CP03-cliente-inactivo", "CP04-sin-detalle", "CP05-deshabilitado"],
)
def test_cln_rechazos_al_programar(servicios, servicio_id, regla, motivo):
    servicio = servicios[servicio_id]
    with pytest.raises(ServicioNoProgramable, match=motivo) as error:
        servicio.programar()
    assert error.value.regla == regla
    assert servicio.estado == EstadoServicio.SOLICITADO  # no cambia si la regla falla
    assert servicio.eventos == []


def test_cln_no_se_programa_dos_veces(servicios):
    servicio = servicios["CLN-O001"]
    servicio.programar()
    with pytest.raises(Exception, match="estado PROGRAMADO"):
        servicio.programar()
    assert servicio.eventos == ["ServicioProgramado"]
